from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from .manager import get_parser_manager
from .repository import (
    RepoSpec,
    install_or_update_repo as _install_or_update_repo,
    is_repo_installed,
    list_remote_parsers,
    install_parser_from_repo as _install_parser_from_repo,
    remove_installed_parser as _remove_installed_parser,
)


def _default_spec() -> RepoSpec:
    return RepoSpec(
        repo_url="https://github.com/Satonix/SekaiTranslator-Parsers",
        branch="main",
    )


def update_repo_from_github(spec: Optional[RepoSpec] = None) -> dict:
    spec = spec or _default_spec()
    _install_or_update_repo(spec)
    return {
        "repo_installed": is_repo_installed(),
        "spec": asdict(spec),
    }


def install_or_update_repo(spec: Optional[RepoSpec] = None) -> dict:
    return update_repo_from_github(spec)


def install_parser(folder: str, spec: Optional[RepoSpec] = None) -> dict:
    spec = spec or _default_spec()
    if not is_repo_installed():
        _install_or_update_repo(spec)
    _install_parser_from_repo(folder)
    return {"ok": True, "folder": folder, "repo_installed": is_repo_installed(), "spec": asdict(spec)}


def list_parsers(spec: Optional[RepoSpec] = None) -> dict:
    spec = spec or _default_spec()

    pm = get_parser_manager(force_reload=True)
    installed = []
    for p in pm.registry.all():
        plug = getattr(p, "plugin", None)
        installed.append(
            {
                "plugin_id": getattr(plug, "plugin_id", ""),
                "name": getattr(plug, "name", ""),
                "extensions": sorted(list(getattr(plug, "extensions", set()) or [])),
                "is_builtin": bool(getattr(p, "is_builtin", False)),
                "folder": getattr(p, "folder", ""),
            }
        )

    available = []
    try:
        available = list_remote_parsers(spec.repo_url, branch=spec.branch)
    except Exception:
        available = []

    return {
        "repo_installed": is_repo_installed(),
        "spec": asdict(spec),
        "installed": installed,
        "available": available,
    }


def remove_external_parser(parser_folder_or_id: str) -> bool:
    return _remove_installed_parser(parser_folder_or_id)
