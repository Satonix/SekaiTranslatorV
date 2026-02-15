from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Optional


def _load_module_from_file(module_name: str, file_path: Path) -> ModuleType:
    """
    Carrega um módulo Python a partir de um arquivo .py.
    Usa um nome único para evitar colisões entre plugins.
    """
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module spec: {file_path}")

    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _looks_like_parser_plugin(obj: Any) -> bool:
    """
    Duck-typing da interface ParserPlugin.
    Não exige herança, só atributos/métodos.
    """
    if obj is None:
        return False

    pid = getattr(obj, "plugin_id", None)
    name = getattr(obj, "name", None)

    return (
        isinstance(pid, str)
        and bool(pid.strip())
        and isinstance(name, str)
        and bool(name.strip())
        and hasattr(obj, "extensions")
        and callable(getattr(obj, "detect", None))
        and callable(getattr(obj, "parse", None))
        and callable(getattr(obj, "rebuild", None))
    )


def _safe_instantiate(cls: Any) -> Optional[Any]:
    if not inspect.isclass(cls):
        return None
    try:
        return cls()
    except Exception:
        return None


def _plugin_from_module(mod: ModuleType) -> Optional[Any]:
    """
    Ordem de resolução:
    1) get_plugin()
    2) PLUGIN (instância)
    3) classes com nome comum: KirikiriKsPlugin, PlainTextPlugin, Plugin, Parser
    4) primeira classe no módulo que pareça plugin
    """
    gp = getattr(mod, "get_plugin", None)
    if callable(gp):
        try:
            p = gp()
            if _looks_like_parser_plugin(p):
                return p
        except Exception:
            pass

    inst = getattr(mod, "PLUGIN", None)
    if _looks_like_parser_plugin(inst):
        return inst

    preferred_class_names = (
        "KirikiriKsPlugin",
        "PlainTextPlugin",
        "Plugin",
        "Parser",
    )
    for name in preferred_class_names:
        cls = getattr(mod, name, None)
        obj = _safe_instantiate(cls)
        if _looks_like_parser_plugin(obj):
            return obj

    for _, cls in inspect.getmembers(mod, inspect.isclass):
        obj = _safe_instantiate(cls)
        if _looks_like_parser_plugin(obj):
            return obj

    return None


def load_plugin_from_plugin_py(plugin_py: str | Path, *, unique_name: str) -> Any:
    plugin_py = Path(plugin_py)
    if not plugin_py.exists():
        raise FileNotFoundError(str(plugin_py))

    unique_name = (unique_name or "sekai_parser").strip()
    if not unique_name:
        unique_name = "sekai_parser"

    mod = _load_module_from_file(unique_name, plugin_py)
    plugin = _plugin_from_module(mod)
    if plugin is None:
        raise RuntimeError(f"No parser plugin found in {plugin_py}")

    pid = (getattr(plugin, "plugin_id", "") or "").strip()
    if not pid:
        raise RuntimeError(f"plugin_id missing in {plugin_py}")

    exts = getattr(plugin, "extensions", None)
    try:
        if exts is None:
            plugin.extensions = set()
        else:
            plugin.extensions = {str(e).lower() for e in exts if str(e).strip()}
    except Exception:
        pass

    return plugin
