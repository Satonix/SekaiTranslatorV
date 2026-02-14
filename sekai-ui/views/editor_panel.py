from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QSplitter,
)

from models.edit_session import EditSession
from views.editor_with_gutter import EditorWithGutter
from views.original_editor import OriginalEditor
from views.translation_editor import TranslationEditor
from models.undo_stack import UndoAction, UndoItem


class EditorPanel(QWidget):
    """
    EditorPanel fiel ao SekaiTranslator antigo.

    RESPONSABILIDADES:
    - Controlar Original + Tradução
    - Gerenciar EditSession
    - Commitar traduções
    - Navegação entre entries
    - Delegar mudança de seleção para o FileTab

    Nota importante:
    - Undo/Redo NÃO pertence ao EditorPanel. O dono do estado global é o FileTab.
      O EditorPanel apenas pede para o FileTab registrar snapshots e aplicar undo.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._file_tab = None
        self._session = EditSession()
        self._entries: list[dict] = []
        self._rows: list[int] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)

        # ================= ORIGINAL =================
        original_container = QWidget()
        original_layout = QVBoxLayout(original_container)
        original_layout.setContentsMargins(0, 0, 0, 0)
        original_layout.setSpacing(2)

        original_label = QLabel("Original")
        original_label.setFixedHeight(18)
        original_label.setStyleSheet("font-weight: bold; color: #cbd5e1;")

        self.original_editor = OriginalEditor(self)
        self.original_with_gutter = EditorWithGutter(self.original_editor)

        original_layout.addWidget(original_label)
        original_layout.addWidget(self.original_with_gutter)

        # ================= TRADUÇÃO =================
        translation_container = QWidget()
        translation_layout = QVBoxLayout(translation_container)
        translation_layout.setContentsMargins(0, 0, 0, 0)
        translation_layout.setSpacing(2)

        translation_label = QLabel("Tradução")
        translation_label.setFixedHeight(18)
        translation_label.setStyleSheet("font-weight: bold; color: #cbd5e1;")

        self.translation_editor = TranslationEditor(self)
        self.translation_with_gutter = EditorWithGutter(self.translation_editor)

        translation_layout.addWidget(translation_label)
        translation_layout.addWidget(self.translation_with_gutter)

        splitter.addWidget(original_container)
        splitter.addWidget(translation_container)
        splitter.setSizes([420, 520])

        layout.addWidget(splitter)

        # ================= INPUT SIGNALS =================
        self.translation_editor.commitRequested.connect(self._on_commit_requested)
        self.translation_editor.jumpNextRequested.connect(self._on_jump_next)
        self.translation_editor.jumpPrevRequested.connect(self._on_jump_prev)

        # Undo/Redo delegados ao FileTab (se existirem esses signals no TranslationEditor)
        if hasattr(self.translation_editor, "undoRequested"):
            self.translation_editor.undoRequested.connect(self._on_undo_requested)
        if hasattr(self.translation_editor, "redoRequested"):
            self.translation_editor.redoRequested.connect(self._on_redo_requested)
            
        self.translation_editor.textChanged.connect(self._on_translation_text_changed)


    def bind_file_tab(self, file_tab):
        self._file_tab = file_tab

    def focus_translation(self) -> None:
        """Foca o editor de tradução (usado por double-click na tabela)."""
        try:
            self.translation_editor.setFocus()
        except Exception:
            pass

    def start_edit_session(self, entries: list[dict], rows: list[int]):
        self._session = EditSession()
        self._session.start(entries, rows)

        self._entries = entries
        self._rows = rows

        self.original_editor.set_entries(entries, rows)

        te = self.translation_editor
        te.bind_edit_session(self._session)
        te.set_rows(rows)
        te._loading_session = True
        try:
            te.load_from_session()
        finally:
            te._loading_session = False


        # força repaint total do gutter
        te.update()
        te.viewport().update()

        if hasattr(self.translation_with_gutter, "gutter"):
            self.translation_with_gutter.gutter.update_width()
            self.translation_with_gutter.gutter.update()

    def clear(self):
        self._session.clear()
        self._entries = []
        self._rows = []
        self.original_editor.setPlainText("")
        self.translation_editor.setPlainText("")

    # =================================================
    # Commit (Enter)
    # =================================================
    def _on_commit_requested(self):
        if not self._session or not self._session.is_active():
            return
        if not self._file_tab:
            return

        # Snapshot "antes" (somente do que está selecionado nesta sessão)
        # O FileTab é quem sabe como snapshotar campos relevantes.
        session_rows = list(self._session.rows or [])
        before_all = self._file_tab.snapshot_rows(session_rows)

        # mapeia row -> snapshot (para montar antes_snap exatamente na ordem de changed_rows)
        before_map: dict[int, dict] = {}
        for i, r in enumerate(session_rows):
            if i < len(before_all):
                before_map[r] = before_all[i]

        changed_rows = self._session.commit()  # retorna rows globais alteradas (list[int])

        # Se nada mudou, ainda assim avança como no Sekai antigo
        if not changed_rows:
            self._file_tab.request_next_entry()
            return

        # monta before_snap alinhado com changed_rows (contrato do FileTab.apply_commit_with_undo)
        before_snap = [before_map.get(r, {}) for r in changed_rows]

        # registra undo + refresh de linhas (centralizado no FileTab)
        self._file_tab.apply_commit_with_undo(changed_rows, before_snap=before_snap)

        # comportamento do Sekai antigo
        self._file_tab.request_next_entry()

    # =================================================
    # Navegação local (Shift+Enter, etc.)
    # =================================================
    def _on_jump_next(self):
        self._jump(+1)

    def _on_jump_prev(self):
        self._jump(-1)

    def _jump(self, delta: int):
        if len(self._entries) <= 1:
            return

        cursor = self.translation_editor.textCursor()
        block = cursor.block()

        target = block.next() if delta > 0 else block.previous()
        if not target.isValid():
            return

        col = cursor.positionInBlock()
        pos = min(col, target.length() - 1)

        new_cursor = QTextCursor(target)
        new_cursor.setPosition(target.position() + pos)
        self.translation_editor.setTextCursor(new_cursor)

    # =================================================
    # Undo/Redo (delegado)
    # =================================================
    def _on_undo_requested(self):
        if self._file_tab:
            self._file_tab.undo()

    def _on_redo_requested(self):
        if self._file_tab:
            self._file_tab.redo()
            
    def _on_translation_text_changed(self):
        if not self._file_tab:
            return
        if not self._session or not self._session.is_active():
            return
        if getattr(self.translation_editor, "_loading_session", False):
            return

        self._file_tab.set_dirty(True)

