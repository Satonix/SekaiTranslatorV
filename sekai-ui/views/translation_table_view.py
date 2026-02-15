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

        self.setSelectionBehavior(QTableView.SelectRows)
        self.setSelectionMode(QTableView.ExtendedSelection)

        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.setShowGrid(False)

        self.setStyleSheet("""
            QTableView {
                outline: 0;
            }
        """)

        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(26)

        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        header.setHighlightSections(False)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)

        self.setHorizontalScrollMode(QTableView.ScrollPerPixel)
        self.setVerticalScrollMode(QTableView.ScrollPerPixel)

        self.setSortingEnabled(False)
        self.setTabKeyNavigation(False)
