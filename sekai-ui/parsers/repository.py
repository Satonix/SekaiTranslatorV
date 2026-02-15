from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import os
import shutil
import tempfile
import zipfile
import urllib.request
import json
import hashlib

def parsers_base_dir() -> Path:
    """
    Base onde ficam os parsers externos.
    Padrão: %LOCALAPPDATA%/SekaiTranslator/Parsers
    """
    local = (os.environ.get("LOCALAPPDATA") or "").strip()
    if local:
        return Path(local) / "SekaiTranslator" / "Parsers"
    return Path.cwd() / "Parsers"


def repo_dir() -> Path:
    """
    Onde o repo baixado é instalado.
    Estrutura esperada pelo manager: <Parsers>/repo/<plugin_folder>/plugin.py
    """
    return parsers_base_dir() / "repo"


def ensure_dirs() -> None:
    repo_dir().mkdir(parents=True, exist_ok=True)



@dataclass(frozen=True)
class RepoSpec:
    """
    Especifica um repositório GitHub de parsers.

    Ex:
      RepoSpec(repo_url="https://github.com/Satonix/SekaiTranslator-Parsers", branch="main")
    """
    repo_url: str
    branch: str = "main"

    @property
    def zip_url(self) -> str:
        base = self.repo_url.rstrip("/")
        return f"{base}/archive/refs/heads/{self.branch}.zip"



def _download_to_file(url: str, out_path: Path, timeout: float = 60.0) -> None:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "SekaiTranslator/1.0 (+https://github.com)"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)



def _find_extracted_root(extract_dir: Path) -> Path:
    root_candidates = [p for p in extract_dir.iterdir() if p.is_dir()]
    if not root_candidates:
        raise RuntimeError("ZIP do repo está vazio ou inválido.")
    
    return max(root_candidates, key=lambda p: sum(1 for _ in p.rglob("*")))


def _find_manifest(extracted_root: Path) -> Optional[Path]:
    """
    Procura manifest.json no root extraído (preferencial).
    Também tenta algumas variações comuns.
    """
    candidates = [
        extracted_root / "manifest.json",
        extracted_root / "parsers" / "manifest.json",
        extracted_root / "plugins" / "manifest.json",
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c

    
    try:
        for c in extracted_root.rglob("manifest.json"):
            if c.is_file():
                return c
    except Exception:
        pass
    return None


def _find_plugins_root(extracted_root: Path) -> Optional[Path]:
    """
    Aceita layouts comuns:
      - <root>/plugins/<parser>/plugin.py
      - <root>/parsers/plugins/<parser>/plugin.py
      - <root>/<parser>/plugin.py   (layout "flat" opcional)
    Retorna uma pasta que contém subpastas de parsers.
    """
    candidates = [
        extracted_root / "plugins",
        extracted_root / "parsers" / "plugins",
    ]
    for c in candidates:
        if c.exists() and c.is_dir():
            for child in c.iterdir():
                if child.is_dir() and (child / "plugin.py").exists():
                    return c

    
    for child in extracted_root.iterdir():
        if child.is_dir() and (child / "plugin.py").exists():
            return extracted_root

    
    for c in extracted_root.rglob("plugins"):
        if not c.is_dir():
            continue
        for child in c.iterdir():
            if child.is_dir() and (child / "plugin.py").exists():
                return c

    return None



def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_manifest(manifest_path: Path) -> dict:
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"manifest.json inválido: {e}")

    if not isinstance(data, dict):
        raise RuntimeError("manifest.json inválido (esperado objeto JSON).")

    items = data.get("items")
    if items is None or not isinstance(items, list):
        raise RuntimeError("manifest.json inválido: 'items' deve ser uma lista.")

    return data


def _build_repo_from_manifest(extracted_root: Path, manifest_path: Path) -> Path:
    """
    Monta uma pasta temporária "repo_built" usando SOMENTE o manifest.
    Valida sha256 de plugin.py se o campo estiver preenchido.
    """
    manifest = _load_manifest(manifest_path)

    plugins_root = _find_plugins_root(extracted_root)
    if plugins_root is None:
        raise RuntimeError(
            "Não encontrei a pasta de plugins no repo.\n"
            "Esperado: plugins/<parser>/plugin.py (ou parsers/plugins/<parser>/plugin.py), "
            "ou layout flat <parser>/plugin.py."
        )

    
    items = manifest.get("items") or []
    built_repo = Path(tempfile.mkdtemp(prefix="sekai_repo_built_"))

    installed = 0
    for it in items:
        if not isinstance(it, dict):
            continue

        folder = (it.get("folder") or "").strip()
        pid = (it.get("id") or "").strip()
        sha = (it.get("sha256") or "").strip().lower()

        if not folder:
            continue

        src = plugins_root / folder
        plugin_py = src / "plugin.py"

        if not plugin_py.exists():
            raise RuntimeError(f"Manifest aponta para '{folder}', mas plugin.py não existe.")

        
        if sha:
            got = _sha256_file(plugin_py)
            if got.lower() != sha:
                raise RuntimeError(
                    f"SHA256 inválido para '{pid or folder}'.\n"
                    f"Esperado: {sha}\n"
                    f"Obtido:   {got}"
                )

        dst = built_repo / folder
        if dst.exists():
            shutil.rmtree(dst, ignore_errors=True)

        shutil.copytree(src, dst)
        installed += 1

    if installed <= 0:
        raise RuntimeError("Manifest não instalou nada (items vazio ou inválido).")

    return built_repo


def _build_repo_by_discovery(extracted_root: Path) -> Path:
    """
    Comportamento antigo: procura plugins_root e copia todas as subpastas com plugin.py.
    """
    plugins_root = _find_plugins_root(extracted_root)
    if plugins_root is None:
        raise RuntimeError(
            "Não encontrei a pasta de plugins no repo.\n"
            "Esperado: plugins/<parser>/plugin.py (ou parsers/plugins/<parser>/plugin.py), "
            "ou layout flat <parser>/plugin.py."
        )

    built_repo = Path(tempfile.mkdtemp(prefix="sekai_repo_built_"))

    for child in sorted(plugins_root.iterdir()):
        if not child.is_dir():
            continue
        if not (child / "plugin.py").exists():
            continue
        shutil.copytree(child, built_repo / child.name)

    if not any(built_repo.iterdir()):
        raise RuntimeError("Nenhum parser válido encontrado (subpastas com plugin.py).")

    return built_repo



def _atomic_replace_dir(src: Path, dst: Path) -> None:
    """
    Substitui dst por src de forma segura (best-effort).
    """
    if not src.exists():
        raise FileNotFoundError(str(src))

    dst.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="sekai_parsers_swap_") as td:
        td_path = Path(td)
        staging = td_path / "staging"
        shutil.copytree(src, staging)

        backup = None
        if dst.exists():
            backup = td_path / "backup"
            shutil.move(str(dst), str(backup))

        shutil.move(str(staging), str(dst))
        



def install_from_github_zip(repo_url: str, *, branch: str = "main") -> Path:
    """
    Baixa o ZIP do GitHub e instala em %LOCALAPPDATA%/SekaiTranslator/Parsers/repo

    Se existir manifest.json: instala somente o que está no manifest (e valida sha256 se informado).
    Se não existir manifest.json: fallback para o autodiscovery antigo.
    """
    ensure_dirs()
    spec = RepoSpec(repo_url=repo_url, branch=branch)

    with tempfile.TemporaryDirectory(prefix="sekai_parsers_dl_") as td:
        td_path = Path(td)

        zip_path = td_path / "repo.zip"
        _download_to_file(spec.zip_url, zip_path)

        extract_dir = td_path / "extract"
        extract_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(extract_dir)

        extracted_root = _find_extracted_root(extract_dir)

        manifest_path = _find_manifest(extracted_root)
        if manifest_path is not None:
            built_repo = _build_repo_from_manifest(extracted_root, manifest_path)
        else:
            built_repo = _build_repo_by_discovery(extracted_root)

        _atomic_replace_dir(built_repo, repo_dir())

        
        try:
            shutil.rmtree(built_repo, ignore_errors=True)
        except Exception:
            pass

    return repo_dir()


def install_or_update_repo(spec: RepoSpec) -> Path:
    return install_from_github_zip(spec.repo_url, branch=spec.branch)


def is_repo_installed(spec: RepoSpec | None = None) -> bool:
    rd = repo_dir()
    if not rd.exists():
        return False
    for child in rd.iterdir():
        if child.is_dir() and (child / "plugin.py").exists():
            return True
    return False


def get_installed_parser_ids() -> list[str]:
    ids: list[str] = []
    try:
        from .manager import get_parser_manager
        mgr = get_parser_manager(force_reload=True)
        for p in mgr.all_plugins():
            pid = (getattr(p, "plugin_id", "") or "").strip()
            if pid:
                ids.append(pid)
    except Exception:
        rd = repo_dir()
        if rd.exists():
            for child in rd.iterdir():
                if child.is_dir() and (child / "plugin.py").exists():
                    ids.append(child.name)

    return sorted(set(ids))


def remove_external_parser(parser_folder_or_id: str) -> bool:
    name = (parser_folder_or_id or "").strip()
    if not name:
        return False

    rd = repo_dir()
    if not rd.exists():
        return False

    direct = rd / name
    if direct.exists() and direct.is_dir():
        shutil.rmtree(direct, ignore_errors=True)
        return True

    
    for child in rd.iterdir():
        if child.is_dir() and (child / "plugin.py").exists() and child.name == name:
            shutil.rmtree(child, ignore_errors=True)
            return True

    return False
