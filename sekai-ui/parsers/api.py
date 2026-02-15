from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .manager import get_parser_manager, reload_parsers
from .repository import RepoSpec, install_or_update_repo, is_repo_installed, get_installed_parser_ids


def list_parsers() -> dict:
    """
    Retorna infos dos parsers carregados (builtin/external) para UI.
    Não faz download. Só lista o que está disponível no disco e carregado pelo manager.
    """
    mgr = get_parser_manager()

    items: list[dict[str, Any]] = []
    for rp in mgr.registry.all():
        p = rp.plugin
        items.append(
            {
                "plugin_id": (getattr(p, "plugin_id", "") or "").strip(),
                "name": (getattr(p, "name", "") or "").strip(),
                "extensions": sorted({str(e).lower() for e in (getattr(p, "extensions", None) or set())}),
                "source": rp.source,
            }
        )

    return {
        "repo_installed": bool(is_repo_installed()),
        "repo_folders": get_installed_parser_ids(),
        "parsers": sorted(items, key=lambda x: (x["source"], x["plugin_id"])),
    }


def update_repo_from_github(
    *,
    owner: str = "Satonix",
    name: str = "SekaiTranslator-Parsers",
    branch: str = "main",
    timeout: float = 60.0,
) -> dict:
    """
    Baixa/atualiza o repo de parsers e recarrega o manager.
    """
    spec = RepoSpec(owner=owner, name=name, branch=branch)
    installed = install_or_update_repo(spec=spec, timeout=timeout)

    reload_parsers()

    return {
        "status": "ok",
        "installed": int(installed),
        "repo": asdict(spec),
    }
