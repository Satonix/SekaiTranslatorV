from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any


def _slugify(name: str) -> str:
    s = (name or "").strip().lower()
    s = re.sub(r"[^a-z0-9\-_ ]+", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    return s or "project"


def _default_base_dir(app_name: str = "SekaiTranslatorV") -> str:
    r"""
    Storage location for projects on Windows:
      %LOCALAPPDATA%\<app_name>\projects

    Fallbacks:
      %APPDATA%\<app_name>\projects
      ~/.sekai/<app_name>/projects
    """
    local = (os.environ.get("LOCALAPPDATA") or "").strip()
    if local:
        return os.path.join(local, app_name, "projects")

    roaming = (os.environ.get("APPDATA") or "").strip()
    if roaming:
        return os.path.join(roaming, app_name, "projects")

    return os.path.join(os.path.expanduser("~"), ".sekai", app_name, "projects")


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _read_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f) if f else {}


def _atomic_write_json(path: str, data: dict) -> None:
    """
    Atomic write: writes to a temp file and replaces.
    Prevents partial/corrupted saves and makes failures visible.
    """
    folder = os.path.dirname(path)
    _ensure_dir(folder)

    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data or {}, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp, path)


# ----------------------------
# Export encoding normalization
# ----------------------------
_EXPORT_LABEL_TO_VALUE: dict[str, tuple[str, bool]] = {
    "UTF-8": ("utf-8", False),
    "UTF-8 (com BOM)": ("utf-8", True),
    "UTF-16 LE (com BOM)": ("utf-16-le", True),
    "UTF-16 LE (sem BOM)": ("utf-16-le", False),
    "UTF-16 BE (com BOM)": ("utf-16-be", True),
    "UTF-16 BE (sem BOM)": ("utf-16-be", False),
    "Windows-1252": ("windows-1252", False),
    "Shift_JIS (CP932)": ("cp932", False),
}


def _normalize_export_settings(project: dict) -> dict:
    if not isinstance(project, dict):
        return project

    exp_raw = str(project.get("export_encoding") or "").strip()
    bom_raw = project.get("export_bom", None)

    if exp_raw in _EXPORT_LABEL_TO_VALUE:
        enc, bom = _EXPORT_LABEL_TO_VALUE[exp_raw]
        project["export_encoding"] = enc
        project["export_bom"] = bom
        return project

    if exp_raw.lower() == "utf-16":
        project["export_encoding"] = "utf-16-le"
        project["export_bom"] = True if bom_raw is None else bool(bom_raw)
        return project

    if not exp_raw:
        project["export_encoding"] = "utf-8"
        project["export_bom"] = False
        return project

    if bom_raw is None:
        project["export_bom"] = False

    return project


def _normalize_project_path_value(p: str) -> str:
    """
    Accepts:
      - directory path
      - path to project.json
    Returns:
      - absolute directory path containing project.json
    """
    p = (p or "").strip()
    if not p:
        return ""
    p = os.path.abspath(p)
    if os.path.isdir(p):
        return p
    if p.lower().endswith("project.json"):
        return os.path.dirname(p)
    # if a file path is accidentally passed, use its folder
    if os.path.isfile(p):
        return os.path.dirname(p)
    # fallback: if it looks like a dir (no extension), keep it
    return p


@dataclass(frozen=True, slots=True)
class LocalProjectInfo:
    name: str
    project_path: str


class LocalProjectService:
    """
    UI-side project persistence.
    """

    def __init__(self, *, app_name: str = "SekaiTranslatorV", base_dir: str | None = None):
        self.app_name = (app_name or "SekaiTranslatorV").strip() or "SekaiTranslatorV"
        self.base_dir = (base_dir or _default_base_dir(self.app_name)).strip()

    def list_projects(self) -> list[dict]:
        _ensure_dir(self.base_dir)
        out: list[dict] = []
        for entry in sorted(os.listdir(self.base_dir)):
            pdir = os.path.join(self.base_dir, entry)
            pj = os.path.join(pdir, "project.json")
            if not os.path.isdir(pdir) or not os.path.isfile(pj):
                continue
            try:
                data = _read_json(pj)
                name = (data.get("name") or entry).strip() or entry
                out.append({"name": name, "project_path": pdir, "root_path": data.get("root_path", "")})
            except Exception:
                continue
        out.sort(key=lambda d: (d.get("name") or "").lower())
        return out

    def create_project(self, payload: dict) -> dict:
        name = (payload.get("name") or "").strip()
        root = (payload.get("game_root") or payload.get("root_path") or "").strip()
        if not name or not root:
            raise ValueError("name e game_root são obrigatórios")

        slug = _slugify(name)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        pdir = os.path.join(self.base_dir, f"{slug}-{stamp}")
        _ensure_dir(pdir)

        export_encoding = (payload.get("export_encoding") or "utf-8").strip() or "utf-8"
        export_bom = bool(payload.get("export_bom", False))

        project: dict[str, Any] = {
            "project_path": pdir,
            "name": name,
            "root_path": root,
            "encoding": "auto",
            "export_encoding": export_encoding,
            "export_bom": export_bom,
            "engine": (payload.get("engine") or "").strip(),
            "parser_id": (payload.get("parser_id") or "").strip(),
            "source_language": (payload.get("source_language") or "").strip(),
            "target_language": (payload.get("target_language") or "pt-BR").strip() or "pt-BR",
            "ai_prompt_preset": (payload.get("ai_prompt_preset") or "default").strip() or "default",
            "ai_custom_prompt_text": (payload.get("ai_custom_prompt_text") or "").strip(),
        }

        project = _normalize_export_settings(project)
        pj = os.path.join(pdir, "project.json")
        _atomic_write_json(pj, project)

        # verify
        verify = _read_json(pj)
        if not isinstance(verify, dict) or not verify.get("name"):
            raise IOError("Falha ao gravar project.json (verificação inválida).")

        return project

    def open_project(self, project_path: str) -> dict:
        pdir = _normalize_project_path_value(project_path)
        if not pdir:
            raise ValueError("project_path vazio")

        pj = os.path.join(pdir, "project.json")
        if not os.path.isfile(pj):
            raise FileNotFoundError("project.json não encontrado")

        project = _read_json(pj)

        project["project_path"] = pdir
        project.setdefault("encoding", "auto")
        if not project.get("target_language"):
            project["target_language"] = "pt-BR"

        project = _normalize_export_settings(project)

        return project

    def save_project(self, project: dict) -> dict:
        if not isinstance(project, dict):
            raise ValueError("project inválido")

        # normalize project_path aggressively
        pdir = _normalize_project_path_value(project.get("project_path") or "")
        if not pdir:
            raise ValueError("project_path ausente/ inválido")
        project["project_path"] = pdir

        pj = os.path.join(pdir, "project.json")

        # enforce invariant: input encoding is per-file
        project["encoding"] = "auto"

        # normalize export settings (and fix if UI label leaked in)
        project = _normalize_export_settings(project)

        # write + verify
        _atomic_write_json(pj, project)

        try:
            after = _read_json(pj)
        except Exception as e:
            raise IOError(f"Falha ao ler de volta project.json após salvar: {e}")

        if not isinstance(after, dict):
            raise IOError("Falha ao ler de volta project.json após salvar (tipo inválido).")

        # garantir campos essenciais/paths
        after["project_path"] = pdir
        after["encoding"] = "auto"
        if not after.get("target_language"):
            after["target_language"] = "pt-BR"

        # normaliza export settings no retorno também (garante consistência)
        after = _normalize_export_settings(after)

        # sanity: ensure critical fields persisted
        if str(after.get("name", "")).strip() != str(project.get("name", "")).strip():
            raise IOError("project.json não refletiu o novo 'name' após salvar (verificação falhou).")

        if str(after.get("export_encoding", "")).strip().lower() != str(project.get("export_encoding", "")).strip().lower():
            raise IOError("project.json não refletiu o novo 'export_encoding' após salvar (verificação falhou).")

        if bool(after.get("export_bom", False)) != bool(project.get("export_bom", False)):
            raise IOError("project.json não refletiu o novo 'export_bom' após salvar (verificação falhou).")

        # ✅ retorno deve ser o estado REAL persistido
        return after