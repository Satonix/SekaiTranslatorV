from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict


class SpanItem(TypedDict, total=False):
    """Item de span para round-trip.

    Recomendação de uso em parsers:
    - kind: "raw" | "cmd" | "text" | "text_mid"
    - line_index: índice da linha no arquivo original
    - raw: linha completa preservada (para raw/cmd)
    - prefix/suffix: partes preservadas ao redor do texto (para text/text_mid)
    """

    kind: Literal["raw", "cmd", "text", "text_mid"]
    line_index: int
    raw: str
    prefix: str
    suffix: str


class EntryDict(TypedDict, total=False):
    entry_id: str
    original: str
    translation: str
    status: str
    is_translatable: bool
    speaker: str
    meta: dict[str, Any]
