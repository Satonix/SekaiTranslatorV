from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem,
    QPushButton, QMessageBox
)
from PySide6.QtCore import Qt


class OpenProjectDialog(QDialog):
    """
    Dialog de abertura de projetos.
    Comunicação 100% via sekai-core.
    """

    def __init__(self, core_client, parent=None):
        super().__init__(parent)

        self.core = core_client
        self.project_path = None

        self.setWindowTitle("Abrir Projeto")
        self.resize(460, 380)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("<b>Projetos existentes</b>"))

        # Lista de projetos
        self.list = QListWidget()
        layout.addWidget(self.list)

        # Botões
        btn_layout = QHBoxLayout()

        self.open_btn = QPushButton("Abrir")
        self.rename_btn = QPushButton("Renomear")
        self.delete_btn = QPushButton("Deletar")

        self.open_btn.clicked.connect(self._open)
        self.rename_btn.clicked.connect(self._rename_wip)
        self.delete_btn.clicked.connect(self._delete_wip)

        btn_layout.addWidget(self.open_btn)
        btn_layout.addWidget(self.rename_btn)
        btn_layout.addWidget(self.delete_btn)

        layout.addLayout(btn_layout)

        # Eventos
        self.list.itemDoubleClicked.connect(self._open_item)

        # Estado inicial
        self._load_projects()

    # Core interaction
    def _load_projects(self):
        self.list.clear()

        resp = self.core.send("project.list")

        if resp.get("status") != "ok":
            QMessageBox.critical(
                self,
                "Erro",
                resp.get("message", "Erro ao listar projetos")
            )
            return

        projects = resp["payload"].get("projects", [])

        if not projects:
            self.list.addItem("(Nenhum projeto encontrado)")
            self.list.setEnabled(False)
            self.open_btn.setEnabled(False)
            self.rename_btn.setEnabled(False)
            self.delete_btn.setEnabled(False)
            return

        self.list.setEnabled(True)
        self.open_btn.setEnabled(True)

        # Ainda não implementados no core
        self.rename_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)

        for p in projects:
            item = QListWidgetItem(p["name"])
            item.setData(Qt.UserRole, p)
            self.list.addItem(item)

    # Actions
    def _open_item(self, item: QListWidgetItem):
        self.project_path = item.data(Qt.UserRole)["project_path"]
        self.accept()

    def _open(self):
        item = self.list.currentItem()
        if not item:
            QMessageBox.warning(
                self,
                "Aviso",
                "Selecione um projeto para abrir."
            )
            return

        self.project_path = item.data(Qt.UserRole)["project_path"]
        self.accept()

    # Placeholders (WIP)
    def _rename_wip(self):
        QMessageBox.information(
            self,
            "Em desenvolvimento",
            "Renomear projeto ainda não está disponível."
        )

    def _delete_wip(self):
        QMessageBox.information(
            self,
            "Em desenvolvimento",
            "Excluir projeto ainda não está disponível."
        )
