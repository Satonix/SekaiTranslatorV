from PySide6.QtWidgets import QTableView, QHeaderView
from PySide6.QtCore import Qt


class TranslationTableView(QTableView):
    """
    View da tabela de tradução.
    Visual e UX fiéis ao SekaiTranslator antigo.

    - NÃO usa delegate de status
    - Status é exibido apenas por cor de fundo da linha (via model)
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Seleção
        self.setSelectionBehavior(QTableView.SelectRows)
        self.setSelectionMode(QTableView.ExtendedSelection)

        # Aparência
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.setShowGrid(False)

        # Remove outline feio de foco
        self.setStyleSheet("""
            QTableView {
                outline: 0;
            }
        """)

        # Headers
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(26)  # altura fiel ao antigo

        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        header.setHighlightSections(False)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        # Ajuste fino por coluna (opcional, mas fiel)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Linha
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Speaker
        header.setSectionResizeMode(2, QHeaderView.Stretch)           # Original
        header.setSectionResizeMode(3, QHeaderView.Stretch)           # Tradução

        # Scroll suave
        self.setHorizontalScrollMode(QTableView.ScrollPerPixel)
        self.setVerticalScrollMode(QTableView.ScrollPerPixel)

        # UX extra
        self.setSortingEnabled(False)
        self.setTabKeyNavigation(False)
