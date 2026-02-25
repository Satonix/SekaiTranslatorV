from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RepoStatus:
    present: bool
    repo_dir: str
    src_dir: str


def _appdata_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        base = os.path.join(os.path.expanduser("~"), ".sekaitranslatorv")
    return Path(base) / "SekaiTranslatorV"


def _legacy_appdata_dir() -> Path:
    """Compat: caminho antigo usado antes da correção."""
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        base = os.path.join(os.path.expanduser("~"), ".sekaitranslatorv")
    return Path(base) / "SekaiTranslatorV"


class ParsersRepository:
    """
    Repo de parsers (Opção A).

    O repositório remoto é um pacote Python com:
        <repo>/src/sekai_parsers

    O app clona/atualiza com git e adiciona <repo>/src ao sys.path para:
        import sekai_parsers
    """

    def __init__(self, repo_url: str, branch: str | None = None):
        self.repo_url = (repo_url or "").strip()
        self.branch = (branch or "").strip() or None

        # ✅ Caminho novo (padrão)
        #   %LOCALAPPDATA%\SekaiTranslatorV\parsers_repo
        self._repo_dir: Path = _appdata_dir() / "parsers_repo"

        # Caminhos antigos (compat / migração)
        self._legacy_repo_dirs: list[Path] = [
            _appdata_dir() / "parsers" / "repo",                 # SekaiTranslatorV\parsers\repo
                                ]

    # ------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------

    def repo_dir(self) -> str:
        return str(self._repo_dir)

    def src_dir(self) -> str:
        return str(self._repo_dir / "src")

    def status(self) -> RepoStatus:
        present = (self._repo_dir / ".git").is_dir()
        return RepoStatus(present=present, repo_dir=self.repo_dir(), src_dir=self.src_dir())

    # ------------------------------------------------------------
    # Git
    # ------------------------------------------------------------

    def _run_git(self, args: list[str]) -> None:
        try:
            proc = subprocess.run(
                ["git", *args],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except FileNotFoundError as e:
            raise RuntimeError("git não encontrado no PATH") from e

        if proc.returncode != 0:
            out = (proc.stdout or "").strip()
            raise RuntimeError(out or "falha ao executar git")

    def _maybe_migrate_legacy_repo(self) -> None:
        """
        Se existir um repo antigo em algum caminho legado e o novo ainda não existir,
        tenta migrar (move) para o caminho novo.
        """
        try:
            if (self._repo_dir / ".git").is_dir():
                return

            legacy_found: Path | None = None
            for p in self._legacy_repo_dirs:
                if (p / ".git").is_dir():
                    legacy_found = p
                    break

            if not legacy_found:
                return

            self._repo_dir.parent.mkdir(parents=True, exist_ok=True)

            # Se destino existir com lixo, remove.
            if self._repo_dir.is_dir():
                try:
                    if any(self._repo_dir.iterdir()):
                        shutil.rmtree(self._repo_dir, ignore_errors=True)
                except Exception:
                    pass

            shutil.move(str(legacy_found), str(self._repo_dir))
        except Exception:
            # best-effort
            pass

    def ensure_repo(self) -> None:
        if not self.repo_url:
            raise RuntimeError("repo_url não configurado")

        self._maybe_migrate_legacy_repo()
        self._repo_dir.parent.mkdir(parents=True, exist_ok=True)

        git_dir = self._repo_dir / ".git"
        if not git_dir.is_dir():
            # limpa se houver lixo
            if self._repo_dir.is_dir():
                try:
                    if any(self._repo_dir.iterdir()):
                        shutil.rmtree(self._repo_dir, ignore_errors=True)
                except Exception:
                    pass

            self._repo_dir.mkdir(parents=True, exist_ok=True)

            clone_args = ["clone", "--depth", "1"]
            if self.branch:
                clone_args += ["--branch", self.branch]
            clone_args += [self.repo_url, str(self._repo_dir)]
            self._run_git(clone_args)
            return

        # atualiza (HEAD remoto)
        self._run_git(["-C", str(self._repo_dir), "fetch", "--all", "--prune"])
        self._run_git(["-C", str(self._repo_dir), "reset", "--hard", "origin/HEAD"])

    # ------------------------------------------------------------
    # Import
    # ------------------------------------------------------------

    def ensure_importable(self) -> RepoStatus:
        """Clona/atualiza e adiciona <repo>/src ao sys.path."""
        self.ensure_repo()
        src = self._repo_dir / "src"
        if src.is_dir():
            src_str = str(src)
            if src_str not in sys.path:
                sys.path.insert(0, src_str)
        return self.status()