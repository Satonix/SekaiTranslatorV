from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QMessageBox

from views.file_tab import FileTab

if TYPE_CHECKING:
    from views.dialogs.search_dialog import SearchResult
else:
    SearchResult = Any

from parsers.autodetect import select_parser
from parsers.base import ParseContext


class ExportOpsMixin:
    def _export_current_file(self):
        tab = self._current_file_tab()
        if not tab or not self.current_project or not tab.file_path:
            return

        parser = getattr(tab, "parser", None)
        ctx = getattr(tab, "parse_ctx", None)

        # Se não temos parser/ctx (ex.: arquivo aberto por outro caminho), recria usando o encoding original.
        if parser is None or ctx is None:
            from services.encoding_service import EncodingService
            from models import project_state_store

            hint_encoding = (self.current_project.get("encoding") or "utf-8").strip() or "utf-8"
            if hint_encoding.lower() == "auto":
                hint_encoding = "utf-8"

            st = project_state_store.load_file_state(self.current_project, tab.file_path)
            state_encoding = (getattr(st, "encoding", "") or "").strip()

            try:
                raw = EncodingService.read_bytes(tab.file_path)
            except Exception:
                raw = b""

            def _try_decode(enc: str) -> bool:
                try:
                    raw.decode(enc, errors="strict")
                    return True
                except Exception:
                    return False

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

            ctx = ParseContext(
                file_path=tab.file_path,
                project=self.current_project,
                original_text=text,
                encoding=chosen,
                options={"newline_style": decoded.newline_style, "had_bom": decoded.had_bom},
            )
            parser_id = (self.current_project.get("parser_id") or "").strip() or None
            parser = select_parser(ctx, text, parser_id=parser_id, allow_autodetect=True, raise_on_fail=True)
            tab.parser = parser
            tab.parse_ctx = ctx

        try:
            out_path = tab.export_to_disk(self.current_project, parser=parser, ctx=ctx)

            exp_enc = (self.current_project.get("export_encoding") or "utf-8").strip() or "utf-8"
            exp_bom = bool(self.current_project.get("export_bom", False))
            bom_txt = " (com BOM)" if exp_bom else ""

            self.statusBar().showMessage(
                f"Arquivo exportado em {exp_enc}{bom_txt}: {os.path.basename(out_path)}",
                2500,
            )
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))

    def _export_project_batch(self):
        if not self.current_project:
            return

        root = (self.fs_model.rootPath() or "").strip()
        if not root or not os.path.isdir(root):
            QMessageBox.critical(self, "Erro", "Root do projeto inválido.")
            return

        supported = self._supported_extensions()

        errors: list[str] = []
        count_ok = 0

        from services.encoding_service import EncodingService
        from models import project_state_store

        # Feedback consistente sobre o formato de saída
        exp_enc = (self.current_project.get("export_encoding") or "utf-8").strip() or "utf-8"
        exp_bom = bool(self.current_project.get("export_bom", False))
        bom_txt = " (com BOM)" if exp_bom else ""

        for base, dirs, files in os.walk(root):
            # não re-exportar exports
            dirs[:] = [d for d in dirs if d.lower() != "exports"]

            for fn in files:
                ext = os.path.splitext(fn)[1].lower()
                if ext and supported and ext not in supported:
                    continue

                src_path = os.path.join(base, fn)

                try:
                    # Detecta encoding de ENTRADA por arquivo (state -> BOM -> hints)
                    hint_encoding = (self.current_project.get("encoding") or "utf-8").strip() or "utf-8"
                    if hint_encoding.lower() == "auto":
                        hint_encoding = "utf-8"

                    st = project_state_store.load_file_state(self.current_project, src_path)
                    state_encoding = (getattr(st, "encoding", "") or "").strip()

                    raw = EncodingService.read_bytes(src_path)

                    def _try_decode(enc: str) -> bool:
                        try:
                            raw.decode(enc, errors="strict")
                            return True
                        except Exception:
                            return False

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


                    try:
                        ctx = ParseContext(
                            file_path=src_path,
                            project=self.current_project,
                            original_text=text,
                            encoding=chosen,
                            options={"newline_style": decoded.newline_style, "had_bom": decoded.had_bom},
                        )
                    except TypeError:
                        ctx = ParseContext(file_path=src_path, project=self.current_project)

                    parser_id = (self.current_project.get("parser_id") or "").strip() or None
                    parser = select_parser(ctx, text, parser_id=parser_id, allow_autodetect=True, raise_on_fail=True)

                    entries = parser.parse(ctx, text)

                    # Usa FileTab para aplicar state + export com o mesmo código do arquivo atual
                    tmp = FileTab(self)
                    tmp.file_path = src_path
                    tmp.parser = parser
                    tmp.parse_ctx = ctx
                    tmp.input_encoding = chosen
                    tmp.newline_style = decoded.newline_style
                    tmp.had_bom = decoded.had_bom

                    tmp.set_entries(entries)
                    tmp.load_project_state_if_exists(self.current_project)

                    # ✅ Export consistente (respeita export_encoding + export_bom e o fix de bytes->reencode)
                    tmp.export_to_disk(self.current_project, parser=parser, ctx=ctx)

                    count_ok += 1

                except Exception as e:
                    try:
                        rel = os.path.relpath(src_path, root)
                    except Exception:
                        rel = src_path
                    errors.append(f"{rel}: {e}")

        if errors:
            QMessageBox.warning(
                self,
                "Exportação em lote",
                f"Concluído com erros.\n\n"
                f"OK: {count_ok}\n"
                f"Erros: {len(errors)}\n"
                f"Saída: {exp_enc}{bom_txt}\n\n"
                + "\n".join(errors[:20]),
            )
        else:
            QMessageBox.information(
                self,
                "Exportação em lote",
                f"OK: {count_ok} arquivos exportados em {exp_enc}{bom_txt}.",
            )

        self.statusBar().showMessage("Exportação em lote finalizada", 3000)

    # ---------------------------------------------------------------------
    # IMPORTANTE:
    # O restante do conteúdo que estava dentro deste arquivo (handlers de IA)
    # estava INDENTADO dentro de _export_project_batch(), o que é um bug.
    # Se esses métodos existem, eles devem ficar no nível da classe (abaixo),
    # não aninhados dentro de _export_project_batch().
    # ---------------------------------------------------------------------

    def _on_ai_translate_progress(self, done: int, total: int):
        if self._ai_progress:
            self._ai_progress.set_total(int(total or 0))
            self._ai_progress.set_progress(int(done or 0))

    def _on_ai_translate_canceled(self):
        try:
            if self._ai_progress:
                self._ai_progress.close()
        except Exception:
            pass
        self.statusBar().showMessage("Tradução cancelada", 2000)

    def _on_ai_translate_failed(self, msg: str):
        try:
            if self._ai_progress:
                self._ai_progress.close()
        except Exception:
            pass

        QMessageBox.critical(self, "Erro", msg)
        self.statusBar().showMessage("Erro na tradução", 3000)

    def _on_ai_translate_finished(self, resp: dict):
        try:
            if self._ai_progress:
                self._ai_progress.close()
        except Exception:
            pass
        self._ai_progress = None

        ctx = self._ai_ctx or {}
        tab: FileTab | None = ctx.get("tab")
        entries: list[dict] = ctx.get("entries") or []
        items: list[dict] = ctx.get("items") or []
        row_by_id: dict[str, int] = ctx.get("row_by_id") or {}
        source_rows: list[int] = ctx.get("source_rows") or []

        if not tab or not entries:
            return

        if isinstance(resp, dict) and resp.get("error"):
            QMessageBox.critical(self, "Erro", str(resp.get("error")))
            self.statusBar().showMessage("Erro na tradução", 3000)
            return

        if not (isinstance(resp, dict) and isinstance(resp.get("results"), list)):
            QMessageBox.critical(self, "Erro", "Resposta inesperada do proxy (batch).")
            self.statusBar().showMessage("Erro na tradução", 3000)
            return

        by_id: dict[str, str] = {}
        for r in resp["results"]:
            if not isinstance(r, dict):
                continue
            rid = str(r.get("id") or "").strip()
            tr = r.get("translation")
            if rid and isinstance(tr, str):
                by_id[rid] = tr

        if not by_id:
            QMessageBox.critical(self, "Erro", "Proxy retornou results vazio.")
            self.statusBar().showMessage("Erro na tradução", 3000)
            return

        from views.dialogs.translation_preview_dialog import TranslationPreviewDialog

        preview_rows = [row_by_id[i["id"]] for i in items if str(i.get("id")) in row_by_id]
        preview = TranslationPreviewDialog(
            self,
            entries=entries,
            source_rows=preview_rows,
            translations_by_id=by_id,
        )
        if not preview.exec():
            self.statusBar().showMessage("Tradução cancelada", 2000)
            return

        changed_rows: list[int] = []
        before_snap: list[dict] = []

        for sr in source_rows:
            if not (0 <= sr < len(entries)):
                continue

            e = entries[sr]
            if not e.get("is_translatable", True):
                continue

            eid = str(e.get("entry_id") or str(sr))
            new_tr = by_id.get(eid)
            if new_tr is None:
                continue

            old_tr = e.get("translation") or ""
            old_status = e.get("status") or "untranslated"

            if old_tr == new_tr and old_status == "in_progress":
                continue

            changed_rows.append(sr)
            before_snap.append({"translation": old_tr, "status": old_status})

            e["translation"] = new_tr
            e["status"] = "in_progress"

        if not changed_rows:
            self.statusBar().showMessage("Nada para atualizar", 2500)
            return

        after_snap: list[dict] = []
        for sr in changed_rows:
            e = entries[sr]
            after_snap.append(
                {"translation": e.get("translation") or "", "status": e.get("status") or "untranslated"}
            )

        tab.record_undo_for_rows(changed_rows, before=before_snap, after=after_snap)

        for sr in changed_rows:
            vr = tab._visible_row_from_source_row(sr)
            if vr is not None:
                tab.model.refresh_row(vr)

        tab.set_dirty(True)
        tab._refresh_editor_from_selection()

        self.statusBar().showMessage("Tradução aplicada (em edição)", 2500)
