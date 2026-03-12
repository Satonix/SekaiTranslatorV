from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
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

        self.setObjectName("editorPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._pending_refresh_source_rows: set[int] = set()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(33)
        self._refresh_timer.timeout.connect(self._flush_pending_row_refreshes)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        splitter = QSplitter(Qt.Vertical)
        splitter.setObjectName("editorSplitter")
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(10)

        original_container = QWidget()
        original_container.setObjectName("originalSection")
        original_container.setAttribute(Qt.WA_StyledBackground, True)
        original_layout = QVBoxLayout(original_container)
        original_layout.setContentsMargins(0, 0, 0, 0)
        original_layout.setSpacing(4)

        original_label = QLabel("Original")
        original_label.setObjectName("originalSectionLabel")
        original_label.setFixedHeight(22)
        original_label.setProperty("sectionLabel", True)

        self.original_editor = OriginalEditor(self)
        self.original_editor.setObjectName("originalEditor")
        self.original_with_gutter = EditorWithGutter(self.original_editor)
        self.original_with_gutter.setObjectName("originalEditorSurface")

        original_layout.addWidget(original_label)
        original_layout.addWidget(self.original_with_gutter)

        translation_container = QWidget()
        translation_container.setObjectName("translationSection")
        translation_container.setAttribute(Qt.WA_StyledBackground, True)
        translation_layout = QVBoxLayout(translation_container)
        translation_layout.setContentsMargins(0, 0, 0, 0)
        translation_layout.setSpacing(4)

        translation_label = QLabel("Tradução")
        translation_label.setObjectName("translationSectionLabel")
        translation_label.setFixedHeight(22)
        translation_label.setProperty("sectionLabel", True)

        self.translation_editor = TranslationEditor(self)
        self.translation_editor.setObjectName("translationEditor")
        self.translation_with_gutter = EditorWithGutter(self.translation_editor)
        self.translation_with_gutter.setObjectName("translationEditorSurface")

        translation_layout.addWidget(translation_label)
        translation_layout.addWidget(self.translation_with_gutter)

        splitter.addWidget(original_container)
        splitter.addWidget(translation_container)
        splitter.setSizes([420, 520])

        layout.addWidget(splitter)

        self.translation_editor.commitRequested.connect(self._on_commit_requested)
        self.translation_editor.jumpNextRequested.connect(self._on_jump_next)
        self.translation_editor.jumpPrevRequested.connect(self._on_jump_prev)

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
        self._refresh_timer.stop()
        self._pending_refresh_source_rows.clear()
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


        te.update()
        te.viewport().update()

        if hasattr(self.translation_with_gutter, "gutter"):
            self.translation_with_gutter.gutter.update_width()
            self.translation_with_gutter.gutter.update()

    def clear(self):
        self._refresh_timer.stop()
        self._pending_refresh_source_rows.clear()
        self._session.clear()
        self._entries = []
        self._rows = []
        self.original_editor.setPlainText("")
        self.translation_editor.setPlainText("")

    def _on_commit_requested(self):
        if not self._session or not self._session.is_active():
            return
        if not self._file_tab:
            return

        session_rows = list(self._session.rows or [])
        before_all = self._file_tab.snapshot_rows(session_rows)

        before_map: dict[int, dict] = {}
        for i, r in enumerate(session_rows):
            if i < len(before_all):
                before_map[r] = before_all[i]

        changed_rows = self._session.commit()

        if not changed_rows:
            self._file_tab.request_next_entry()
            return

        before_snap = [before_map.get(r, {}) for r in changed_rows]

        self._file_tab.apply_commit_with_undo(changed_rows, before_snap=before_snap)

        self._file_tab.request_next_entry()

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
        try:
            self._pending_refresh_source_rows.update(int(sr) for sr in (self._session.rows or []))
            if not self._refresh_timer.isActive():
                self._refresh_timer.start()
        except Exception:
            pass

    def _flush_pending_row_refreshes(self):
        if not self._file_tab or not self._pending_refresh_source_rows:
            return
        rows = sorted(self._pending_refresh_source_rows)
        self._pending_refresh_source_rows.clear()
        try:
            for sr in rows:
                vr = self._file_tab._visible_row_from_source_row(sr)
                if vr is not None:
                    self._file_tab.model.refresh_row(vr)
        except Exception:
            pass
