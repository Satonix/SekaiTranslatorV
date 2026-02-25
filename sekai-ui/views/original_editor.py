from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtGui import QTextOption, QFont, QTextCursor


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

        def _norm_line(v: object) -> str:
            s = v if isinstance(v, str) else ""
            s = s.replace("\r", "")
            # Never allow embedded newlines inside a single entry.
            s = s.replace("\n", "")
            return s

        text = "\n".join(_norm_line(e.get("original", "")) for e in self._entries)
        self.setPlainText(text)

        # Small spacing between blocks (reads like padding, not blank lines)
        try:
            self._apply_block_padding(px=6)
        except Exception:
            pass
        self.verticalScrollBar().setValue(0)

    def _apply_block_padding(self, *, px: int = 6) -> None:
        doc = self.document()
        cursor = QTextCursor(doc)
        cursor.beginEditBlock()
        try:
            block = doc.firstBlock()
            while block.isValid():
                c = QTextCursor(block)
                fmt = block.blockFormat()
                fmt.setTopMargin(0)
                fmt.setBottomMargin(float(px))
                c.setBlockFormat(fmt)
                block = block.next()
        finally:
            cursor.endEditBlock()

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
