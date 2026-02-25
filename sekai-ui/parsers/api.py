from __future__ import annotations

import os
import sys
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


DEFAULT_REPO_URL = "https://github.com/Satonix/SekaiTranslatorVParsers.git"


def _appdata_repo_dir() -> Path:
    # %LOCALAPPDATA%\SekaiTranslatorV\parsers_repo
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(base) / "SekaiTranslatorV" / "parsers_repo"


def _src_dir(repo_dir: Path) -> Path:
    return repo_dir / "src"


def _ensure_on_syspath(path: Path) -> None:
    p = str(path.resolve())
    if p not in sys.path:
        sys.path.insert(0, p)


def _run_git(args: list[str], cwd: Optional[Path] = None) -> None:
    cmd = ["git", *args]
    try:
        subprocess.check_call(cmd, cwd=str(cwd) if cwd else None)
    except FileNotFoundError as e:
        raise RuntimeError(
            "Git não encontrado. Instale o Git e garanta que 'git' está no PATH."
        ) from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Falha ao executar git: {' '.join(cmd)}") from e


def update_repo_from_github(repo_url: str | None = None, repo_dir: Path | None = None) -> Path:
    repo_url = (repo_url or DEFAULT_REPO_URL).strip()
    repo_dir = repo_dir or _appdata_repo_dir()
    repo_dir.parent.mkdir(parents=True, exist_ok=True)

    if (repo_dir / ".git").is_dir():
        _run_git(["pull", "--ff-only"], cwd=repo_dir)
    else:
        if repo_dir.exists() and any(repo_dir.iterdir()):
            # pasta existe e não está vazia
            raise RuntimeError(f"Diretório de repo já existe e não é um git repo: {repo_dir}")
        _run_git(["clone", repo_url, str(repo_dir)])

    # garante import pelo "src/"
    _ensure_on_syspath(_src_dir(repo_dir))
    return repo_dir


def list_parsers(*args: Any, **kwargs: Any):
    # compat com imports antigos: "from parsers.api import list_parsers"
    api = ParsersAPI(repo_url=kwargs.pop("repo_url", None))
    return api.list_available()


@dataclass
class ParsersAPI:
    """
    API usada pela UI (PluginManagerDialog).
    Mantém compat com chamadas antigas:
      - ParsersAPI(repo_url=...)
      - .list_available()
      - .update_repo()
      - .update_repo_from_github()
      - .list_parsers()
    """
    repo_url: Optional[str] = None
    repo_dir: Optional[Path] = None

    def __post_init__(self) -> None:
        if self.repo_dir is None:
            self.repo_dir = _appdata_repo_dir()
        if not self.repo_url:
            self.repo_url = DEFAULT_REPO_URL

    def update_repo_from_github(self) -> Path:
        return update_repo_from_github(self.repo_url, self.repo_dir)

    # alias esperado por partes da UI antiga
    def update_repo(self) -> Path:
        return self.update_repo_from_github()

    def _import_sekai_parsers(self):
        # tenta atualizar/garantir path primeiro (se repo ainda não existe)
        if not (_src_dir(self.repo_dir) / "sekai_parsers").exists():
            self.update_repo_from_github()
        else:
            _ensure_on_syspath(_src_dir(self.repo_dir))

        try:
            import sekai_parsers  # type: ignore
            return sekai_parsers
        except Exception as e:
            raise RuntimeError(f"Falha ao importar sekai_parsers do repo: {e}") from e

    def list_available(self):
        sp = self._import_sekai_parsers()

        # preferível: sekai_parsers.list_engines() -> list[str]
        fn = getattr(sp, "list_engines", None)
        if callable(fn):
            engines = fn() or []
            # UI espera list[dict]
            if engines and isinstance(engines[0], str):
                return [
                    {
                        "id": eid,
                        "name": eid,
                        "version": "",
                        "description": "",
                        "extensions": [],
                    }
                    for eid in engines
                ]
            return engines

        # fallback: tentar registry diretamente
        reg = getattr(sp, "registry", None)
        if reg is not None:
            fn2 = getattr(reg, "list_engines", None)
            if callable(fn2):
                engines = fn2() or []
                if engines and isinstance(engines[0], str):
                    return [
                        {
                            "id": eid,
                            "name": eid,
                            "version": "",
                            "description": "",
                            "extensions": [],
                        }
                        for eid in engines
                    ]
                return engines

        return []


    # alias esperado por partes da UI antiga
    def list_parsers(self):
        return self.list_available()
