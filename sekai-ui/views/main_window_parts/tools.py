from __future__ import annotations

import os
import re
from typing import Any, TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from views.file_tab import FileTab

if TYPE_CHECKING:
    from views.dialogs.search_dialog import SearchResult
else:
    SearchResult = Any

from parsers.autodetect import select_parser
from parsers.base import ParseContext


class ToolsMixin:
    # -------------------------
    # Dialogs / tools
    # -------------------------
    def _open_plugins(self):
        from views.dialogs.plugin_manager_dialog import PluginManagerDialog
        PluginManagerDialog(self).exec()

    def _open_qa(self):
        from views.dialogs.qa_dialog import QADialog
        QADialog(self).exec()

    def _open_glossary(self):
        from views.dialogs.glossary_dialog import GlossaryDialog
        GlossaryDialog(self).exec()

    def _open_tm(self):
        from views.dialogs.translation_memory_dialog import TranslationMemoryDialog
        TranslationMemoryDialog(self).exec()

    def _open_about(self):
        msg = QMessageBox(self)
        msg.setWindowTitle("Sobre")
        msg.setIcon(QMessageBox.Information)
        msg.setText(f"{self.app_name}\nVersão {self.app_version}")
        msg.setInformativeText("Ferramenta de tradução de Visual Novels.")
        btn_check = msg.addButton("Verificar atualizações...", QMessageBox.ActionRole)
        msg.addButton(QMessageBox.Ok)
        msg.exec()
        if msg.clickedButton() == btn_check:
            self._check_updates_now()

    def _open_preferences(self):
        from views.dialogs.preferences_dialog import PreferencesDialog
        PreferencesDialog(self).exec()

    def _open_search(self):
        """Abre o diálogo de busca (Ctrl+F)."""
        from views.dialogs.search_dialog import SearchDialog

        allow_project = bool(self.current_project)
        default_scope = "project" if allow_project else "file"

        dlg = SearchDialog(
            parent=self,
            do_search=self.search_service._search_run,
            replace_one=self.search_service._search_replace_one,
            replace_all=self.search_service._search_replace_all,
            open_result=self.search_service._search_open_result,
            default_scope=default_scope,
        )

        if not allow_project:
            try:
                dlg.rb_project.setEnabled(False)
                dlg.rb_file.setChecked(True)
            except Exception:
                pass

        dlg.exec()

    # -------------------------
    # Replace helpers
    # -------------------------
    def _replace_all_in_open_tab(self, tab: FileTab, rx: re.Pattern, repl: str) -> int:
        entries = getattr(tab, "_entries", []) or []
        changed_rows: list[int] = []
        before: list[dict] = []
        after: list[dict] = []
        total_replacements = 0

        for i, e in enumerate(entries):
            if not isinstance(e, dict):
                continue

            old_v = self._entry_translation_text(e)
            if not isinstance(old_v, str) or not old_v:
                continue

            new_v, n = rx.subn(repl, old_v)
            if n <= 0 or new_v == old_v:
                continue

            total_replacements += int(n)
            changed_rows.append(i)
            before.append({"translation": old_v, "status": e.get("status") or "untranslated"})
            e["translation"] = new_v
            after.append({"translation": new_v, "status": e.get("status") or "untranslated"})

        if not changed_rows:
            return 0

        # depende do seu FileTab ter essas APIs
        tab.record_undo_for_rows(changed_rows, before=before, after=after)
        tab.set_dirty(True)

        for r in changed_rows:
            vr = tab._visible_row_from_source_row(r)
            if vr is not None:
                tab.model.refresh_row(vr)

        tab._refresh_editor_from_selection()
        self._update_tab_title(tab)
        return total_replacements

    def _replace_all_in_project(self, rx: re.Pattern, repl: str) -> int:
        if not self.current_project:
            return 0

        root = (self.current_project.get("root_path") or "").strip()
        if not root or not os.path.isdir(root):
            return 0

        supported = self._supported_extensions()

        # hint apenas (entrada real deve ser detectada por arquivo)
        hint_encoding = (self.current_project.get("encoding") or "utf-8").strip() or "utf-8"
        if hint_encoding.lower() == "auto":
            hint_encoding = "utf-8"

        total_replacements = 0

        from services.encoding_service import EncodingService
        from models import project_state_store

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

                    # Se já estiver aberto, opera em memória (inclui não-salvo)
                    tab = self._open_files.get(abs_path)
                    if tab is not None:
                        total_replacements += int(self._replace_all_in_open_tab(tab, rx, repl) or 0)
                        continue

                    # --- ler bytes + detectar encoding original do arquivo ---
                    try:
                        st = project_state_store.load_file_state(self.current_project, abs_path)
                        state_encoding = (getattr(st, "encoding", "") or "").strip()
                    except Exception:
                        st = None
                        state_encoding = ""

                    try:
                        raw = EncodingService.read_bytes(abs_path)
                    except Exception:
                        continue

                    def _try_decode(enc: str) -> str | None:
                        try:
                            raw.decode(enc, errors="strict")
                            return enc
                        except Exception:
                            return None

                    bom_first: list[str] = []
                    if raw.startswith(b"\xef\xbb\xbf"):
                        bom_first.append("utf-8-sig")
                    elif raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
                        bom_first.append("utf-16")

                    candidates: list[str] = []
                    for e in [
                        state_encoding,
                        *bom_first,
                        hint_encoding,
                        "utf-8",
                        "utf-8-sig",
                        "cp932",
                        "shift_jis",
                        "windows-1252",
                    ]:
                        e = (e or "").strip()
                        if e and e not in candidates:
                            candidates.append(e)

                    chosen = ""
                    for enc in candidates:
                        if _try_decode(enc):
                            chosen = enc
                            break
                    if not chosen:
                        chosen = hint_encoding

                    decoded = EncodingService.decode_bytes(raw, chosen, errors="replace")
                    text = decoded.text or ""

                    # --- parse ---
                    try:
                        parser = select_parser(self.current_project, abs_path, text)
                        try:
                            ctx = ParseContext(
                                file_path=abs_path,
                                project=self.current_project,
                                original_text=text,
                                encoding=chosen,
                                options={"newline_style": decoded.newline_style, "had_bom": decoded.had_bom},
                            )
                        except TypeError:
                            ctx = ParseContext(file_path=abs_path, project=self.current_project)

                        entries = parser.parse(ctx, text)
                    except Exception:
                        continue

                    # --- aplicar estado salvo (tradução/status) se existir ---
                    try:
                        if st and getattr(st, "entries", None):
                            by_id: dict[str, dict] = {}
                            for se in st.entries:
                                if not isinstance(se, dict):
                                    continue
                                se_eid = se.get("entry_id")
                                if se_eid is None:
                                    continue
                                by_id[str(se_eid)] = se

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
                    except Exception:
                        pass

                    # --- replace ---
                    changed_any = False
                    for e in entries:
                        if not isinstance(e, dict):
                            continue
                        old_v = self._entry_translation_text(e)
                        if not isinstance(old_v, str) or not old_v:
                            continue
                        new_v, n = rx.subn(repl, old_v)
                        if n > 0 and new_v != old_v:
                            e["translation"] = new_v
                            total_replacements += int(n)
                            changed_any = True

                    # --- salvar estado do arquivo (não exporta arquivo final aqui) ---
                    if changed_any:
                        try:
                            # mantém encoding original detectado
                            project_state_store.save_file_state(
                                self.current_project,
                                abs_path,
                                entries,
                                encoding=chosen,
                                newline_style=decoded.newline_style,
                                had_bom=decoded.had_bom,
                            )
                        except TypeError:
                            # compat com assinatura antiga
                            try:
                                project_state_store.save_file_state(self.current_project, abs_path, entries)
                            except Exception:
                                pass
                        except Exception:
                            pass
        finally:
            QApplication.restoreOverrideCursor()

        return total_replacements

    
    # -------------------------
    # AI Translate
    # -------------------------
    def _translate_current_file_with_ai(self) -> None:
        """
        Tradução com IA para as linhas selecionadas no arquivo atual.
        - Não bloqueia a UI (usa QThread + AITranslateWorker)
        - Mostra preview e aplica com undo/redo
        """
        from PySide6.QtCore import QThread, Qt
        from PySide6.QtWidgets import QProgressDialog, QMessageBox

        # Aba atual (arquivo)
        tab = None
        try:
            if hasattr(self, "_current_file_tab"):
                tab = self._current_file_tab()
        except Exception:
            tab = None

        if tab is None:
            try:
                w = self.tabs.currentWidget() if hasattr(self, "tabs") else None
                if w is not None and hasattr(w, "file_path") and hasattr(w, "model"):
                    tab = w
            except Exception:
                tab = None

        if tab is None or not getattr(tab, "file_path", None):
            QMessageBox.critical(self, "Erro", "Nenhum arquivo aberto.")
            return

        if not getattr(self, "current_project", None):
            QMessageBox.critical(self, "Erro", "Nenhum projeto aberto.")
            return

        # Linhas selecionadas (visíveis -> source rows)
        # IMPORTANTE:
        # - selectedRows() pode retornar só as linhas com seleção na coluna 0.
        # - selectedIndexes() pode falhar em alguns casos (ex.: seleção por range/drag).
        # Use selection() (QItemSelection) para coletar ranges e incluir todas as linhas no meio.
        visible_rows: list[int] = []
        try:
            sm = tab.table.selectionModel() if hasattr(tab, "table") else None
            if sm:
                rows_set: set[int] = set()

                try:
                    sel = sm.selection()
                    for r in sel:
                        top = int(r.top())
                        bottom = int(r.bottom())
                        for rr in range(top, bottom + 1):
                            rows_set.add(rr)
                except Exception:
                    pass

                if not rows_set:
                    try:
                        idxs = list(sm.selectedIndexes() or [])
                        for i in idxs:
                            rows_set.add(int(i.row()))
                    except Exception:
                        pass

                if not rows_set:
                    try:
                        for i in sm.selectedRows():
                            rows_set.add(int(i.row()))
                    except Exception:
                        pass

                visible_rows = sorted(rows_set)
        except Exception:
            # fallback legado
            try:
                visible_rows = list(tab._visible_rows() or [])
            except Exception:
                visible_rows = []
        if not visible_rows:
            QMessageBox.information(self, "IA", "Selecione uma ou mais linhas para traduzir.")
            return

        source_rows: list[int] = []
        # Mapear visible row -> source row de forma robusta:
        # 1) se a model expõe "entries" (lista visível), use identidade do dict para achar no vetor fonte (tab._entries)
        # 2) fallback para tab._source_row_from_visible_row (model.visible_row_to_source_row)
        entries = getattr(tab, "_entries", []) or []

        for vr in visible_rows:
            sr: int | None = None

            # (1) identidade do dict (mais confiável quando entry_id/line_number não são únicos)
            try:
                vis_entries = getattr(getattr(tab, "model", None), "entries", None)
                if isinstance(vis_entries, list) and 0 <= vr < len(vis_entries):
                    ve = vis_entries[vr]
                    if isinstance(ve, dict):
                        for i, e in enumerate(entries):
                            if e is ve:
                                sr = i
                                break
            except Exception:
                sr = None

            # (2) fallback: mapper do model (entry_id/line_number)
            if sr is None:
                try:
                    sr = tab._source_row_from_visible_row(vr)
                except Exception:
                    sr = None

            if isinstance(sr, int) and 0 <= sr < len(entries) and sr not in source_rows:
                source_rows.append(sr)

        if not source_rows:
            QMessageBox.information(self, "IA", "Seleção inválida.")
            return

        # Config IA
        proxy_url = ""
        try:
            proxy_url = self._proxy_url()
        except Exception:
            proxy_url = ""

        api_token = (getattr(self, "api_token", None) or "").strip()
        if not api_token:
            QMessageBox.critical(self, "Erro", "Você precisa estar logado para usar a tradução com IA.")
            return

        target_language = (self.current_project.get("target_language") or "").strip() or "pt-BR"

        custom_prompt_text = (self.current_project.get("custom_prompt_text") or "").strip()
        user_prompt = (self.current_project.get("user_prompt") or "").strip()

        if not custom_prompt_text:
            try:
                from views.dialogs.project_settings_ai_tab import ProjectSettingsAITab
                key = (self.current_project.get("ai_prompt_key") or "default").strip() or "default"
                custom_prompt_text = (ProjectSettingsAITab.PROMPT_PRESETS.get(key) or "").strip()
            except Exception:
                custom_prompt_text = ""

        items: list[dict] = []
        preview_rows: list[dict] = []
        for r in source_rows:
            e = entries[r] if 0 <= r < len(entries) else None
            if not isinstance(e, dict):
                continue
            original = (e.get("original") or "").strip()
            if not original:
                continue
            item_id = str(e.get("entry_id") or e.get("id") or r)
            items.append({"id": item_id, "text": original})
            preview_rows.append({"row": r, "original": original, "translation": ""})

        if not items:
            QMessageBox.information(self, "IA", "Nenhuma linha traduzível na seleção.")
            return

        payload: dict = {
            "items": items,
            "target_language": target_language,
        }
        if custom_prompt_text:
            payload["custom_prompt_text"] = custom_prompt_text
        if user_prompt:
            payload["user_prompt"] = user_prompt

        # Worker em thread
        from views.workers.ai_translate_worker import AITranslateWorker

        progress = QProgressDialog("Traduzindo com IA...", "Cancelar", 0, len(items), self)
        progress.setWindowTitle("IA")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setValue(0)
        progress.show()  # NÃO usar exec() aqui

        thread = QThread(self)
        worker = AITranslateWorker(
            proxy_url=proxy_url,
            api_token=api_token,
            payload=payload,
            timeout=60.0,
            chunk_size=1,
        )
        worker.moveToThread(thread)

        def _cleanup() -> None:
            # encerra progress
            try:
                progress.close()
            except Exception:
                pass
            try:
                progress.deleteLater()
            except Exception:
                pass

            # encerra thread/worker
            try:
                thread.quit()
            except Exception:
                pass
            try:
                setattr(self, "_ai_translate_bridge", None)
            except Exception:
                pass
            try:
                worker.deleteLater()
            except Exception:
                pass
            try:
                thread.deleteLater()
            except Exception:
                pass

        def _on_progress(done: int, total: int) -> None:
            try:
                progress.setMaximum(max(1, int(total)))
                progress.setValue(int(done))
            except Exception:
                pass

        def _on_failed(msg: str) -> None:
            _cleanup()
            QMessageBox.critical(self, "Erro", f"Falha na tradução com IA:\n{msg}")

        def _on_canceled() -> None:
            _cleanup()
            QMessageBox.information(self, "IA", "Tradução cancelada.")

        def _on_finished(resp: dict) -> None:
            _cleanup()

            results = resp.get("results") if isinstance(resp, dict) else None
            if not isinstance(results, list):
                QMessageBox.critical(self, "Erro", "Resposta inválida do proxy.")
                return

            by_id: dict[str, str] = {}
            for r in results:
                if not isinstance(r, dict):
                    continue
                rid = str(r.get("id") or "")
                tr = r.get("translation")
                if rid and isinstance(tr, str):
                    by_id[rid] = tr

            # preencher preview_rows
            for pr in preview_rows:
                row = pr.get("row")
                e = entries[row] if isinstance(row, int) and 0 <= row < len(entries) else None
                if isinstance(e, dict):
                    item_id = str(e.get("entry_id") or e.get("id") or row)
                    pr["translation"] = by_id.get(item_id, "")

            from views.dialogs.translation_preview_dialog import TranslationPreviewDialog

            dlg = TranslationPreviewDialog(
                self,
                entries=entries,
                source_rows=list(source_rows),
                translations_by_id=by_id,
            )
            dlg.exec()

            if not getattr(dlg, "confirmed", False):
                return

            before_snap: list[dict] = tab.snapshot_rows(list(source_rows))
            changed_rows: list[int] = []

            for row in source_rows:
                if not (0 <= row < len(entries)):
                    continue
                e = entries[row]
                if not isinstance(e, dict):
                    continue
                item_id = str(e.get("entry_id") or e.get("id") or row)
                tr = by_id.get(item_id, "")
                if not isinstance(tr, str) or tr.strip() == "":
                    continue
                e["translation"] = tr
                e["status"] = "in_progress"   # <- aqui
                changed_rows.append(row)

            # aplicar com undo (otimizado para grandes seleções)
            if changed_rows:
                try:
                    if len(changed_rows) >= 200 and hasattr(tab, "model"):
                        _orig_refresh_row = getattr(tab.model, "refresh_row", None)
                        try:
                            if callable(_orig_refresh_row):
                                tab.model.refresh_row = lambda _row: None  # type: ignore
                            tab.apply_commit_with_undo(changed_rows, before_snap=before_snap)
                        finally:
                            if callable(_orig_refresh_row):
                                tab.model.refresh_row = _orig_refresh_row  # type: ignore

                        # um repaint único para toda a tabela visível
                        try:
                            rc = tab.model.rowCount()
                            cc = tab.model.columnCount()
                            if rc > 0 and cc > 0:
                                left = tab.model.index(0, 0)
                                right = tab.model.index(rc - 1, cc - 1)
                                tab.model.dataChanged.emit(left, right)
                        except Exception:
                            pass
                    else:
                        tab.apply_commit_with_undo(changed_rows, before_snap=before_snap)
                except Exception:
                    tab.apply_commit_with_undo(changed_rows, before_snap=before_snap)

            try:
                tab._refresh_editor_from_selection()
            except Exception:
                pass
            try:
                self._update_tab_title(tab)
            except Exception:
                pass

        # Bridge QObject: garante que callbacks rodam na UI thread (evita travar ao abrir dialogs)
        from PySide6.QtCore import QObject, Slot

        class _AIBridge(QObject):
            @Slot(int, int)
            def on_progress(self, done: int, total: int) -> None:
                _on_progress(done, total)

            @Slot(str)
            def on_failed(self, msg: str) -> None:
                _on_failed(msg)

            @Slot()
            def on_canceled(self) -> None:
                _on_canceled()

            @Slot(dict)
            def on_finished(self, resp: dict) -> None:
                _on_finished(resp)

        bridge = _AIBridge(self)
        # manter referência durante a execução (evita GC)
        self._ai_translate_bridge = bridge  # type: ignore[attr-defined]

        worker.progress.connect(bridge.on_progress, type=Qt.QueuedConnection)
        worker.failed.connect(bridge.on_failed, type=Qt.QueuedConnection)
        worker.canceled.connect(bridge.on_canceled, type=Qt.QueuedConnection)
        worker.finished.connect(bridge.on_finished, type=Qt.QueuedConnection)

        thread.started.connect(worker.run)
        progress.canceled.connect(worker.cancel)

        # limpeza quando a thread finalizar (sem bloquear a UI)
        try:
            thread.finished.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)
        except Exception:
            pass

        thread.start()
