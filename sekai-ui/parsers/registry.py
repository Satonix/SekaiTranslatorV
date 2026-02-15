from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Any


@dataclass(frozen=True)
class RegisteredParser:
    plugin: Any  
    source: str  


class ParserRegistry:
    """
    Registro em memória dos parsers carregados.

    Regras:
    - plugin_id é obrigatório e normalizado (strip/lower)
    - Se houver conflito de plugin_id:
        external sobrescreve builtin
        external sobrescreve external (último vence)
        builtin NÃO sobrescreve external
    - Valida atributos básicos para evitar plugin quebrado derrubar o app
    """

    def __init__(self) -> None:
        self._by_id: Dict[str, RegisteredParser] = {}

    @staticmethod
    def _norm_id(pid: str) -> str:
        return (pid or "").strip().lower()

    def register(self, plugin: Any, source: str) -> None:
        if plugin is None:
            raise ValueError("plugin is required")

        pid_raw = getattr(plugin, "plugin_id", "") or ""
        pid = self._norm_id(pid_raw)
        if not pid:
            raise ValueError("Parser plugin_id is required")

        
        for attr in ("detect", "parse", "rebuild"):
            fn = getattr(plugin, attr, None)
            if not callable(fn):
                raise ValueError(f"Parser '{pid}' missing callable '{attr}()'")

        
        exts = getattr(plugin, "extensions", None)
        if exts is None:
            try:
                setattr(plugin, "extensions", set())
            except Exception:
                pass
        else:
            try:
                norm_exts = {str(e).lower() for e in exts if str(e).strip()}
                setattr(plugin, "extensions", set(norm_exts))
            except Exception:
                
                pass

        
        existing = self._by_id.get(pid)
        if existing is not None:
            if existing.source == "external" and source != "external":
                
                return

        self._by_id[pid] = RegisteredParser(plugin=plugin, source=source)

    def all(self) -> List[RegisteredParser]:
        
        items = list(self._by_id.items())
        items.sort(key=lambda kv: (0 if kv[1].source == "external" else 1, kv[0]))
        return [rp for _, rp in items]

    def get(self, plugin_id: str) -> Optional[RegisteredParser]:
        return self._by_id.get(self._norm_id(plugin_id))

    def ids(self) -> List[str]:
        return [rp_id for rp_id in self._by_id.keys()]
