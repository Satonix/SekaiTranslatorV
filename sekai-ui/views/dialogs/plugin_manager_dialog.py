from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QMessageBox,
    QTabWidget,
    QWidget,
)

from parsers.manager import get_parser_manager, reload_parsers
from parsers.repository import install_from_github_zip, remove_external_parser


REPO_OWNER = "Satonix"
REPO_NAME = "SekaiTranslator-Parsers"
REPO_BRANCH = "main"


class PluginManagerDialog(QDialog):
    """
    Gerenciador com abas:
    - Parsers (real): instala/recarrega/remove parsers externos
    - Plugins (placeholder): mantém o dummy por enquanto
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Gerenciador de Plugins")
        self.resize(620, 420)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("Gerenciador")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        self.parsers_tab = self._build_parsers_tab()
        self.plugins_tab = self._build_plugins_tab()

        self.tabs.addTab(self.parsers_tab, "Parsers")
        self.tabs.addTab(self.plugins_tab, "Plugins")

        self._reload_parsers_list()

    def _build_parsers_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        hint = QLabel(
            "Parsers definem como o SekaiTranslator extrai e reconstrói texto.\n"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888;")
        outer.addWidget(hint)

        self.parsers_list = QListWidget()
        self.parsers_list.setSelectionMode(QListWidget.SingleSelection)
        outer.addWidget(self.parsers_list, 1)

        btns = QHBoxLayout()
        btns.addStretch()

        self.btn_install = QPushButton("Instalar/Atualizar do GitHub")
        self.btn_remove = QPushButton("Remover Selecionado")
        self.btn_reload = QPushButton("Recarregar")

        btns.addWidget(self.btn_install)
        btns.addWidget(self.btn_remove)
        btns.addWidget(self.btn_reload)

        outer.addLayout(btns)

        self.btn_install.clicked.connect(self._install_from_repo)
        self.btn_remove.clicked.connect(self._remove_selected_parser)
        self.btn_reload.clicked.connect(self._reload_parsers_list)

        self.parsers_list.itemSelectionChanged.connect(self._refresh_parsers_buttons)

        return w

    def _reload_parsers_list(self) -> None:
        try:
            reload_parsers()
        except Exception:
            pass

        self.parsers_list.clear()

        mgr = get_parser_manager()
        reg_items = mgr.registry.all()

        def _sort_key(rp):
            src = getattr(rp, "source", "")
            p = rp.plugin
            name = getattr(p, "name", getattr(p, "plugin_id", ""))
            return (0 if src == "builtin" else 1, str(name).lower())

        for rp in sorted(reg_items, key=_sort_key):
            p = rp.plugin
            pid = getattr(p, "plugin_id", "")
            name = getattr(p, "name", pid)
            src = rp.source

            exts = getattr(p, "extensions", None) or set()
            ext_txt = ", ".join(sorted({str(e).lower() for e in exts})) if exts else "auto"

            label = f"{name}  —  {pid}   [{src}]   (ext: {ext_txt})"
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, {"plugin_id": pid, "source": src})
            self.parsers_list.addItem(it)

        self._refresh_parsers_buttons()

    def _refresh_parsers_buttons(self) -> None:
        it = self.parsers_list.currentItem()
        if not it:
            self.btn_remove.setEnabled(False)
            return

        meta = it.data(Qt.UserRole) or {}
        src = (meta.get("source") or "").strip()
        self.btn_remove.setEnabled(src == "external")

    def _install_from_repo(self) -> None:
        try:
            self.btn_install.setEnabled(False)
            self.btn_remove.setEnabled(False)
            self.btn_reload.setEnabled(False)

            install_from_github_zip(
                "https://github.com/Satonix/SekaiTranslator-Parsers",
                branch="main",
            )


            QMessageBox.information(
                self,
                "Parsers",
                f"Parsers instalados/atualizados do repositório:\n{REPO_OWNER}/{REPO_NAME}",
            )
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
        finally:
            self.btn_install.setEnabled(True)
            self.btn_reload.setEnabled(True)
            self._reload_parsers_list()

    def _remove_selected_parser(self) -> None:
        it = self.parsers_list.currentItem()
        if not it:
            return

        meta = it.data(Qt.UserRole) or {}
        pid = (meta.get("plugin_id") or "").strip()
        src = (meta.get("source") or "").strip()
        if src != "external":
            return

        folder_name = pid

        res = QMessageBox.question(
            self,
            "Remover parser",
            f"Remover o parser externo:\n{pid}\n\nIsso apagará a pasta:\n{folder_name}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if res != QMessageBox.Yes:
            return

        try:
            remove_external_parser(folder_name)
            QMessageBox.information(self, "Parsers", f"Parser removido: {pid}")
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
        finally:
            self._reload_parsers_list()

    def _build_plugins_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        title = QLabel("Plugins (WIP)")
        title.setStyleSheet("font-weight: bold;")
        outer.addWidget(title)

        self.plugin_list = QListWidget()
        outer.addWidget(self.plugin_list, 1)

        self._load_dummy_plugins()

        btns = QHBoxLayout()
        btns.addStretch()

        self.btn_add = QPushButton("Adicionar")
        self.btn_remove2 = QPushButton("Remover")
        self.btn_reload2 = QPushButton("Recarregar")

        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_remove2)
        btns.addWidget(self.btn_reload2)

        outer.addLayout(btns)

        self.btn_add.clicked.connect(self._wip)
        self.btn_remove2.clicked.connect(self._wip)
        self.btn_reload2.clicked.connect(self._wip)

        return w

    def _load_dummy_plugins(self) -> None:
        self.plugin_list.clear()
        plugins = [
            "Visual: Colored Names",
            "QA: Line Overflow",
            "Glossary: Common Terms",
        ]
        self.plugin_list.addItems(plugins)

    def _wip(self) -> None:
        QMessageBox.information(self, "Em desenvolvimento", "Funcionalidade ainda não implementada.")
