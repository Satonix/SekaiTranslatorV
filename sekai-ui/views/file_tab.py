from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QSplitter,
    QAbstractItemView,
)

from views.translation_table_view import TranslationTableView
from models.translation_table_model import TranslationTableModel
from views.editor_panel import EditorPanel

from models.undo_stack import UndoStack, UndoAction, UndoItem
from models import project_state_store


class FileTab(QWidget):
    """
    Aba de arquivo.
    Orquestra tabela ↔ editor.

    Responsabilidades extras:
    - persistir estado local do projeto (sem tocar no arquivo original)
    - exportar via parser.rebuild (UI-side)
    - undo/redo de translation/status (UI-side, consistente com EditorPanel)
    """

    dirtyChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.file_path: str | None = None
        self.parser = None
        self.parse_ctx = None


        self._entries: list[dict] = []
        self._pending_select_entry_id: str | None = None
        self._pending_select_source_row: int | None = None

        self.is_dirty: bool = False
        self._undo = UndoStack()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        splitter = QSplitter(Qt.Vertical)
        layout.addWidget(splitter)

        self.table = TranslationTableView(self)
        self.model = TranslationTableModel([])
        self.table.setModel(self.model)
        try:
            self.table.doubleClicked.connect(self._on_table_double_clicked)
        except Exception:
            pass
        splitter.addWidget(self.table)

        self.editor = EditorPanel(self)
        self.editor.bind_file_tab(self)
        splitter.addWidget(self.editor)

        splitter.setSizes([420, 480])

        self._selection_connected = False

        try:
            self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
            self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        except Exception:
            pass

    def set_dirty(self, dirty: bool) -> None:
        dirty = bool(dirty)
        if self.is_dirty == dirty:
            return
        self.is_dirty = dirty
        self.dirtyChanged.emit(self.is_dirty)

    def _visible_rows(self) -> list[int]:
        sm = self.table.selectionModel()
        if not sm:
            return []
        return [i.row() for i in sm.selectedRows()]

    def _source_row_from_visible_row(self, visible_row: int) -> int | None:
        if hasattr(self.model, "visible_row_to_source_row"):
            return self.model.visible_row_to_source_row(visible_row)
        return None

    def _visible_row_from_source_row(self, source_row: int) -> int | None:
        """Map SOURCE row (self._entries) -> visible row (self.model.entries).

        The table only shows translatable entries (model.entries). A source row
        may point to a non-visible entry (e.g. non-translatable/header rows).
        In that case, we try:
        1) direct dict identity lookup
        2) entry_id lookup
        3) nearest visible row (forward, then backward)
        """
        if not (0 <= source_row < len(self._entries)):
            return None

        e = self._entries[source_row]

        try:
            return self.model.entries.index(e)
        except Exception:
            pass

        try:
            eid = e.get("entry_id") if isinstance(e, dict) else None
            if eid:
                eid = str(eid)
                for vr, ve in enumerate(self.model.entries or []):
                    if isinstance(ve, dict) and str(ve.get("entry_id") or "") == eid:
                        return vr
        except Exception:
            pass

        try:
            visible_set = set(id(x) for x in (self.model.entries or []))
            for sr in range(source_row + 1, len(self._entries)):
                ee = self._entries[sr]
                if id(ee) in visible_set:
                    try:
                        return self.model.entries.index(ee)
                    except Exception:
                        break
            for sr in range(source_row - 1, -1, -1):
                ee = self._entries[sr]
                if id(ee) in visible_set:
                    try:
                        return self.model.entries.index(ee)
                    except Exception:
                        break
        except Exception:
            pass

        return None

    def set_entries(self, entries: list[dict]):
        self._entries = entries or []

        self.model.set_entries(self._entries)

        sm = self.table.selectionModel()
        if sm and not self._selection_connected:
            sm.selectionChanged.connect(self._on_selection_changed)
            self._selection_connected = True

        self._undo.clear()
        self.set_dirty(False)

        if self.model.rowCount() > 0:
            self.table.selectRow(0)

        if self.model.rowCount() > 0 and (self._pending_select_entry_id is not None or self._pending_select_source_row is not None):
            eid = self._pending_select_entry_id
            sr = self._pending_select_source_row
            self._pending_select_entry_id = None
            self._pending_select_source_row = None
            try:
                if eid:
                    self.select_entry(eid, fallback_row=sr)
                elif isinstance(sr, int):
                    self.select_source_row(sr)
            except Exception:
                pass


    def _on_selection_changed(self, *_):
        rows_visible = self._visible_rows()
        if not rows_visible:
            self.editor.clear()
            return

        rows_source: list[int] = []
        selected_entries: list[dict] = []

        for vr in rows_visible:
            sr = self._source_row_from_visible_row(vr)
            if sr is None:
                continue
            if 0 <= sr < len(self._entries):
                rows_source.append(sr)
                selected_entries.append(self._entries[sr])

        if not rows_source:
            self.editor.clear()
            return

        self.editor.start_edit_session(selected_entries, rows_source)

    def request_next_entry(self):
        """
        Seleciona a próxima linha da tabela (VISÍVEL).
        FIEL AO SEKAI TRANSLATOR ANTIGO.
        """
        sm = self.table.selectionModel()
        if not sm:
            return

        rows = sorted(idx.row() for idx in sm.selectedRows())
        if not rows:
            return

        next_row = rows[-1] + 1
        if next_row >= self.model.rowCount():
            return

        self.table.clearSelection()
        self.table.selectRow(next_row)
        self.table.scrollTo(
            self.model.index(next_row, 0),
            QAbstractItemView.PositionAtCenter,
        )

    def select_source_row(self, source_row: int) -> None:
        """Select a row by SOURCE index (index in self._entries).

        This is used by global search / QA to jump directly to a line.
        """
        try:
            sr = int(source_row)
        except Exception:
            return

        if not self._entries:
            self._pending_select_source_row = sr
            self._pending_select_entry_id = None
            return


        if not (0 <= sr < len(self._entries)):
            return

        vr = self._visible_row_from_source_row(sr)
        if vr is None:
            try:
                vr = self.model.entries.index(self._entries[sr])
            except Exception:
                vr = None

        if vr is None:
            return

        try:
            self.table.clearSelection()
            self.table.selectRow(vr)
            self.table.scrollTo(
                self.model.index(vr, 0),
                QAbstractItemView.PositionAtCenter,
            )
        except Exception:
            pass

    def select_entry(self, entry_id: str | None, fallback_row: int | None = None) -> None:
        """Select an entry using the stable ``entry_id``.

        Search results coming from project-wide scans may be based on a
        freshly-parsed entries list, so using ``source_row`` alone can be
        brittle when parsers include non-translatable rows or their ordering
        changes. ``entry_id`` is the stable key.
        """
        if not self._entries:
            self._pending_select_entry_id = str(entry_id or "") or None
            self._pending_select_source_row = int(fallback_row) if isinstance(fallback_row, int) else None
            return

        if isinstance(entry_id, str) and entry_id:
            for i, e in enumerate(self._entries or []):
                if isinstance(e, dict) and str(e.get("entry_id") or "") == entry_id:
                    self.select_source_row(i)
                    return

        if isinstance(fallback_row, int):
            try:
                self.select_source_row(int(fallback_row))
            except Exception:
                return

    def undo(self) -> None:
        act = self._undo.pop_undo()
        if not act:
            return

        for it in act.items:
            if 0 <= it.row < len(self._entries):
                e = self._entries[it.row]
                e[it.field] = it.old_value

                if it.field == "translation":
                    e["_last_committed_translation"] = it.old_value if it.old_value is not None else ""
                elif it.field == "status":
                    e["_last_committed_status"] = it.old_value if it.old_value is not None else "untranslated"

                vr = self._visible_row_from_source_row(it.row)
                if vr is not None:
                    self.model.refresh_row(vr)

        self.set_dirty(True)
        self._refresh_editor_from_selection()

    def redo(self) -> None:
        act = self._undo.pop_redo()
        if not act:
            return

        for it in act.items:
            if 0 <= it.row < len(self._entries):
                e = self._entries[it.row]
                e[it.field] = it.new_value

                if it.field == "translation":
                    e["_last_committed_translation"] = it.new_value if it.new_value is not None else ""
                elif it.field == "status":
                    e["_last_committed_status"] = it.new_value if it.new_value is not None else "untranslated"

                vr = self._visible_row_from_source_row(it.row)
                if vr is not None:
                    self.model.refresh_row(vr)

        self.set_dirty(True)
        self._refresh_editor_from_selection()

    def _refresh_editor_from_selection(self) -> None:
        self._on_selection_changed()

    def save_project_state(self, project: dict) -> None:
        if not self.file_path:
            return
        project_state_store.save_file_state(project, self.file_path, self._entries)
        self.set_dirty(False)

    def load_project_state_if_exists(self, project: dict) -> None:
        if not self.file_path:
            return

        st = project_state_store.load_file_state(project, self.file_path)
        if not st:
            return

        saved = st.entries

        by_id: dict[str, dict] = {}
        for e in saved:
            eid = e.get("entry_id")
            if isinstance(eid, str):
                by_id[eid] = e

        if by_id:
            for cur in self._entries:
                eid = cur.get("entry_id")
                if isinstance(eid, str) and eid in by_id:
                    s = by_id[eid]
                    if "translation" in s:
                        cur["translation"] = s.get("translation") or ""
                    if "status" in s:
                        cur["status"] = s.get("status") or "untranslated"
        elif len(saved) == len(self._entries):
            for cur, s in zip(self._entries, saved):
                cur["translation"] = s.get("translation") or ""
                cur["status"] = s.get("status") or "untranslated"

        self.model.set_entries(self._entries)
        self._undo.clear()
        self.set_dirty(False)

        if self.model.rowCount() > 0:
            self.table.selectRow(0)

    @staticmethod
    def compute_export_path(project: dict, src_path: str) -> str:
        root = (project.get("root_path") or "").strip()
        if not root:
            root = os.path.dirname(src_path)

        try:
            rel = os.path.relpath(src_path, root)
        except Exception:
            rel = os.path.basename(src_path)

        rel = rel.replace("\\", os.sep)
        return os.path.join(root, "exports", rel)

    def export_to_disk(self, project: dict, *, parser, ctx) -> str:
        """
        Rebuild via parser plugin e grava em compute_export_path (NUNCA no original).

        Regras:
        - Se parser.rebuild() retornar bytes/bytearray -> salva em modo binário (wb)
        - Se retornar str -> salva em modo texto (w) usando project["encoding"]
        """
        if not self.file_path:
            raise RuntimeError("file_path não definido no FileTab")

        if parser is None:
            raise RuntimeError("parser não fornecido para export_to_disk()")

        if not hasattr(parser, "rebuild") or not callable(getattr(parser, "rebuild")):
            raise RuntimeError("parser inválido: não implementa rebuild(ctx, entries)")

        out_data = parser.rebuild(ctx, self._entries)

        out_path = self.compute_export_path(project, self.file_path)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        if isinstance(out_data, (bytes, bytearray)):
            with open(out_path, "wb") as f:
                f.write(bytes(out_data))
        else:
            if not isinstance(out_data, str):
                raise RuntimeError("parser.rebuild() deve retornar str ou bytes/bytearray")
            encoding = (project.get("encoding") or "utf-8").strip() or "utf-8"
            try:
                "".encode(encoding)
            except Exception:
                encoding = "utf-8"
            with open(out_path, "w", encoding=encoding, errors="replace") as f:
                f.write(out_data)

        return out_path


    def snapshot_rows(self, rows: list[int]) -> list[dict]:
        snap: list[dict] = []
        for r in rows:
            if 0 <= r < len(self._entries):
                e = self._entries[r]
                snap.append(
                    {
                        "translation": e.get("_last_committed_translation", e.get("translation")),
                        "status": e.get("_last_committed_status", e.get("status")),
                    }
                )
        return snap

    
    def _current_user_id(self) -> str:
        import os
        return (os.environ.get("SEKAI_USER_ID")
                or os.environ.get("USERNAME")
                or os.environ.get("USER")
                or "unknown")

    def _now_iso(self) -> str:
        from datetime import datetime, timezone
        dt = datetime.now().astimezone()
        return dt.isoformat(timespec="seconds")

    def _bump_entry_revision(self, e: dict, *, field: str) -> None:
        """
        Bumps per-entry revision and stamps audit fields when translation/status changes.
        Stored in entry dict and persisted via project_state_store.
        """
        rev = e.get("_rev")
        try:
            rev_i = int(rev)
        except Exception:
            rev_i = 0
        e["_rev"] = rev_i + 1
        e["_updated_at"] = self._now_iso()
        e["_updated_by"] = self._current_user_id()
        e["_updated_field"] = field

    def apply_commit_with_undo(self, changed_rows: list[int], *, before_snap: list[dict]) -> None:
        if not changed_rows:
            return

        after_snap = self.snapshot_rows(changed_rows)
        self.record_undo_for_rows(changed_rows, before=before_snap, after=after_snap)

        before_map = {changed_rows[i]: (before_snap[i] if i < len(before_snap) else {}) for i in range(len(changed_rows))}
        after_map = {changed_rows[i]: (after_snap[i] if i < len(after_snap) else {}) for i in range(len(changed_rows))}
        for r in changed_rows:
            if 0 <= r < len(self._entries):
                b = before_map.get(r, {}) or {}
                a = after_map.get(r, {}) or {}
                e = self._entries[r]
                if b.get('translation') != a.get('translation'):
                    self._bump_entry_revision(e, field='translation')
                if b.get('status') != a.get('status'):
                    self._bump_entry_revision(e, field='status')

        for r in changed_rows:
            vr = self._visible_row_from_source_row(r)
            if vr is not None:
                self.model.refresh_row(vr)

        self.set_dirty(True)

    def record_undo_for_rows(self, rows: list[int], *, before: list[dict], after: list[dict]) -> None:
        if not rows:
            return

        if not hasattr(self, "_undo") or self._undo is None:
            return

        items: list[UndoItem] = []

        for i, row in enumerate(rows):
            if i >= len(before) or i >= len(after):
                continue

            b = before[i] or {}
            a = after[i] or {}

            for field in ("translation", "status"):
                old_v = b.get(field)
                new_v = a.get(field)
                if old_v != new_v:
                    items.append(
                        UndoItem(
                            row=row,
                            field=field,
                            old_value=old_v,
                            new_value=new_v,
                        )
                    )

        if not items:
            return

        self._undo.push(UndoAction(items=items))
