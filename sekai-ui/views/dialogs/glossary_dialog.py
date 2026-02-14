from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QLineEdit,
    QMessageBox,
)


class GlossaryDialog(QDialog):
    """
    Dialog simples de Glossário — placeholder.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Glossário")
        self.resize(500, 360)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Glossário")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        # Lista de termos
        self.term_list = QListWidget()
        layout.addWidget(self.term_list, 1)

        self._load_dummy_terms()

        # Entrada
        self.term_edit = QLineEdit()
        self.term_edit.setPlaceholderText("Novo termo")
        layout.addWidget(self.term_edit)

        # Botões
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_add = QPushButton("Adicionar")
        self.btn_remove = QPushButton("Remover")
        self.btn_close = QPushButton("Fechar")

        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_remove)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

        self.btn_add.clicked.connect(self._wip)
        self.btn_remove.clicked.connect(self._wip)
        self.btn_close.clicked.connect(self.reject)

    def _load_dummy_terms(self):
        terms = [
            "主人公 → Protagonista",
            "先輩 → Veterano",
            "魔法 → Magia",
        ]
        self.term_list.addItems(terms)

    def _wip(self):
        QMessageBox.information(
            self,
            "Glossário",
            "Funcionalidade ainda não implementada."
        )
