from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtGui import QTextOption, QFont


class OriginalEditor(QPlainTextEdit):
    """
    Editor do texto original (somente leitura).
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setReadOnly(True)
        self.setUndoRedoEnabled(False)
        self.setWordWrapMode(QTextOption.NoWrap)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setCursorWidth(0)

        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(10)
        self.setFont(font)

        self._entries: list[dict] = []
        self._rows: list[int] = []

    def set_entries(self, entries: list[dict], rows: list[int]):
        self._entries = entries or []
        self._rows = rows or []

        if not self._entries:
            self.setPlainText("")
            return

        text = "\n".join(e.get("original", "") for e in self._entries)
        self.setPlainText(text)
        self.verticalScrollBar().setValue(0)

    def get_entry_for_block(self, block_number: int):
        if 0 <= block_number < len(self._entries):
            return self._entries[block_number]
        return None

    def get_global_row_for_block(self, block_number: int):
        """
        🔑 Número REAL da tabela para o gutter.
        """
        if 0 <= block_number < len(self._rows):
            return self._rows[block_number]
        return None


    def get_meta_for_block(self, block_number: int):
        if block_number < 0 or block_number >= len(self._rows):
            return None, ""

        row = self._rows[block_number]
        entry = self._entries[block_number]

        speaker = entry.get("speaker") or ""
        return row, speaker
