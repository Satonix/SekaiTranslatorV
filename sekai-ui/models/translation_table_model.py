from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex, QSettings
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from themes.theme_manager import ThemeManager


class TranslationTableModel(QAbstractTableModel):
    COLUMNS = ["Linha", "Personagem", "Original", "Tradução"]

    def __init__(self, entries=None, parent=None):
        super().__init__(parent)
        self.all_entries: list[dict] = entries or []
        self.entries: list[dict] = []
        self._visible_to_source_row: list[int] = []
        self._entry_id_to_source_row: dict[str, int] = {}
        self._status_palette_cache_key: tuple[str, str, bool, int] | None = None
        self._status_palette_cache: dict[str, QColor | None] = {}
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

    def _status_palette(self) -> dict[str, QColor | None]:
        app = QApplication.instance()
        try:
            enabled = bool(app.property("sekai_background_enabled")) if app is not None else False
        except Exception:
            enabled = False
        try:
            prop = app.property("sekai_background_overlay") if app is not None else None
            overlay = int(prop) if prop is not None else 140
        except Exception:
            overlay = 140
        if app is None or (app.property("sekai_background_overlay") is None if app is not None else True):
            try:
                settings = QSettings("SekaiTranslatorV", "SekaiTranslatorV")
                enabled = bool(settings.value("ui/background_enabled", enabled, type=bool))
                overlay = int(settings.value("ui/background_overlay", overlay) or overlay)
            except Exception:
                pass
        overlay = max(0, min(220, overlay))
        try:
            theme_id = str(app.property("sekai_theme") or "").strip() if app is not None else ""
        except Exception:
            theme_id = ""
        try:
            theme_signature = str(app.property("sekai_theme_signature") or "").strip() if app is not None else ""
        except Exception:
            theme_signature = ""
        cache_key = (theme_id, theme_signature, enabled, overlay)
        if self._status_palette_cache_key == cache_key and self._status_palette_cache:
            return self._status_palette_cache
        palette = {
            "untranslated": ThemeManager.status_color("untranslated", background_enabled=enabled, overlay=overlay, app=app),
            "in_progress": ThemeManager.status_color("in_progress", background_enabled=enabled, overlay=overlay, app=app),
            "translated": ThemeManager.status_color("translated", background_enabled=enabled, overlay=overlay, app=app),
            "reviewed": ThemeManager.status_color("reviewed", background_enabled=enabled, overlay=overlay, app=app),
        }
        self._status_palette_cache_key = cache_key
        self._status_palette_cache = palette
        return palette

    @staticmethod
    def _normalized_status(value) -> str:
        s = str(value or "untranslated").strip().lower().replace(" ", "_")
        if s in ("untranslated", "not_translated"):
            return "untranslated"
        if s in ("inprogress", "in_progress"):
            return "in_progress"
        if s in ("translated", "done"):
            return "translated"
        if s in ("reviewed", "approved"):
            return "reviewed"
        return "untranslated"

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
            return self._status_palette().get(self._normalized_status(entry.get("status")))

        return None

    def set_entries(self, entries: list[dict]):
        self.beginResetModel()
        self.all_entries = entries or []
        self.entries = []
        self._visible_to_source_row = []
        self._entry_id_to_source_row = {}
        for i, e in enumerate(self.all_entries):
            if not isinstance(e, dict):
                continue
            eid = e.get("entry_id")
            if eid:
                self._entry_id_to_source_row[str(eid)] = i
            if e.get("is_translatable", True):
                self.entries.append(e)
                self._visible_to_source_row.append(i)
        self._status_palette_cache_key = None
        self._status_palette_cache = {}
        self.endResetModel()

    def refresh_row(self, row: int):
        if 0 <= row < self.rowCount():
            left = self.index(row, 0)
            right = self.index(row, self.columnCount() - 1)
            self.dataChanged.emit(left, right)

    def visible_row_to_source_row(self, visible_row: int) -> int | None:
        if not (0 <= visible_row < len(self.entries)):
            return None
        if 0 <= visible_row < len(self._visible_to_source_row):
            return self._visible_to_source_row[visible_row]
        vid = self.entries[visible_row].get("entry_id")
        if vid:
            hit = self._entry_id_to_source_row.get(str(vid))
            if hit is not None:
                return hit
        ln = self.entries[visible_row].get("line_number")
        orig = self.entries[visible_row].get("original")
        for i, e in enumerate(self.all_entries):
            if e.get("line_number") == ln and e.get("original") == orig:
                return i
        return None
