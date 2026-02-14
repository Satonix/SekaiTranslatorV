from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class PromptManagerTab(QWidget):
    """
    Aba fixa de gerenciamento de prompts / IA (layout-only).
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        title = QLabel("Prompts / IA")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")

        hint = QLabel(
            "Gerencie prompts e comportamento da IA.\n\n"
            "(Preview, templates, contexto, etc.)"
        )

        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addStretch()
