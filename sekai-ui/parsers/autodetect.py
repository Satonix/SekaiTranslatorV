from __future__ import annotations

import os

from .base import ParseContext, ParserError
from .manager import get_parser_manager


def _plugin_exts_lower(plugin) -> set[str]:
    """
    Retorna um set de extensões em lowercase para o plugin.

    Cacheia no próprio objeto do plugin para evitar recriação (hot path em auto-detect).
    """
    cached = getattr(plugin, "_sekai_exts_lower", None)
    if isinstance(cached, set):
        return cached

    exts = getattr(plugin, "extensions", None) or set()
    out = {str(e).lower() for e in exts if e}
    setattr(plugin, "_sekai_exts_lower", out)
    return out


def select_parser(project: dict, file_path: str, text: str):
    """
    Estratégia:
    1) Se project.parser_id existir, usa ele.
    2) Senão, ranqueia detect(ctx, text).
    3) Se ninguém pontuar > 0, levanta ParserError.
    """
    mgr = get_parser_manager()

    parser_id = (project.get("parser_id") or "").strip()
    if parser_id:
        p = mgr.get(parser_id)
        if p:
            return p

    ctx = ParseContext(
        project=project,
        file_path=file_path,
        original_text=text,
    )

    ext = os.path.splitext(file_path)[1].lower()

    best = None
    best_score = 0.0

    plugins = mgr.all_plugins()  # evita chamar duas vezes (e re-alocar lista)
    for p in plugins:
        try:
            exts = _plugin_exts_lower(p)
            if exts and ext not in exts:
                continue

            score = float(p.detect(ctx, text) or 0.0)
            if score > best_score:
                best_score = score
                best = p
        except Exception:
            continue

    if best is not None and best_score > 0.0:
        return best

    available = sorted(pid for pid in (getattr(p, "plugin_id", "") for p in plugins) if pid)

    raise ParserError(
        "Nenhum parser compatível foi detectado.\n\n"
        f"Arquivo: {file_path}\n"
        f"Extensão: {ext or '(sem extensão)'}\n"
        f"Parsers disponíveis: {', '.join(available) or '(nenhum)'}\n\n"
        "Instale parsers em Plugins → Parsers."
    )
