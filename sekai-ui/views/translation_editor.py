from PySide6.QtWidgets import QPlainTextEdit
from PySide6.QtGui import QTextOption, QFont, QKeyEvent, QTextCursor
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

    # (Se você usa no EditorPanel)
    undoRequested = Signal()
    redoRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # Visual
        self.setUndoRedoEnabled(True)
        self.setWordWrapMode(QTextOption.NoWrap)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)

        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(10)
        self.setFont(font)

        # Estado
        self._session: EditSession | None = None
        self._rows: list[int] = []

        self.textChanged.connect(self._on_text_changed)

    # Bind
    def bind_edit_session(self, session: EditSession):
        self._session = session

    def set_rows(self, rows: list[int]):
        self._rows = rows or []

    # Load
    def load_from_session(self):
        if not self._session or not self._session.is_active():
            self.setPlainText("")
            return

        lines = [e.get("translation", "") for e in self._session.entries]

        self.blockSignals(True)
        self.setPlainText("\n".join(lines))
        self.blockSignals(False)

        self.verticalScrollBar().setValue(0)

    # Input
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

        # Ctrl+Z / Ctrl+Shift+Z (se você estiver usando esses sinais no EditorPanel)
        if ctrl and not alt and not meta and key == Qt.Key_Z:
            if shift:
                self.redoRequested.emit()
            else:
                self.undoRequested.emit()
            event.accept()
            return

        if is_enter and not ctrl and not shift and not alt and not meta:
            # ENTER → commit
            self.commitRequested.emit()
            event.accept()
            return

        if is_enter and ctrl:
            # CTRL + ENTER → commit + next
            self.commitRequested.emit()
            self.jumpNextRequested.emit()
            event.accept()
            return

        if is_enter and shift:
            # SHIFT + ENTER → next
            self.jumpNextRequested.emit()
            event.accept()
            return

        # BACKSPACE → não remover linha
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

    # Sync
    def _on_text_changed(self):
        if not self._session or not self._session.is_active():
            return

        doc = self.document()
        lines = []

        block = doc.firstBlock()
        while block.isValid():
            lines.append(block.text())
            block = block.next()

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
