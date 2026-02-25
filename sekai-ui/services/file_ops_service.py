from __future__ import annotations

import os
from typing import Any

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QMessageBox

from parsers.autodetect import select_parser
from parsers.base import ParseContext
from services.encoding_service import EncodingService
from models import project_state_store


def open_file(main_window: Any, index: QModelIndex) -> None:
    """Abre arquivo a partir do tree view (QFileSystemModel).

    Espera que main_window tenha:
      - fs_model (QFileSystemModel)
      - tabs (QTabWidget)
      - current_project (dict)
      - _open_files (dict[path->FileTab]) (opcional)
    """
    try:
        file_path = main_window.fs_model.filePath(index)
    except Exception:
        file_path = ""

    file_path = (file_path or "").strip()
    if not file_path or not os.path.isfile(file_path):
        return

    # Evita abrir duplicado
    open_files = getattr(main_window, "_open_files", None) or {}
    if file_path in open_files:
        try:
            tab = open_files[file_path]
            main_window.tabs.setCurrentWidget(tab)
        except Exception:
            pass
        return

    project = getattr(main_window, "current_project", None) or {}

    # Encoding de ENTRADA:
    # - Se já foi detectado antes (estado do projeto), reutilize para garantir round-trip estável.
    # - Caso contrário, tenta detectar de forma conservadora (BOM + lista de candidatos),
    #   preferindo o encoding configurado no projeto como "hint".
    hint_encoding = (project.get("encoding") or "utf-8").strip() or "utf-8"
    if hint_encoding.lower() == "auto":
        hint_encoding = "utf-8"

    st = project_state_store.load_file_state(project, file_path)
    state_encoding = (getattr(st, "encoding", "") or "").strip()

    raw = b""
    try:
        raw = EncodingService.read_bytes(file_path)
    except Exception as e:
        QMessageBox.critical(main_window, "Erro", f"Falha ao ler arquivo:\n{e}")
        return

    def _try_decode(enc: str) -> str | None:
        try:
            raw.decode(enc, errors="strict")
            return enc
        except Exception:
            return None

    # BOM heuristics (não tenta "adivinhar" sem necessidade)
    bom_first: list[str] = []
    if raw.startswith(b"\xef\xbb\xbf"):
        bom_first.append("utf-8-sig")
    elif raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        # 'utf-16' usa BOM automaticamente
        bom_first.append("utf-16")

    candidates: list[str] = []
    for e in [state_encoding, *bom_first, hint_encoding, "utf-8", "utf-8-sig", "cp932", "shift_jis", "windows-1252"]:
        e = (e or "").strip()
        if e and e not in candidates:
            candidates.append(e)

    chosen = ""
    for enc in candidates:
        if _try_decode(enc):
            chosen = enc
            break

    if not chosen:
        # fallback: usa hint do projeto com replace (não crasha), mas marca o encoding usado
        chosen = hint_encoding

    try:
        decoded = EncodingService.decode_bytes(raw, chosen, errors="replace")
        text = decoded.text or ""
    except Exception as e:
        QMessageBox.critical(main_window, "Erro", f"Falha ao decodificar arquivo:\n{e}")
        return

    try:
        ctx = ParseContext(
            file_path=file_path,
            project=project,
            original_text=text,
            encoding=chosen,
            options={"newline_style": decoded.newline_style, "had_bom": decoded.had_bom},
        )
        parser = select_parser(ctx, text, raise_on_fail=True)

        # Compat: parsers antigos retornam diretamente uma lista de Entry.
        # Parsers novos podem retornar ParseResult(engine_id, entries=[...]).
        parse_res = parser.parse(ctx, text)
        if isinstance(parse_res, list):
            entries = parse_res
        else:
            entries = getattr(parse_res, "entries", None) or []
    except Exception as e:
        QMessageBox.critical(main_window, "Erro", f"Falha no parse: {e}")
        return

    try:
        from views.file_tab import FileTab  # import tardio p/ evitar ciclos

        tab = FileTab(main_window)
        tab.file_path = file_path
        tab.parser = parser
        tab.parse_ctx = ctx
        tab.input_encoding = chosen
        tab.newline_style = decoded.newline_style
        tab.had_bom = decoded.had_bom
        tab.set_entries(entries)
        
        try:
            tab.load_project_state_if_exists(project)
        except Exception as e:
            QMessageBox.warning(main_window, "Aviso", f"Falha ao carregar estado salvo:\n{e}")

        title = os.path.basename(file_path) or file_path
        tab_index = main_window.tabs.addTab(tab, title)
        main_window.tabs.setCurrentIndex(tab_index)

        if not hasattr(main_window, "_open_files") or main_window._open_files is None:
            main_window._open_files = {}
        main_window._open_files[file_path] = tab

        title = os.path.basename(file_path) or file_path
        tab_index = main_window.tabs.addTab(tab, title)
        main_window.tabs.setCurrentIndex(tab_index)

        if not hasattr(main_window, "_open_files") or main_window._open_files is None:
            main_window._open_files = {}
        main_window._open_files[file_path] = tab
    except Exception as e:
        QMessageBox.critical(main_window, "Erro", f"Falha ao abrir aba:\n{e}")
        return
