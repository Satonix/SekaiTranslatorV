from __future__ import annotations

import os
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen


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
    Repo de parsers (sem Git).

    O repositório remoto é um pacote Python com:
        <repo>/src/sekai_parsers

    O app baixa sempre o ZIP da branch main e extrai em:
        %LOCALAPPDATA%\\SekaiTranslatorV\\parsers_repo

    Depois adiciona <repo>/src ao sys.path para:
        import sekai_parsers
    """

    def __init__(self, repo_url: str, branch: str | None = None):
        self.repo_url = (repo_url or "").strip()
        # branch ignorada: sempre main
        self.branch = "main"

        # ✅ Caminho novo (padrão)
        #   %LOCALAPPDATA%\\SekaiTranslatorV\\parsers_repo
        self._repo_dir: Path = _appdata_dir() / "parsers_repo"

        # Caminhos antigos (compat / migração)
        self._legacy_repo_dirs: list[Path] = [
            _appdata_dir() / "parsers" / "repo",  # SekaiTranslatorV\\parsers\\repo
        ]

    # ------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------

    def repo_dir(self) -> str:
        return str(self._repo_dir)

    def src_dir(self) -> str:
        return str(self._repo_dir / "src")

    def status(self) -> RepoStatus:
        present = (self._repo_dir / "src" / "sekai_parsers").is_dir()
        return RepoStatus(present=present, repo_dir=self.repo_dir(), src_dir=self.src_dir())

    # ------------------------------------------------------------
    # Legacy migration
    # ------------------------------------------------------------

    def _maybe_migrate_legacy_repo(self) -> None:
        """
        Se existir um repo antigo em algum caminho legado e o novo ainda não existir,
        tenta migrar (move) para o caminho novo.
        """
        try:
            if (self._repo_dir / "src" / "sekai_parsers").is_dir():
                return

            legacy_found: Path | None = None
            for p in self._legacy_repo_dirs:
                if (p / "src" / "sekai_parsers").is_dir():
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

    # ------------------------------------------------------------
    # Download ZIP (main)
    # ------------------------------------------------------------

    def _zip_url_for_main(self) -> str:
        """
        Converte repo_url do GitHub para URL do zip da main.
        Aceita:
          - https://github.com/OWNER/REPO
          - https://github.com/OWNER/REPO.git
        Retorna:
          - https://github.com/OWNER/REPO/archive/refs/heads/main.zip
        """
        url = (self.repo_url or "").strip()
        if not url:
            raise RuntimeError("repo_url não configurado")

        if url.endswith(".git"):
            url = url[:-4]

        url = url.rstrip("/")

        if "github.com/" not in url:
            raise RuntimeError("repo_url não é um link do GitHub suportado")

        return f"{url}/archive/refs/heads/main.zip"

    def _download_zip(self, zip_url: str, out_path: Path) -> None:
        req = Request(zip_url, headers={"User-Agent": "SekaiTranslatorV"})
        with urlopen(req, timeout=60) as resp:
            out_path.write_bytes(resp.read())

    def ensure_repo(self) -> None:
        if not self.repo_url:
            raise RuntimeError("repo_url não configurado")

        self._maybe_migrate_legacy_repo()
        self._repo_dir.parent.mkdir(parents=True, exist_ok=True)

        zip_url = self._zip_url_for_main()

        # Baixa/extrai em temp e depois substitui a pasta inteira.
        with tempfile.TemporaryDirectory(prefix="sekai_parsers_") as td:
            td_path = Path(td)
            zip_path = td_path / "repo.zip"
            extract_dir = td_path / "extract"
            extract_dir.mkdir(parents=True, exist_ok=True)

            self._download_zip(zip_url, zip_path)

            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)

            roots = [p for p in extract_dir.iterdir() if p.is_dir()]
            if not roots:
                raise RuntimeError("ZIP inválido: sem pasta raiz extraída")

            extracted_root = roots[0]
            if not (extracted_root / "src" / "sekai_parsers").is_dir():
                raise RuntimeError("ZIP inválido: não encontrei src/sekai_parsers")

            # ------------------------------------------------------------
            # Substituição robusta no Windows (evita WinError 183)
            # ------------------------------------------------------------

            import os

            dst = self._repo_dir
            tmp_dst = dst.with_name(dst.name + ".new")
            bak_dst = dst.with_name(dst.name + ".bak")

            # Limpa sobras antigas
            shutil.rmtree(tmp_dst, ignore_errors=True)
            shutil.rmtree(bak_dst, ignore_errors=True)

            # Copia para pasta temporária (.new)
            shutil.copytree(extracted_root, tmp_dst)

            # Troca atômica
            if dst.exists():
                try:
                    os.replace(dst, bak_dst)  # move dst -> bak
                except Exception:
                    shutil.rmtree(dst, ignore_errors=True)

            os.replace(tmp_dst, dst)  # move new -> final

            # Remove backup (best-effort)
            shutil.rmtree(bak_dst, ignore_errors=True)

    # ------------------------------------------------------------
    # Import
    # ------------------------------------------------------------

    def ensure_importable(self) -> RepoStatus:
        """Baixa/atualiza e adiciona <repo>/src ao sys.path."""
        self.ensure_repo()
        src = self._repo_dir / "src"
        if src.is_dir():
            src_str = str(src)
            if src_str not in sys.path:
                sys.path.insert(0, src_str)
        return self.status()