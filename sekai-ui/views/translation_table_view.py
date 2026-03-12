from PySide6.QtWidgets import QTableView, QHeaderView

from views.status_delegate import StatusDelegate
from PySide6.QtCore import Qt


class TranslationTableView(QTableView):
    """
    View da tabela de tradução.
    Visual e UX fiéis ao SekaiTranslator antigo.

    - Usa delegate compatível para preservar as cores do status
    - Status é exibido por cor de fundo da linha (via model)
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setSelectionBehavior(QTableView.SelectRows)
        self.setSelectionMode(QTableView.ExtendedSelection)

        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.setShowGrid(False)

        # NOTE:
        # Em alguns estilos (principalmente no Windows com scaling fracionário),
        # selecionar várias linhas pode aparentar um "vão"/linha em branco entre
        # as linhas selecionadas. Isso costuma vir de borda/padding padrão.
        # Forçamos itens sem borda/padding para a seleção ficar "contínua".

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
        self.setItemDelegate(StatusDelegate(self))

        try:
            self.viewport().setProperty("sekaiOverlayViewport", True)
            self.viewport().setAttribute(Qt.WA_StyledBackground, True)
            self.viewport().setAutoFillBackground(False)
        except Exception:
            pass
