from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from parsers.api import ParsersAPI


class PluginManagerDialog(QDialog):
    """Gerencia parsers (formato Opção A).

    No formato novo, os parsers vivem em um único repo Python e são
    listados via registry. A UI oferece apenas "Atualizar".
    """

    def __init__(self, parent=None, repo_url: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("Parsers")
        self.setMinimumSize(720, 420)

        self.api = ParsersAPI(repo_url=repo_url)

        self.listw = QListWidget(self)
        self.listw.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

        self.lbl_info = QLabel("", self)
        self.lbl_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.lbl_info.setWordWrap(True)

        self.btn_refresh = QPushButton("Recarregar lista", self)
        self.btn_update = QPushButton("Atualizar repo", self)
        self.btn_close = QPushButton("Fechar", self)

        top = QHBoxLayout()
        top.addWidget(QLabel("Parsers disponíveis (repo externo):", self))
        top.addStretch(1)
        top.addWidget(self.btn_update)
        top.addWidget(self.btn_refresh)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(self.btn_close)

        lay = QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self.listw, 1)
        lay.addWidget(self.lbl_info)
        lay.addLayout(bottom)

        self.btn_close.clicked.connect(self.accept)
        self.btn_refresh.clicked.connect(self.reload)
        self.btn_update.clicked.connect(self.update_repo)
        self.listw.currentItemChanged.connect(self._on_sel)

        self.reload()

    def reload(self) -> None:
        try:
            items = self.api.list_available()
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return

        self.listw.clear()
        for p in items:
            title = f"{p.get('name') or p.get('id')}  ({p.get('id')})"
            it = QListWidgetItem(title)
            it.setData(Qt.ItemDataRole.UserRole, p)
            self.listw.addItem(it)

        if self.listw.count() > 0:
            self.listw.setCurrentRow(0)

    def update_repo(self) -> None:
        try:
            self.api.update_repo()
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return
        self.reload()

    def _on_sel(self, cur: QListWidgetItem | None, _prev: QListWidgetItem | None) -> None:
        if not cur:
            self.lbl_info.setText("")
            return
        p = cur.data(Qt.ItemDataRole.UserRole) or {}
        desc = (p.get("description") or "").strip()
        exts = ", ".join(p.get("extensions") or [])
        ver = (p.get("version") or "").strip()
        self.lbl_info.setText(
            f"ID: {p.get('id') or ''}\n"
            f"Versão: {ver}\n"
            f"Extensões: {exts}\n\n"
            f"{desc}"
        )
