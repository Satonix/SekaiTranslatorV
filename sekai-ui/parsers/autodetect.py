from __future__ import annotations

from parsers.base import ParseContext
from parsers.manager import get_parser_manager


def autodetect_parser_id(ctx: ParseContext, text: str) -> str | None:
    """Retorna o parser_id mais provável para o arquivo atual."""

    mgr = get_parser_manager()
    best_id: str | None = None
    best_score = 0.0

    for meta in mgr.list_available():
        pid = meta.get("id")
        if not pid:
            continue
        p = mgr.get_parser(pid)
        if not p:
            continue
        score = float(p.detect(ctx, text))
        if score > best_score:
            best_score = score
            best_id = pid

    return best_id


def select_parser(
    ctx: ParseContext,
    text: str,
    parser_id: str | None = None,
    allow_autodetect: bool = True,
    raise_on_fail: bool = True,
):
    """Seleciona um parser.

    - Se ``parser_id`` for fornecido, tenta carregar esse.
    - Caso contrário, faz autodetect (se permitido).
    """

    mgr = get_parser_manager()

    def _try_get_with_fallback(pid_in: str):
        """Try to resolve parser ids like 'kirikiri.ks.yandere' when only
        'kirikiri.ks' exists. Falls back by trimming suffix segments."""
        pid_try = (pid_in or "").strip()
        while pid_try:
            p = mgr.get_parser(pid_try)
            if p:
                return p
            if "." not in pid_try:
                break
            pid_try = pid_try.rsplit(".", 1)[0]
        return None

    pid = (parser_id or "").strip() or None
    if not pid and allow_autodetect:
        pid = autodetect_parser_id(ctx, text)

    if pid:
        p = _try_get_with_fallback(pid)
        if p:
            return p

    if allow_autodetect:
        pid2 = autodetect_parser_id(ctx, text)
        if pid2:
            p2 = _try_get_with_fallback(pid2)
            if p2:
                return p2

    if raise_on_fail:
        raise RuntimeError("Nenhum parser compatível encontrado. Verifique o repo de parsers.")
    return None
