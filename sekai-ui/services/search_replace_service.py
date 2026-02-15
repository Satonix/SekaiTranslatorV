from __future__ import annotations

import os
import re
import copy
from typing import Any

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from parsers.autodetect import select_parser
from parsers.base import ParseContext
from parsers.manager import get_parser_manager
from models import project_state_store

from views.dialogs.search_dialog import SearchResult


class SearchReplaceService:
    """
    Serviço de busca/substituição.
    Mantém o SearchDialog como UI-only e concentra a lógica fora do MainWindow.

    Observação:
    - Este serviço delega atributos desconhecidos para o MainWindow via __getattr__.
      Isso preserva os "princípios" atuais (MainWindow como orquestrador) sem
      duplicar estado/infra.
    """

    def __init__(self, main_window):
        self._mw = main_window

    def __getattr__(self, name: str):
        return getattr(self._mw, name)

    
    def _norm_path(self, p: str) -> str:
        try:
            return os.path.normcase(os.path.abspath(p))
        except Exception:
            return str(p or "")

    def _get_open_tab_for_path(self, path: str):
        """Return (key, tab) for an opened file, matching by normalized absolute path."""
        if not path:
            return None, None
        want = self._norm_path(path)
        try:
            if path in (self._open_files or {}):
                return path, self._open_files.get(path)
            ap = os.path.abspath(path)
            if ap in (self._open_files or {}):
                return ap, self._open_files.get(ap)
        except Exception:
            pass

        try:
            for k, t in (self._open_files or {}).items():
                if not k:
                    continue
                if self._norm_path(k) == want:
                    return k, t
        except Exception:
            pass
        return None, None

    def _search_run(self, query: str, params: dict) -> list[SearchResult]:
        q = (query or "").strip()
        if not q:
            return []

        p = dict(params or {})
        p["query"] = q
        scope = str(p.get("scope") or "file").strip().lower()
        if scope == "project":
            return self._search_in_project(p)
        return self._search_in_current_file(p)

    def _search_open_result(self, res: SearchResult) -> None:
        if not res or not getattr(res, "file_path", None):
            return
        if not self.current_project:
            return

        target_path = os.path.abspath(str(res.file_path))

        _, tab = self._get_open_tab_for_path(target_path)
        if tab is None:
            try:
                idx = self.fs_model.index(target_path)
                if idx.isValid():
                    self._open_file(idx)
            except Exception:
                pass

        _, tab = self._get_open_tab_for_path(target_path)
        if tab is None:
            return

        self.tabs.setCurrentWidget(tab)

        entry_id = str(getattr(res, "entry_id", "") or "").strip()
        try:
            fallback_row = int(res.source_row) if res.source_row is not None else None
        except Exception:
            fallback_row = None

        if entry_id:
            try:
                tab.select_entry(entry_id, fallback_row=fallback_row)
                return
            except Exception:
                pass

        entries = getattr(tab, "_entries", []) or []

        try:
            field = str(getattr(res, "field", "") or "").strip().lower()
            snippet = str(getattr(res, "snippet", "") or "").strip()
            if field in ("original", "translation") and snippet and entries:
                sn = " ".join(snippet.split())
                candidates: list[int] = []
                for i, e in enumerate(entries):
                    if not isinstance(e, dict):
                        continue
                    if field == "translation":
                        txt = str(self._entry_translation_text(e) or "")
                    else:
                        txt = str(e.get("original") or "")
                    t = " ".join(txt.replace("\n", " ").split())
                    if sn and sn in t:
                        candidates.append(i)

                if candidates:
                    if isinstance(fallback_row, int):
                        best = min(candidates, key=lambda i: abs(i - fallback_row))
                    else:
                        best = candidates[0]
                    tab.select_source_row(int(best))
                    return
        except Exception:
            pass

        if isinstance(fallback_row, int) and entries:
            try:
                sr = max(0, min(fallback_row, len(entries) - 1))
                tab.select_source_row(int(sr))
            except Exception:
                pass



    def _as_text(self, v) -> str:
        if isinstance(v, str):
            return v
        if isinstance(v, (list, tuple)):
            return "\n".join(str(x) for x in v if x is not None)
        return ""

    def _get_translation_text(self, entry: dict) -> str:
        tr = entry.get("translation")
        tr_txt = self._as_text(tr).strip()
        if tr_txt:
            return tr_txt

        tr2 = entry.get("_last_committed_translation")
        return self._as_text(tr2).strip()



    def _search_compile(self, params: dict):
        q = str(params.get("query") or "").strip("\n\r\t ")
        if not q:
            return None

        case_sensitive = bool(params.get("case_sensitive"))
        use_regex = bool(params.get("regex"))

        flags = 0
        if not case_sensitive:
            flags |= re.IGNORECASE

        if use_regex:
            try:
                return re.compile(q, flags)
            except re.error as e:
                raise RuntimeError(f"Regex inválido: {e}")

        return re.compile(re.escape(q), flags)

    def _search_entry_matches(self, rx: re.Pattern, entry: dict, *, in_original: bool, in_translation: bool) -> list[str]:
        """Return a list of matched fields: ['original', 'translation'].

        This is used by SearchDialog to show one result per matched field.
        """
        matched: list[str] = []

        if in_original:
            s = entry.get("original")
            s = s if isinstance(s, str) else ""
            if s and rx.search(s):
                matched.append("original")

        if in_translation:
            s = self._entry_translation_text(entry)
            if s and rx.search(s):
                matched.append("translation")

        return matched

    def _search_in_current_file(self, params: dict) -> list[SearchResult]:
        tab = self._current_file_tab()
        if not tab or not tab.file_path:
            return []

        rx = self._search_compile(params)
        if rx is None:
            return []

        in_original = bool(params.get("in_original", True))
        in_translation = bool(params.get("in_translation", True))

        results: list[SearchResult] = []

        for i, e in enumerate(getattr(tab, "_entries", []) or []):
            if not isinstance(e, dict):
                continue

            fields = self._search_entry_matches(rx, e, in_original=in_original, in_translation=in_translation)
            if not fields:
                continue

            for field in fields:
                if field == "translation":
                    snippet_src = self._entry_translation_text(e)
                else:
                    snippet_src = e.get(field)
                snippet = str(snippet_src or "").replace("\n", " ").strip()
                results.append(
                    SearchResult(
                        scope="file",
                        file_path=os.path.abspath(tab.file_path),
                        source_row=i,
                        entry_id=str(e.get("entry_id") or ""),
                        field=field,
                        snippet=snippet,
                    )
                )

        return results

    def _search_in_project(self, params: dict) -> list[SearchResult]:
        if not self.current_project:
            return []

        root = (self.current_project.get("root_path") or "").strip()
        if not root or not os.path.isdir(root):
            return []

        rx = self._search_compile(params)
        if rx is None:
            return []

        in_original = bool(params.get("in_original", True))
        in_translation = bool(params.get("in_translation", True))

        supported = self._supported_extensions()
        encoding = (self.current_project.get("encoding") or "utf-8").strip() or "utf-8"

        results: list[SearchResult] = []

        open_entries_by_path: dict[str, list[dict]] = {}
        try:
            for p, tab in (self._open_files or {}).items():
                ap = os.path.abspath(p)
                ents = getattr(tab, "_entries", None)
                if isinstance(ents, list) and ap:
                    open_entries_by_path[ap] = ents
        except Exception:
            open_entries_by_path = {}

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for base, dirs, files in os.walk(root):
                dirs[:] = [d for d in dirs if d.lower() != "exports"]

                for fn in files:
                    ext = os.path.splitext(fn)[1].lower()
                    if ext and supported and ext not in supported:
                        continue

                    path = os.path.join(base, fn)
                    abs_path = os.path.abspath(path)
                    if not self._is_openable_candidate(path):
                        continue

                    if abs_path in open_entries_by_path:
                        try:
                            entries = open_entries_by_path[abs_path] or []
                            for i, e in enumerate(entries):
                                if not isinstance(e, dict):
                                    continue
                                fields = self._search_entry_matches(
                                    rx,
                                    e,
                                    in_original=in_original,
                                    in_translation=in_translation,
                                )
                                if not fields:
                                    continue
                                for field in fields:
                                    if field == "translation":
                                        snippet_src = self._entry_translation_text(e)
                                    else:
                                        snippet_src = e.get(field) or ""
                                    snippet = str(snippet_src).replace("\n", " ").strip()
                                    results.append(
                                        SearchResult(
                                            scope="project",
                                            file_path=abs_path,
                                            source_row=i,
                                            entry_id=str(e.get("entry_id") or ""),
                                            field=field,
                                            snippet=snippet,
                                        )
                                    )
                        except Exception:
                            pass
                        continue

                    try:
                        with open(path, "r", encoding=encoding, errors="replace") as f:
                            text = f.read()
                    except Exception:
                        continue

                    try:
                        parser = select_parser(self.current_project, path, text)
                        ctx = ParseContext(file_path=path, project=self.current_project, original_text=text)
                        entries = parser.parse(ctx, text)
                    except Exception:
                        continue

                    try:
                        st = project_state_store.load_file_state(self.current_project, path)
                        saved = getattr(st, "entries", None) if st else None
                        if isinstance(saved, list) and saved:
                            by_id: dict[str, dict] = {}
                            by_original: dict[str, list[dict]] = {}

                            for se in saved:
                                if not isinstance(se, dict):
                                    continue
                                se_eid = se.get("entry_id")
                                if se_eid is not None:
                                    by_id[str(se_eid)] = se
                                o = se.get("original")
                                if isinstance(o, str) and o:
                                    by_original.setdefault(o, []).append(se)

                            if by_id:
                                for ce in entries or []:
                                    if not isinstance(ce, dict):
                                        continue
                                    eid = ce.get("entry_id")
                                    key = str(eid) if eid is not None else ""
                                    if key and key in by_id:
                                        se = by_id[key]
                                        if "translation" in se:
                                            ce["translation"] = se.get("translation") or ""
                                        if "status" in se:
                                            ce["status"] = se.get("status") or "untranslated"

                            for ce in entries or []:
                                if not isinstance(ce, dict):
                                    continue
                                if isinstance(ce.get("translation"), str) and (ce.get("translation") or "").strip():
                                    continue
                                o = ce.get("original")
                                if not (isinstance(o, str) and o):
                                    continue
                                candidates = by_original.get(o) or []
                                if len(candidates) != 1:
                                    continue
                                se = candidates[0]
                                if "translation" in se:
                                    ce["translation"] = se.get("translation") or ""
                                if "status" in se:
                                    ce["status"] = se.get("status") or "untranslated"

                            if isinstance(entries, list) and len(saved) == len(entries):
                                for ce, se in zip(entries, saved):
                                    if not (isinstance(ce, dict) and isinstance(se, dict)):
                                        continue
                                    if "translation" in se and not (isinstance(ce.get("translation"), str) and (ce.get("translation") or "").strip()):
                                        ce["translation"] = se.get("translation") or ""
                                    if "status" in se and not isinstance(ce.get("status"), str):
                                        ce["status"] = se.get("status") or "untranslated"
                    except Exception:
                        pass

                    for i, e in enumerate(entries or []):
                        if not isinstance(e, dict):
                            continue

                        matched_fields = self._search_entry_matches(
                            rx,
                            e,
                            in_original=in_original,
                            in_translation=in_translation,
                        )
                        if not matched_fields:
                            continue

                        for field in matched_fields:
                            if field == "translation":
                                snippet_src = self._entry_translation_text(e)
                            else:
                                snippet_src = e.get(field) if field in ("original", "translation") else ""
                            snippet = str(snippet_src or "").replace("\n", " ").strip()

                            results.append(
                                SearchResult(
                                    scope="project",
                                    file_path=os.path.abspath(path),
                                    source_row=i,
                                    entry_id=str(e.get("entry_id") or ""),
                                    field=str(field),
                                    snippet=snippet,
                                )
                            )
        finally:
            QApplication.restoreOverrideCursor()

        return results

    def _entry_translation_text(self, e: dict) -> str:
        """
        Tradução efetiva para busca:
        - preferir translation se existir
        - fallback para _last_committed_translation (caso o commit mova pra lá)
        """
        tr = e.get("translation")
        if isinstance(tr, str) and tr.strip():
            return tr

        tr2 = e.get("_last_committed_translation")
        if isinstance(tr2, str) and tr2.strip():
            return tr2

        return ""


    def _search_replace_one(self, res: SearchResult, query: str, replace_text: str, params: dict) -> bool:
        """Replace only the selected match.

        - Only supports replacing in the 'translation' field (safe for rebuild).
        - For files not currently open, it applies the change to the persisted project state.
        """
        if not res or not res.file_path:
            return False

        if (res.field or "") != "translation":
            return False

        rx = self._search_compile({**(params or {}), "query": query})
        if rx is None:
            return False

        path = os.path.abspath(res.file_path)

        _, tab = self._get_open_tab_for_path(path)
        if tab is not None:
            entries = getattr(tab, "_entries", []) or []
            row = int(res.source_row)
            if not (0 <= row < len(entries)):
                return False

            e = entries[row]
            old_v = self._entry_translation_text(e)
            if not isinstance(old_v, str):
                old_v = ""

            new_v = rx.sub(replace_text, old_v, count=1)
            if new_v == old_v:
                return False

            before = [{"translation": old_v, "status": e.get("status") or "untranslated"}]
            e["translation"] = new_v
            after = [{"translation": new_v, "status": e.get("status") or "untranslated"}]

            tab.record_undo_for_rows([row], before=before, after=after)
            tab.set_dirty(True)

            vr = tab._visible_row_from_source_row(row)
            if vr is not None:
                tab.model.refresh_row(vr)
            tab._refresh_editor_from_selection()
            self._update_tab_title(tab)
            return True

        if not self.current_project:
            return False

        try:
            root = (self.current_project.get("root_path") or "").strip()
            encoding = (self.current_project.get("encoding") or "utf-8").strip() or "utf-8"
            with open(path, "r", encoding=encoding, errors="replace") as f:
                text = f.read()
            parser = select_parser(self.current_project, path, text)
            ctx = ParseContext(file_path=path, project=self.current_project, original_text=text)
            entries = parser.parse(ctx, text)

            st = project_state_store.load_file_state(self.current_project, path)
            if st and getattr(st, "entries", None):
                by_id: dict[str, dict] = {}
                try:
                    for se in st.entries:
                        if not isinstance(se, dict):
                            continue
                        se_eid = se.get("entry_id")
                        if se_eid is None:
                            continue
                        by_id[str(se_eid)] = se
                except Exception:
                    by_id = {}

                if by_id:
                    for ce in entries:
                        if not isinstance(ce, dict):
                            continue
                        eid = ce.get("entry_id")
                        key = str(eid) if eid is not None else ""
                        if not key or key not in by_id:
                            continue
                        se = by_id[key]
                        if "translation" in se:
                            ce["translation"] = se.get("translation") or ""
                        if "status" in se:
                            ce["status"] = se.get("status") or "untranslated"

            row = int(res.source_row)
            if not (0 <= row < len(entries)):
                return False

            e = entries[row]
            old_v = self._entry_translation_text(e)
            if not isinstance(old_v, str):
                old_v = ""
            new_v = rx.sub(replace_text, old_v, count=1)
            if new_v == old_v:
                return False

            e["translation"] = new_v
            project_state_store.save_file_state(self.current_project, path, entries)
            return True
        except Exception:
            return False

    
    def _search_replace_all(self, query: str, replace_text: str, params: dict) -> int:
        """Replace all matches according to params.

        Safety: replacement only applies to the 'translation' field.
        Returns the total number of *occurrences* replaced (not rows).
        """
        if not self.current_project:
            return 0

        rx = self._search_compile({**(params or {}), "query": query})
        if rx is None:
            return 0

        scope = str((params or {}).get("scope") or "file").strip().lower()
        if scope == "file":
            tab = self._current_file_tab()
            if not tab or not tab.file_path:
                return 0
            return int(self._replace_all_in_open_tab(tab, rx, replace_text) or 0)

        return int(self._replace_all_in_project(rx, replace_text) or 0)

    def _replace_all_in_open_tab(self, tab, rx, replace_text: str) -> int:
        """Replace in an opened FileTab (in-memory), with undo."""
        if not tab:
            return 0

        entries = getattr(tab, "_entries", []) or []
        if not entries:
            return 0

        changed_rows: list[int] = []
        before: list[dict] = []
        after: list[dict] = []
        total_occ = 0

        for i, e in enumerate(entries):
            if not isinstance(e, dict):
                continue

            old_v = str(self._entry_translation_text(e) or "")
            new_v, n = rx.subn(replace_text, old_v)
            if n <= 0:
                continue

            total_occ += int(n)

            changed_rows.append(i)
            before.append({"translation": old_v, "status": e.get("status") or "untranslated"})
            e["translation"] = new_v
            after.append({"translation": new_v, "status": e.get("status") or "untranslated"})

            try:
                vr = tab._visible_row_from_source_row(i)
                if vr is not None:
                    tab.model.refresh_row(vr)
            except Exception:
                pass

        if not changed_rows:
            return 0

        try:
            tab.record_undo_for_rows(changed_rows, before=before, after=after)
        except Exception:
            pass

        try:
            tab.set_dirty(True)
        except Exception:
            pass

        try:
            tab._refresh_editor_from_selection()
        except Exception:
            pass

        try:
            self._update_tab_title(tab)
        except Exception:
            pass

        return int(total_occ)

    def _apply_saved_state_to_entries(self, path: str, entries: list[dict]) -> None:
        """Apply saved project state (translations/status) onto freshly parsed entries."""
        if not (self.current_project and path and isinstance(entries, list)):
            return

        try:
            st = project_state_store.load_file_state(self.current_project, path)
            saved = getattr(st, "entries", None) if st else None
        except Exception:
            saved = None

        if not (isinstance(saved, list) and saved):
            return

        by_id: dict[str, dict] = {}
        by_original: dict[str, list[dict]] = {}

        for se in saved:
            if not isinstance(se, dict):
                continue
            se_eid = se.get("entry_id")
            if se_eid is not None:
                by_id[str(se_eid)] = se
            o = se.get("original")
            if isinstance(o, str) and o:
                by_original.setdefault(o, []).append(se)

        if by_id:
            for ce in entries:
                if not isinstance(ce, dict):
                    continue
                eid = ce.get("entry_id")
                key = str(eid) if eid is not None else ""
                if key and key in by_id:
                    se = by_id[key]
                    if "translation" in se:
                        ce["translation"] = se.get("translation") or ""
                    if "status" in se:
                        ce["status"] = se.get("status") or "untranslated"

        for ce in entries:
            if not isinstance(ce, dict):
                continue
            if isinstance(ce.get("translation"), str) and (ce.get("translation") or "").strip():
                continue
            o = ce.get("original")
            if not (isinstance(o, str) and o):
                continue
            cands = by_original.get(o) or []
            if len(cands) != 1:
                continue
            se = cands[0]
            if "translation" in se:
                ce["translation"] = se.get("translation") or ""
            if "status" in se:
                ce["status"] = se.get("status") or "untranslated"

        if len(saved) == len(entries):
            for ce, se in zip(entries, saved):
                if not (isinstance(ce, dict) and isinstance(se, dict)):
                    continue
                if "translation" in se and not (isinstance(ce.get("translation"), str) and (ce.get("translation") or "").strip()):
                    ce["translation"] = se.get("translation") or ""
                if "status" in se and not isinstance(ce.get("status"), str):
                    ce["status"] = se.get("status") or "untranslated"

    def _replace_all_in_project(self, rx, replace_text: str) -> int:
        """Replace across project files (persisting state for closed files)."""
        if not self.current_project:
            return 0

        root = (self.current_project.get("root_path") or "").strip()
        if not root or not os.path.isdir(root):
            return 0

        supported = self._supported_extensions()
        encoding = (self.current_project.get("encoding") or "utf-8").strip() or "utf-8"

        total_occ = 0

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for base, dirs, files in os.walk(root):
                dirs[:] = [d for d in dirs if d.lower() != "exports"]

                for fn in files:
                    ext = os.path.splitext(fn)[1].lower()
                    if ext and supported and ext not in supported:
                        continue

                    path = os.path.join(base, fn)
                    if not self._is_openable_candidate(path):
                        continue

                    abs_path = os.path.abspath(path)

                    _, tab = self._get_open_tab_for_path(abs_path)
                    if tab is not None:
                        total_occ += int(self._replace_all_in_open_tab(tab, rx, replace_text) or 0)
                        continue

                    try:
                        with open(abs_path, "r", encoding=encoding, errors="replace") as f:
                            text = f.read()
                    except Exception:
                        continue

                    try:
                        parser = select_parser(self.current_project, abs_path, text)
                        ctx = ParseContext(file_path=abs_path, project=self.current_project, original_text=text)
                        entries = parser.parse(ctx, text)
                        if not isinstance(entries, list):
                            continue
                    except Exception:
                        continue

                    self._apply_saved_state_to_entries(abs_path, entries)

                    changed = False
                    file_occ = 0

                    for e in entries:
                        if not isinstance(e, dict):
                            continue
                        old_v = str(self._entry_translation_text(e) or "")
                        new_v, n = rx.subn(replace_text, old_v)
                        if n <= 0:
                            continue
                        file_occ += int(n)
                        e["translation"] = new_v
                        changed = True

                    if changed:
                        try:
                            project_state_store.save_file_state(self.current_project, abs_path, entries)
                            total_occ += int(file_occ)
                        except Exception:
                            pass
        finally:
            QApplication.restoreOverrideCursor()

        return int(total_occ)
