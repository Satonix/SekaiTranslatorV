from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QPushButton,
)


class AboutDialog(QDialog):
    """
    Dialog Sobre — simples e fiel ao SekaiTranslator antigo.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Sobre")
        self.resize(360, 220)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("SekaiTranslator")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        version = QLabel("Versão 1.0 (UI em reconstrução)")
        layout.addWidget(version)

        desc = QLabel(
            "Ferramenta de tradução de Visual Novels.\n\n"
            "Projeto focado em produtividade,\n"
            "qualidade e extensibilidade."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addStretch()

        btn = QPushButton("Fechar")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)
