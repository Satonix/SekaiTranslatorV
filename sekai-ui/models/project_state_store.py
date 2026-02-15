from __future__ import annotations

import json
import os
import re
import hashlib
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FileState:
    """
    Estado persistido por arquivo:
    - entries: lista de dicts do core (com translation/status/etc.)
    """
    file_path: str
    entries: list[dict]


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _safe_relpath(root: str, path: str) -> str:
    try:
        rel = os.path.relpath(path, root)
    except Exception:
        rel = os.path.basename(path)
    rel = rel.replace("\\", "/")
    return rel


def _appdata_base_dir() -> str:
    """
    Base única no sistema (não dentro do project_path).
    """
    base = os.environ.get("LOCALAPPDATA", "")
    if base:
        return os.path.join(base, "SekaiTranslator")
    return os.path.abspath(os.path.join(".", ".sekai_local"))


def _sanitize_component(s: str) -> str:
    """
    Sanitiza para virar nome de pasta seguro no Windows.
    """
    s = (s or "").strip()
    if not s:
        return "Project"
    s = re.sub(r"[^\w\-. ]+", "_", s, flags=re.UNICODE)
    s = s.strip().strip(".")
    return s or "Project"


def _project_key(project: dict) -> str:
    """
    Gera um identificador estável para o projeto, sem usar path absoluto como nome.
    Usa:
    - basename do project_path (normalmente o nome da pasta do projeto)
    - fallback: project.name
    E adiciona hash curto do (project_path|root_path) para evitar colisões.
    """
    project_path = (project.get("project_path") or "").strip()
    root_path = (project.get("root_path") or "").strip()
    display_name = (project.get("name") or "").strip()

    base_name = ""
    if project_path:
        base_name = os.path.basename(project_path.rstrip("\\/"))
    if not base_name:
        base_name = display_name or "Project"

    base_name = _sanitize_component(base_name)

    seed = project_path or root_path or display_name or base_name
    h = hashlib.sha1(seed.encode("utf-8", errors="ignore")).hexdigest()[:8]

    return f"{base_name}_{h}"


def state_root(project: dict) -> str:
    """
    Pasta única de estado no sistema:
    %LOCALAPPDATA%/SekaiTranslator/ProjectStates/<project_key>/
    """
    base = _appdata_base_dir()
    return os.path.join(base, "ProjectStates", _project_key(project))


def state_path_for_file(project: dict, file_path: str) -> str:
    """
    Salva como JSON espelhando a árvore do root_path.
    ex.: script/scene01.ks -> script/scene01.ks.json
    """
    root = project.get("root_path") or ""
    rel = _safe_relpath(root, file_path)

    return os.path.join(state_root(project), rel + ".json")


def load_file_state(project: dict, file_path: str) -> FileState | None:
    p = state_path_for_file(project, file_path)
    if not os.path.exists(p):
        return None

    try:
        with open(p, "r", encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
    except Exception:
        return None

    entries = data.get("entries")
    if not isinstance(entries, list):
        return None

    return FileState(file_path=file_path, entries=entries)


def save_file_state(project: dict, file_path: str, entries: list[dict]) -> None:
    p = state_path_for_file(project, file_path)
    _ensure_dir(os.path.dirname(p))

    payload = {
        "file_path": file_path,
        "entries": entries,
    }

    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
