from __future__ import annotations

"""Helpers para parsers de scripts de texto (ex: KiriKiri .ks).

Este módulo não é usado automaticamente pelo UI; ele existe para reduzir boilerplate
na criação de novos parsers e tornar rebuild/round-trip mais previsível.
"""

import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional, Tuple

from .entries import make_entry
from .types import EntryDict, SpanItem


COMMENT_RE = re.compile(r"^\s*;")
LABEL_RE = re.compile(r"^\s*\*")
INLINE_CMD_RE = re.compile(r"^\s*@")
TAG_ONLY_RE = re.compile(r"^\s*(?:\[[^\]]+\]\s*)+(?:\r?\n)?$")
ANY_TAG_RE = re.compile(r"\[[^\]]+\]")


def split_leading_ws(s: str) -> Tuple[str, str]:
    i = 0
    n = len(s)
    while i < n and s[i] in (" ", "\t"):
        i += 1
    return s[:i], s[i:]


def is_translatable_text(text: str) -> bool:
    if text is None or text.strip() == "":
        return False
    if TAG_ONLY_RE.match(text):
        return False
    tmp = ANY_TAG_RE.sub("", text)
    return tmp.strip() != ""


def find_first_break_tag(line: str, tags: tuple[str, ...] = ("[r]", "[cr]")) -> tuple[int, str]:
    """Retorna (idx, tag) para o primeiro tag encontrado; (-1, "") se não houver."""
    best = (-1, "")
    for t in tags:
        idx = line.find(t)
        if idx < 0:
            continue
        if best[0] < 0 or idx < best[0]:
            best = (idx, t)
    return best


@dataclass
class BlockState:
    """Estado de um bloco de diálogo."""

    start_line: Optional[int] = None
    span: list[SpanItem] = None  # type: ignore[assignment]
    text_lines: list[str] = None  # type: ignore[assignment]
    text_line_count: int = 0

    def __post_init__(self) -> None:
        if self.span is None:
            self.span = []
        if self.text_lines is None:
            self.text_lines = []


class ScriptBlockBuilder:
    """Builder genérico para blocos de texto com comandos intermediários.

    Padrão:
    - pending_prefix: linhas de comando (tag-only/@cmd) entre falas
    - bloco começa na primeira linha de texto (ou na linha com terminador)
    - bloco termina quando encontrar um terminador (ex: [r]/[cr])
    - span guarda informações para rebuild seguro
    """

    def __init__(self) -> None:
        self.pending_prefix: list[SpanItem] = []
        self.block = BlockState()

    def feed_prefix_line(self, *, line_index: int, raw: str) -> None:
        self.pending_prefix.append({"kind": "raw", "line_index": line_index, "raw": raw})

    def _start_block(self, start_line: int) -> None:
        if self.block.start_line is None:
            self.block.start_line = start_line
            if self.pending_prefix:
                self.block.span.extend(self.pending_prefix)
                self.pending_prefix = []

    def feed_text_mid(self, *, line_index: int, raw_line: str) -> None:
        lead, rest = split_leading_ws(raw_line)
        self._start_block(line_index)
        self.block.span.append(
            {
                "kind": "text_mid",
                "line_index": line_index,
                "prefix": lead,
                "suffix": "\n" if raw_line.endswith("\n") else "",
            }
        )
        self.block.text_lines.append(rest.rstrip("\n"))
        self.block.text_line_count += 1

    def feed_text_end(self, *, line_index: int, prefix: str, body: str, suffix: str) -> None:
        self._start_block(line_index)
        self.block.span.append(
            {
                "kind": "text",
                "line_index": line_index,
                "prefix": prefix,
                "suffix": suffix,
            }
        )
        self.block.text_lines.append(body.rstrip("\n"))
        self.block.text_line_count += 1

    def flush_entry(
        self,
        *,
        end_line: int,
        speaker: str = "",
        status: str = "untranslated",
        extra_meta: dict[str, Any] | None = None,
    ) -> EntryDict | None:
        if self.block.start_line is None:
            self.block = BlockState()
            return None

        original = "\n".join(self.block.text_lines).rstrip("\n")
        if not is_translatable_text(original):
            self.block = BlockState()
            return None

        meta = {
            "start_line": self.block.start_line,
            "end_line": end_line,
            "text_line_count": self.block.text_line_count,
            "span": self.block.span,
        }
        if extra_meta:
            meta.update(extra_meta)

        e = make_entry(
            entry_id=f"{self.block.start_line}-{end_line}",
            original=original,
            translation="",
            status=status,
            is_translatable=True,
            speaker=speaker,
            meta=meta,
        )

        self.block = BlockState()
        return e
