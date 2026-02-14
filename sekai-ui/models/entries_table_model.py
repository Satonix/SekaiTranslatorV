from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex

COLUMNS = ["#", "Personagem", "Original", "Status"]

class EntriesTableModel(QAbstractTableModel):
    def __init__(self, entries: list[dict]):
        super().__init__()
        self.entries = entries

    def rowCount(self, parent=QModelIndex()):
        return len(self.entries)

    def columnCount(self, parent=QModelIndex()):
        return len(COLUMNS)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        entry = self.entries[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                return entry["entry_id"]
            if col == 1:
                return entry.get("speaker") or ""
            if col == 2:
                return entry["original"]
            if col == 3:
                return entry["status"]

        if role == Qt.UserRole:
            return entry

        return None

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return COLUMNS[section]
        return None

    def refresh_row(self, row: int):
        top = self.index(row, 0)
        bottom = self.index(row, self.columnCount() - 1)
        self.dataChanged.emit(top, bottom)
