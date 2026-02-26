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

    STATUS_COLORS = {
        "untranslated": None,
        # Use opaque colors. Semi-transparent backgrounds can look "invisible"
        # depending on palette/style and Windows scaling.
        "in_progress": QColor(116, 120, 18, 255),  # 747812
        "translated": QColor(42, 79, 49, 255),     # 2A4F31
        "reviewed": QColor(140, 110, 180, 255),
    }

    def __init__(self, entries=None, parent=None):
        super().__init__(parent)

        self.all_entries: list[dict] = entries or []

        self.entries: list[dict] = []
        self.set_entries(self.all_entries)

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

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        entry = self.entries[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                ln = entry.get("line_number")
                if isinstance(ln, int) and ln > 0:
                    return ln
                return index.row() + 1

            if col == 1:
                return entry.get("speaker") or ""

            if col == 2:
                return entry.get("original", "") or ""

            if col == 3:
                return entry.get("translation", "") or ""

        if role == Qt.TextAlignmentRole:
            if col == 0:
                return Qt.AlignCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        if role == Qt.BackgroundRole:
            status = entry.get("status", "untranslated")
            if not isinstance(status, str):
                status = "untranslated"
            s = status.strip().lower().replace(" ", "_")
            # Accept legacy/uppercase variants coming from parsers/core
            if s in ("untranslated", "not_translated"):
                s = "untranslated"
            elif s in ("inprogress", "in_progress"):
                s = "in_progress"
            elif s in ("translated", "done"):
                s = "translated"
            elif s in ("reviewed", "approved"):
                s = "reviewed"
            return self.STATUS_COLORS.get(s)

        return None

    def set_entries(self, entries: list[dict]):
        """
        Recebe entradas do core e mantém apenas as traduzíveis na tabela.
        """
        self.beginResetModel()

        self.all_entries = entries or []
        self.entries = [
            e for e in self.all_entries
            if e.get("is_translatable", True)
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

        vid = self.entries[visible_row].get("entry_id")
        if vid:
            for i, e in enumerate(self.all_entries):
                if e.get("entry_id") == vid:
                    return i

        ln = self.entries[visible_row].get("line_number")
        orig = self.entries[visible_row].get("original")
        for i, e in enumerate(self.all_entries):
            if e.get("line_number") == ln and e.get("original") == orig:
                return i

        return None