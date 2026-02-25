from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class ParseContext:
    """
    Contexto do parse/rebuild no UI (sekai-ui).

    OPÇÃO A:
    - original_text SEMPRE contém o texto bruto original do arquivo.
    - Parsers estruturais (ex: Artemis) usam isso para rebuild seguro.
    """
    project: dict
    file_path: str
    original_text: str

    # Campos opcionais para facilitar parsers mais robustos.
    # Mantidos com defaults para não quebrar chamadas existentes.
    encoding: str = ""
    options: dict[str, Any] = field(default_factory=dict)

    @property
    def path(self) -> Path:
        return Path(self.file_path)

    def splitlines(self, *, keepends: bool = True) -> list[str]:
        """Convenience: acesso consistente ao texto original em linhas."""
        return self.original_text.splitlines(keepends=keepends)


class ParserPlugin(Protocol):
    """
    Interface que um parser-plugin deve implementar.
    """

    plugin_id: str

    name: str

    extensions: set[str]

    def detect(self, ctx: ParseContext, text: str) -> float:
        """
        Retorna score [0..1] indicando quão provável este parser
        servir para este arquivo.
        """
        ...

    def parse(self, ctx: ParseContext, text: str) -> list[dict]:
        """
        Converte o texto bruto em entries para o editor.
        Normalmente: text == ctx.original_text
        """
        ...

    def rebuild(self, ctx: ParseContext, entries: list[dict]) -> str:
        """
        Reconstrói o arquivo final.

        IMPORTANTE:
        - Para parsers estruturais, use ctx.original_text como base
        - Nunca tente reconstruir o arquivo inteiro só a partir das entries
        """
        ...


class ParserError(RuntimeError):
    pass
