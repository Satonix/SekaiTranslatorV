from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

from .loader import load_plugin_from_plugin_py
from .registry import ParserRegistry
from .repository import repo_dir, parsers_base_dir


def external_parsers_dir() -> Path:
    """
    Pasta onde os parsers externos ficam instalados.

    Padrão (novo):
      %LOCALAPPDATA%\\SekaiTranslator\\Parsers\\repo\\<parser>\\plugin.py

    Compat (legado):
      %LOCALAPPDATA%\\SekaiTranslator\\Parsers\\<parser>\\plugin.py
    """
    return repo_dir()


def external_parsers_legacy_dir() -> Path:
    
    return parsers_base_dir() / "Parsers"


@dataclass
class ParserManager:
    registry: ParserRegistry

    def get(self, plugin_id: str) -> Optional[Any]:
        rp = self.registry.get(plugin_id)
        return rp.plugin if rp else None

    def all_plugins(self) -> List[Any]:
        return [rp.plugin for rp in self.registry.all()]


_MANAGER: ParserManager | None = None


def _discover_from_dir(reg: ParserRegistry, folder: Path, *, source: str, prefix: str) -> None:
    if not folder.exists():
        return

    for child in sorted(folder.iterdir()):
        if not child.is_dir():
            continue

        plugin_py = child / "plugin.py"
        if not plugin_py.exists():
            continue

        unique_name = f"{prefix}_{child.name}"
        try:
            plugin = load_plugin_from_plugin_py(plugin_py, unique_name=unique_name)
            reg.register(plugin, source=source)
        except Exception:
            
            continue


def get_parser_manager(force_reload: bool = False) -> ParserManager:
    global _MANAGER
    if _MANAGER is not None and not force_reload:
        return _MANAGER

    reg = ParserRegistry()

    
    _discover_from_dir(reg, external_parsers_dir(), source="external", prefix="sekai_parser_external")

    
    _discover_from_dir(reg, external_parsers_legacy_dir(), source="external", prefix="sekai_parser_external_legacy")

    _MANAGER = ParserManager(registry=reg)
    return _MANAGER


def reload_parsers() -> ParserManager:
    return get_parser_manager(force_reload=True)
