from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex
from PySide6.QtGui import QColor


class TranslationTableModel(QAbstractTableModel):
    """
    Modelo de tabela fiel ao SekaiTranslator antigo.

    - NÃO possui coluna Status
    - Status é representado APENAS por cor de fundo da linha
    - Modelo somente leitura
    - Mostra apenas entries traduzíveis (is_translatable == True)
    """

    COLUMNS = ["Linha", "Personagem", "Original", "Tradução"]

    # Cores suaves para tema escuro (TEMPORÁRIO)
    STATUS_COLORS = {
        "untranslated": None,                       # padrão
        "in_progress": QColor(70, 110, 180, 80),    # azul suave
        "translated": QColor(70, 160, 120, 80),     # verde suave
        "reviewed": QColor(140, 110, 180, 80),      # roxo suave
    }

    def __init__(self, entries=None, parent=None):
        super().__init__(parent)

        # all_entries = tudo que veio do core
        self.all_entries: list[dict] = entries or []

        # entries = apenas traduzíveis (o que aparece na tabela)
        self.entries: list[dict] = []
        self.set_entries(self.all_entries)

    # Qt básicos
    def rowCount(self, parent=QModelIndex()):
        return len(self.entries)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None

        if orientation == Qt.Horizontal:
            if 0 <= section < len(self.COLUMNS):
                return self.COLUMNS[section]
            return None

        return section + 1

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled

    # Data
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        entry = self.entries[index.row()]
        col = index.column()

        # Texto
        if role == Qt.DisplayRole:
            if col == 0:
                # Linha real do arquivo quando disponível (Kirikiri: line_number)
                ln = entry.get("line_number")
                if isinstance(ln, int) and ln > 0:
                    return ln
                # fallback: índice visível
                return index.row() + 1

            if col == 1:
                return entry.get("speaker") or ""

            if col == 2:
                return entry.get("original", "") or ""

            if col == 3:
                return entry.get("translation", "") or ""

        # Alinhamento
        if role == Qt.TextAlignmentRole:
            if col == 0:
                return Qt.AlignCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        # Cor de fundo (status)
        if role == Qt.BackgroundRole:
            status = entry.get("status", "untranslated")

            # Se por algum motivo vier como algo não-string, faz fallback
            if not isinstance(status, str):
                status = "untranslated"

            return self.STATUS_COLORS.get(status)

        return None

    # Helpers
    def set_entries(self, entries: list[dict]):
        """
        Recebe entradas do core e mantém apenas as traduzíveis na tabela.
        """
        self.beginResetModel()

        self.all_entries = entries or []
        self.entries = [
            e for e in self.all_entries
            if e.get("is_translatable", True)  # fallback True por compat
        ]

        self.endResetModel()

    def refresh_row(self, row: int):
        """
        Re-renderiza visualmente uma linha específica (da TABELA visível).
        """
        if 0 <= row < self.rowCount():
            left = self.index(row, 0)
            right = self.index(row, self.columnCount() - 1)
            self.dataChanged.emit(left, right)

    def visible_row_to_source_row(self, visible_row: int) -> int | None:
        """
        Converte row da tabela (filtrada) para row no vetor original do arquivo.
        Útil para o FileTab mapear seleção -> entrada original.
        """
        if not (0 <= visible_row < len(self.entries)):
            return None

        # Se o core tiver uma chave única, use-a (entry_id).
        vid = self.entries[visible_row].get("entry_id")
        if vid:
            for i, e in enumerate(self.all_entries):
                if e.get("entry_id") == vid:
                    return i

        # Fallback: tenta por line_number + original (não perfeito, mas seguro)
        ln = self.entries[visible_row].get("line_number")
        orig = self.entries[visible_row].get("original")
        for i, e in enumerate(self.all_entries):
            if e.get("line_number") == ln and e.get("original") == orig:
                return i

        return None
