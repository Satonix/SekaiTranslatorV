from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class PluginsTab(QWidget):
    """
    Aba fixa de gerenciamento de plugins (layout-only).
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        title = QLabel("Plugins")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")

        hint = QLabel(
            "Gerencie plugins do SekaiTranslator.\n\n"
            "(Conteúdo será conectado futuramente)"
        )

        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addStretch()
