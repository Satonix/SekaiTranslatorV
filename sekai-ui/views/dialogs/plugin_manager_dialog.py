from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
    QMessageBox,
)

from parsers.api import list_parsers, install_or_update_repo, install_parser, remove_external_parser


KIND_HEADER = "header"
KIND_AVAILABLE = "available"
KIND_INSTALLED = "installed"


class PluginManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Gerenciador de Extensões")
        self.resize(720, 460)

        self._info_label = QLabel("")
        self._list = QListWidget()

        self._btn_repo = QPushButton("Baixar/Atualizar repositório")
        self._btn_install = QPushButton("Instalar selecionado")
        self._btn_remove = QPushButton("Remover selecionado")
        self._btn_close = QPushButton("Fechar")

        self._btn_repo.clicked.connect(self._install_from_repo)
        self._btn_install.clicked.connect(self._install_selected)
        self._btn_remove.clicked.connect(self._remove_selected)
        self._btn_close.clicked.connect(self.accept)
        self._list.currentItemChanged.connect(self._sync_buttons)

        root = QVBoxLayout(self)
        root.addWidget(self._info_label)
        root.addWidget(self._list, 1)

        row = QHBoxLayout()
        row.addWidget(self._btn_repo)
        row.addWidget(self._btn_install)
        row.addWidget(self._btn_remove)
        row.addStretch(1)
        row.addWidget(self._btn_close)
        root.addLayout(row)

        self._reload_parsers_list()

    def _add_header(self, text: str) -> None:
        it = QListWidgetItem(text)
        it.setFlags(Qt.ItemIsEnabled)
        it.setData(Qt.UserRole, KIND_HEADER)
        it.setData(Qt.UserRole + 1, "")
        it.setData(Qt.UserRole + 2, "")
        self._list.addItem(it)

    def _reload_parsers_list(self) -> None:
        self._list.clear()

        info = list_parsers()
        repo_ok = bool(info.get("repo_installed", False))
        installed = info.get("installed") or []
        available = info.get("available") or []

        self._info_label.setText(
            "Repositório: " + ("instalado" if repo_ok else "não instalado") +
            f" | Instalados: {len(installed)} | Disponíveis: {len(available)}"
        )

        installed_by_folder = {((p.get("folder") or "").strip()): p for p in installed if (p.get("folder") or "").strip()}
        installed_ids = {((p.get("plugin_id") or "").strip()) for p in installed if (p.get("plugin_id") or "").strip()}

        self._add_header("Instalados")
        installed_sorted = sorted(installed, key=lambda p: (p.get("name") or p.get("plugin_id") or "").lower())
        if not installed_sorted:
            it = QListWidgetItem("(nenhum)")
            it.setFlags(Qt.ItemIsEnabled)
            it.setData(Qt.UserRole, KIND_HEADER)
            self._list.addItem(it)
        else:
            for p in installed_sorted:
                pid = (p.get("plugin_id") or "").strip()
                name = (p.get("name") or "").strip() or pid or "(sem nome)"
                exts = p.get("extensions") or []
                folder = (p.get("folder") or "").strip() or ""
                label = f"{name}  ({', '.join(exts)})"
                it = QListWidgetItem(label)
                it.setData(Qt.UserRole, KIND_INSTALLED)
                it.setData(Qt.UserRole + 1, folder)
                it.setData(Qt.UserRole + 2, pid)
                self._list.addItem(it)

        self._add_header("Disponíveis (repo)")
        available_sorted = sorted(available, key=lambda p: (p.get("name") or p.get("plugin_id") or "").lower())
        if not available_sorted:
            it = QListWidgetItem("(nenhum)")
            it.setFlags(Qt.ItemIsEnabled)
            it.setData(Qt.UserRole, KIND_HEADER)
            self._list.addItem(it)
        else:
            for p in available_sorted:
                pid = (p.get("plugin_id") or "").strip()
                name = (p.get("name") or "").strip() or pid or "(sem nome)"
                exts = p.get("extensions") or []
                folder = (p.get("folder") or "").strip()

                installed_flag = False
                if folder and folder in installed_by_folder:
                    installed_flag = True
                elif pid and pid in installed_ids:
                    installed_flag = True

                suffix = " — instalado" if installed_flag else ""
                label = f"{name}  ({', '.join(exts)}){suffix}"
                it = QListWidgetItem(label)
                it.setData(Qt.UserRole, KIND_AVAILABLE)
                it.setData(Qt.UserRole + 1, folder)
                it.setData(Qt.UserRole + 2, pid)
                self._list.addItem(it)

        self._sync_buttons()

    def _sync_buttons(self) -> None:
        it = self._list.currentItem()
        if not it:
            self._btn_install.setEnabled(False)
            self._btn_remove.setEnabled(False)
            return

        kind = it.data(Qt.UserRole) or ""
        self._btn_install.setEnabled(kind == KIND_AVAILABLE and bool((it.data(Qt.UserRole + 1) or "").strip()))
        self._btn_remove.setEnabled(kind == KIND_INSTALLED and bool((it.data(Qt.UserRole + 1) or "").strip()))

    def _install_from_repo(self) -> None:
        try:
            install_or_update_repo()
            QMessageBox.information(self, "Extensões", "Repositório atualizado com sucesso.")
        except Exception as e:
            QMessageBox.critical(self, "Extensões", f"Falha ao atualizar repositório:\n\n{e}")
        self._reload_parsers_list()

    def _install_selected(self) -> None:
        it = self._list.currentItem()
        if not it:
            return
        kind = it.data(Qt.UserRole) or ""
        if kind != KIND_AVAILABLE:
            return

        folder = (it.data(Qt.UserRole + 1) or "").strip()
        if not folder:
            QMessageBox.critical(self, "Extensões", "Item inválido: folder vazio.")
            return

        try:
            install_parser(folder)
            QMessageBox.information(self, "Extensões", f"Instalado: {folder}")
        except Exception as e:
            QMessageBox.critical(self, "Extensões", f"Falha ao instalar:\n\n{e}")

        self._reload_parsers_list()

    def _remove_selected(self) -> None:
        it = self._list.currentItem()
        if not it:
            return

        kind = it.data(Qt.UserRole) or ""
        if kind != KIND_INSTALLED:
            return

        folder = (it.data(Qt.UserRole + 1) or "").strip()
        if not folder:
            return

        res = QMessageBox.question(
            self,
            "Remover extensão",
            f"Remover:\n\n{it.text()}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if res != QMessageBox.Yes:
            return

        try:
            remove_external_parser(folder)
        except Exception as e:
            QMessageBox.critical(self, "Extensões", f"Falha ao remover:\n\n{e}")

        self._reload_parsers_list()
