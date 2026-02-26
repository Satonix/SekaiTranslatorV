from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtGui import QTextOption, QFont, QKeyEvent, QTextCursor, QTextBlockFormat
from PySide6.QtCore import Qt, Signal

from models.edit_session import EditSession


class TranslationEditor(QPlainTextEdit):
    """
    Editor de tradução fiel ao SekaiTranslator antigo.

    Regras:
    - 1 linha = 1 entry
    - Enter = commit
    - Shift+Enter = navegar
    - Ctrl+Enter = commit + navegar
    - Nunca cria/remove linhas
    """

    commitRequested = Signal()
    jumpNextRequested = Signal()
    jumpPrevRequested = Signal()

    undoRequested = Signal()
    redoRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setUndoRedoEnabled(True)
        self.setWordWrapMode(QTextOption.NoWrap)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)

        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(10)
        self.setFont(font)

        self._session: EditSession | None = None
        self._rows: list[int] = []

        # Guard against recursive normalization when we need to restore the
        # invariant "1 line = 1 entry" (e.g. Ctrl+A + Backspace collapses blocks).
        self._internal_change: bool = False


        # True while EditorPanel is loading a new session; prevents marking rows as IN_PROGRESS.
        self._loading_session: bool = False
        self.textChanged.connect(self._on_text_changed)

    def bind_edit_session(self, session: EditSession):
        self._session = session

    def set_rows(self, rows: list[int]):
        self._rows = rows or []
    def load_from_session(self) -> None:
        # While we are loading a new session, ignore textChanged signals so
        # selecting a row does not mark it as IN_PROGRESS.
        self._loading_session = True
        try:
            if not self._session or not self._session.is_active():
                self.blockSignals(True)
                try:
                    self.setPlainText("")
                finally:
                    self.blockSignals(False)
                return

            # Keep the invariant "1 line = 1 entry".
            def _norm_line(v: object) -> str:
                s = v if isinstance(v, str) else ""
                s = s.replace("\r", "")
                s = s.replace("\n", "")
                return s

            lines = [_norm_line(e.get("translation", "")) for e in self._session.entries]

            self.blockSignals(True)
            try:
                self.setPlainText("\n".join(lines))
            finally:
                self.blockSignals(False)

            # Visual spacing (does not create blank lines)
            try:
                self._apply_block_padding(px=6)
            except Exception:
                pass

            self.verticalScrollBar().setValue(0)
        finally:
            self._loading_session = False

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

    def keyPressEvent(self, event: QKeyEvent):
        if not self._session or not self._session.is_active():
            super().keyPressEvent(event)
            return

        key = event.key()
        mods = event.modifiers()

        is_enter = key in (Qt.Key_Return, Qt.Key_Enter)
        ctrl = bool(mods & Qt.ControlModifier)
        shift = bool(mods & Qt.ShiftModifier)
        alt = bool(mods & Qt.AltModifier)
        meta = bool(mods & Qt.MetaModifier)

        if ctrl and not alt and not meta and key == Qt.Key_Z:
            if shift:
                self.redoRequested.emit()
            else:
                self.undoRequested.emit()
            event.accept()
            return

        if is_enter and not ctrl and not shift and not alt and not meta:
            self.commitRequested.emit()
            event.accept()
            return

        if is_enter and ctrl:
            self.commitRequested.emit()
            self.jumpNextRequested.emit()
            event.accept()
            return

        if is_enter and shift:
            self.jumpNextRequested.emit()
            event.accept()
            return

        if key == Qt.Key_Backspace:
            cursor = self.textCursor()
            if cursor.positionInBlock() == 0 and cursor.block().text() == "":
                event.accept()
                return

        super().keyPressEvent(event)

    def insertFromMimeData(self, source):
        """
        Cola texto respeitando 1 linha = 1 entry.
        Distribui múltiplas linhas sobre a posição atual (sem criar novas linhas).
        """
        if not self._session or not self._session.is_active():
            super().insertFromMimeData(source)
            return

        if not source.hasText():
            return

        text = source.text().replace("\r", "")
        lines = text.split("\n")

        cursor = self.textCursor()
        start_block = cursor.blockNumber()

        doc = self.document()
        max_blocks = doc.blockCount()

        self.blockSignals(True)
        try:
            for i, line in enumerate(lines):
                target_block = start_block + i
                if target_block >= max_blocks:
                    break

                block = doc.findBlockByNumber(target_block)
                if not block.isValid():
                    break

                block_cursor = QTextCursor(block)
                block_cursor.select(QTextCursor.LineUnderCursor)
                block_cursor.removeSelectedText()
                block_cursor.insertText(line)
        finally:
            self.blockSignals(False)

        self._on_text_changed()

    def _on_text_changed(self):
        if self._internal_change or self._loading_session:
            return

        if not self._session or not self._session.is_active():
            return

        doc = self.document()
        lines: list[str] = []

        block = doc.firstBlock()
        while block.isValid():
            lines.append(block.text())
            block = block.next()

        # Enforce: exactly N blocks (one per selected entry).
        # Deleting across multiple lines can remove newline separators and collapse
        # the document into fewer blocks, which makes the gutter shrink and leaves
        # stale translations in non-first entries.
        n = len(self._session.entries)
        if n > 0 and len(lines) != n:
            normalized = (lines[:n] + [""] * max(0, n - len(lines)))[:n]

            # Preserve cursor as best-effort.
            cur = self.textCursor()
            cur_block = max(0, min(cur.blockNumber(), n - 1))
            cur_pos = max(0, cur.positionInBlock())

            self._internal_change = True
            self.blockSignals(True)
            try:
                self.setPlainText("\n".join(normalized))
                b = self.document().findBlockByNumber(cur_block)
                if b.isValid():
                    c2 = QTextCursor(b)
                    c2.setPosition(b.position() + min(cur_pos, len(b.text())))
                    self.setTextCursor(c2)
            finally:
                self.blockSignals(False)
                self._internal_change = False

            self._session.on_text_edited(normalized)
            return

        self._session.on_text_edited(lines)

    def get_meta_for_block(self, block_number: int):
        """
        Retorna (row_global, speaker) para o gutter.
        """
        if not self._session or not self._session.is_active():
            return None, ""

        if block_number < 0 or block_number >= len(self._session.rows):
            return None, ""

        row = self._session.rows[block_number]
        entry = self._session.entries[block_number]
        speaker = entry.get("speaker") or ""
        return row, speaker
