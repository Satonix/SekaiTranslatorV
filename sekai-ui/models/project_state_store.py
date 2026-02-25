from __future__ import annotations

import json
import os
import re
import hashlib
import tempfile
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FileState:
    """
    Estado persistido por arquivo:
    - entries: lista de dicts do core (com translation/status/etc.)
    - encoding: encoding detectado/usado ao ler o arquivo original
    - newline_style: "\r\n" ou "\n" detectado no arquivo original
    - had_bom: se o arquivo original tinha BOM (útil para round-trip)
    """
    file_path: str
    entries: list[dict]
    encoding: str = ""
    newline_style: str = ""
    had_bom: bool = False


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _safe_relpath(root: str, path: str) -> str:
    try:
        rel = os.path.relpath(path, root)
    except Exception:
        rel = os.path.basename(path)
    # normaliza separadores para virar chave estável no Windows
    rel = rel.replace("\\", "/")
    return rel


def _appdata_base_dir() -> str:
    """
    Base única no sistema (não dentro do project_path).
    """
    base = os.environ.get("LOCALAPPDATA", "")
    app_name = "SekaiTranslatorV"

    # Se existir version.APP_NAME, usa ele para manter consistente com o app
    try:
        from version import APP_NAME as _APP_NAME
        app_name = (_APP_NAME or app_name).strip() or app_name
    except Exception:
        pass

    if base:
        return os.path.join(base, app_name)

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
    E adiciona hash curto do (project_path|root_path|name) para evitar colisões.
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
    %LOCALAPPDATA%/<APP_NAME>/ProjectStates/<project_key>/
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


def _atomic_write_json(path: str, payload: dict) -> None:
    d = os.path.dirname(path) or "."
    _ensure_dir(d)

    fd, tmp = tempfile.mkstemp(prefix=".tmp_", dir=d, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)  # atomic no Windows
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass


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

    encoding = (data.get("encoding") or "").strip()
    newline_style = (data.get("newline_style") or "").strip()
    had_bom = bool(data.get("had_bom") or False)

    return FileState(
        file_path=file_path,
        entries=entries,
        encoding=encoding,
        newline_style=newline_style,
        had_bom=had_bom,
    )


def save_file_state(
    project: dict,
    file_path: str,
    entries: list[dict],
    *,
    encoding: str = "",
    newline_style: str = "",
    had_bom: bool = False,
) -> None:
    p = state_path_for_file(project, file_path)

    payload = {
        "file_path": file_path,
        "entries": entries,
        "encoding": (encoding or "").strip(),
        "newline_style": (newline_style or "").strip(),
        "had_bom": bool(had_bom),
    }

    _atomic_write_json(p, payload)