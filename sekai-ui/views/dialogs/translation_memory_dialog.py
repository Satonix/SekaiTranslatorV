from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QMessageBox,
)


class TranslationMemoryDialog(QDialog):
    """
    Dialog simples de Memória de Tradução — placeholder.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Memória de Tradução")
        self.resize(520, 380)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Memória de Tradução")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        info = QLabel(
            "Correspondências de tradução armazenadas.\n"
            "(Exato / Similar — futuro)"
        )
        info.setStyleSheet("color: #777;")
        layout.addWidget(info)

        self.memory_list = QListWidget()
        layout.addWidget(self.memory_list, 1)

        self._load_dummy_memory()

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_clear = QPushButton("Limpar")
        self.btn_close = QPushButton("Fechar")

        btn_layout.addWidget(self.btn_clear)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

        self.btn_clear.clicked.connect(self._wip)
        self.btn_close.clicked.connect(self.reject)

    def _load_dummy_memory(self):
        items = [
            "……雪が降ってる。 → …Está nevando.",
            "今日は寒いね。 → Hoje está frio.",
        ]
        self.memory_list.addItems(items)

    def _wip(self):
        QMessageBox.information(
            self,
            "Memória de Tradução",
            "Funcionalidade ainda não implementada."
        )
