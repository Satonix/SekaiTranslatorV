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
import re


def parsers_base_dir() -> Path:
    local = (os.environ.get("LOCALAPPDATA") or "").strip()
    if local:
        return Path(local) / "SekaiTranslator" / "Parsers"
    return Path.cwd() / "Parsers"


def repo_dir() -> Path:
    return parsers_base_dir() / "repo"


def installed_dir() -> Path:
    return parsers_base_dir() / "installed"


def ensure_dirs() -> None:
    repo_dir().mkdir(parents=True, exist_ok=True)
    installed_dir().mkdir(parents=True, exist_ok=True)


def _normalize_github_repo_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    u = u.replace("\\", "/").rstrip("/")
    if u.endswith(".git"):
        u = u[:-4].rstrip("/")
    m = re.match(r"^https?://github\.com/([^/]+)/([^/]+)(/.*)?$", u, re.IGNORECASE)
    if not m:
        return u
    owner = m.group(1)
    repo = m.group(2)
    return f"https://github.com/{owner}/{repo}"


@dataclass(frozen=True)
class RepoSpec:
    repo_url: str
    branch: str = "main"

    @property
    def zip_url(self) -> str:
        base = _normalize_github_repo_url(self.repo_url).rstrip("/")
        return f"{base}/archive/refs/heads/{self.branch}.zip"


def _download_bytes(url: str, *, timeout: float = 60.0) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "SekaiTranslator/1.0 (+https://github.com)"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _assert_is_zip(data: bytes, *, url: str) -> None:
    if len(data) < 4:
        raise RuntimeError(f"Download inválido (muito pequeno). URL: {url}")
    if not (data[0:2] == b"PK"):
        head = data[:200]
        try:
            preview = head.decode("utf-8", errors="replace")
        except Exception:
            preview = repr(head)
        raise RuntimeError(
            "Falha ao baixar o repositório de parsers: o conteúdo baixado NÃO é um ZIP.\n\n"
            f"URL: {url}\n\n"
            "Isso costuma acontecer quando o repo_url está apontando para /tree/... (página HTML) "
            "em vez da raiz do repositório.\n\n"
            "Primeiros bytes do download (preview):\n"
            f"{preview}"
        )


def _find_manifest(extracted_root: Path) -> Optional[Path]:
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


def _has_any_plugin_folder(plugins_dir: Path) -> bool:
    try:
        for child in plugins_dir.iterdir():
            if child.is_dir() and (child / "plugin.py").is_file():
                return True
    except Exception:
        return False
    return False


def _find_plugins_root(extracted_root: Path) -> Optional[Path]:
    direct = [
        extracted_root / "plugins",
        extracted_root / "parsers" / "plugins",
    ]
    for c in direct:
        if c.is_dir() and _has_any_plugin_folder(c):
            return c

    try:
        for c in extracted_root.rglob("plugins"):
            if c.is_dir() and _has_any_plugin_folder(c):
                return c
    except Exception:
        pass

    return None


def _find_extracted_root(extract_dir: Path) -> Path:
    roots = [p for p in extract_dir.iterdir() if p.is_dir()]
    if not roots:
        raise RuntimeError("ZIP do repo está vazio ou inválido (nenhuma pasta extraída).")

    for r in roots:
        if _find_plugins_root(r) is not None:
            return r

    best = None
    best_score = -1
    for r in roots:
        try:
            score = sum(1 for _ in r.rglob("*"))
        except Exception:
            score = 0
        if score > best_score:
            best = r
            best_score = score

    return best or roots[0]


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


def _plugins_not_found_diag(extracted_root: Path, *, repo_url: str, zip_url: str) -> str:
    root_items = []
    try:
        for p in extracted_root.iterdir():
            root_items.append(p.name + ("/" if p.is_dir() else ""))
    except Exception:
        pass

    extra = ""
    if "SekaiTranslatorV" in (repo_url or ""):
        extra = (
            "\nParece que você baixou o repositório do APP (SekaiTranslatorV) e não o repositório de parsers.\n"
            "O repo_url configurado está errado.\n"
            "Esperado: https://github.com/Satonix/SekaiTranslator-Parsers\n"
        )

    return (
        "Não encontrei a pasta de plugins no repo.\n"
        "Esperado: plugins/<parser>/plugin.py (ou parsers/plugins/<parser>/plugin.py).\n\n"
        f"repo_url: {repo_url}\n"
        f"zip_url: {zip_url}\n"
        f"Root extraído: {extracted_root}\n"
        f"Itens no root: {', '.join(root_items) if root_items else '(não foi possível listar)'}\n"
        f"{extra}"
    )


def _build_repo_from_manifest(extracted_root: Path, manifest_path: Path, *, repo_url: str, zip_url: str) -> Path:
    manifest = _load_manifest(manifest_path)
    plugins_root = _find_plugins_root(extracted_root)
    if plugins_root is None:
        raise RuntimeError(_plugins_not_found_diag(extracted_root, repo_url=repo_url, zip_url=zip_url))

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


def _build_repo_by_discovery(extracted_root: Path, *, repo_url: str, zip_url: str) -> Path:
    plugins_root = _find_plugins_root(extracted_root)
    if plugins_root is None:
        raise RuntimeError(_plugins_not_found_diag(extracted_root, repo_url=repo_url, zip_url=zip_url))

    built_repo = Path(tempfile.mkdtemp(prefix="sekai_repo_built_"))

    found = 0
    for child in sorted(plugins_root.iterdir()):
        if not child.is_dir():
            continue
        if not (child / "plugin.py").exists():
            continue
        shutil.copytree(child, built_repo / child.name)
        found += 1

    if found <= 0:
        raise RuntimeError("Nenhum parser válido encontrado em plugins/<parser>/plugin.py.")

    return built_repo


def _atomic_replace_dir(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(str(src))

    dst.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="sekai_parsers_swap_") as td:
        td_path = Path(td)
        staging = td_path / "staging"
        shutil.copytree(src, staging)

        if dst.exists():
            backup = td_path / "backup"
            shutil.move(str(dst), str(backup))

        shutil.move(str(staging), str(dst))


def install_from_github_zip(repo_url: str, *, branch: str = "main") -> Path:
    ensure_dirs()
    spec = RepoSpec(repo_url=repo_url, branch=branch)
    zip_url = spec.zip_url

    with tempfile.TemporaryDirectory(prefix="sekai_parsers_dl_") as td:
        td_path = Path(td)

        raw = _download_bytes(zip_url, timeout=60.0)
        _assert_is_zip(raw, url=zip_url)

        zip_path = td_path / "repo.zip"
        zip_path.write_bytes(raw)

        extract_dir = td_path / "extract"
        extract_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(extract_dir)

        extracted_root = _find_extracted_root(extract_dir)

        manifest_path = _find_manifest(extracted_root)
        if manifest_path is not None:
            built_repo = _build_repo_from_manifest(extracted_root, manifest_path, repo_url=repo_url, zip_url=zip_url)
        else:
            built_repo = _build_repo_by_discovery(extracted_root, repo_url=repo_url, zip_url=zip_url)

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


def install_parser_from_repo(folder: str) -> Path:
    ensure_dirs()
    folder = (folder or "").strip().strip("\\/").strip()
    if not folder:
        raise RuntimeError("Folder inválido.")

    src = repo_dir() / folder
    plugin_py = src / "plugin.py"
    if not plugin_py.exists():
        raise RuntimeError(f"plugin.py não encontrado para '{folder}'.")

    dst = installed_dir() / folder
    if dst.exists():
        shutil.rmtree(dst, ignore_errors=True)

    shutil.copytree(src, dst)
    return dst


def remove_installed_parser(folder_or_id: str) -> bool:
    name = (folder_or_id or "").strip()
    if not name:
        return False

    base = installed_dir()
    if not base.exists():
        return False

    direct = base / name
    if direct.exists() and direct.is_dir():
        shutil.rmtree(direct, ignore_errors=True)
        return True

    for child in base.iterdir():
        if child.is_dir() and (child / "plugin.py").exists() and child.name == name:
            shutil.rmtree(child, ignore_errors=True)
            return True

    return False


def list_remote_parsers(repo_url: str, branch: str = "main", timeout: int = 12) -> list[dict]:
    repo_url = (repo_url or "").strip()
    if not repo_url:
        return []

    spec = RepoSpec(repo_url=repo_url, branch=branch)
    raw = _download_bytes(spec.zip_url, timeout=float(timeout))
    _assert_is_zip(raw, url=spec.zip_url)
    return _scan_zip_for_plugins(raw)


def _scan_zip_for_plugins(raw_zip: bytes) -> list[dict]:
    out: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="sekai_parsers_list_") as td:
        zpath = os.path.join(td, "repo.zip")
        with open(zpath, "wb") as f:
            f.write(raw_zip)

        with zipfile.ZipFile(zpath, "r") as z:
            names = z.namelist()

            plugin_paths: list[str] = []
            for n in names:
                low = n.lower().replace("\\", "/")
                if "/plugins/" in low and low.endswith("/plugin.py"):
                    plugin_paths.append(n)

            for n in plugin_paths:
                norm = n.replace("\\", "/")
                parts = [p for p in norm.split("/") if p]
                folder = ""
                try:
                    i = next(i for i, p in enumerate(parts) if p.lower() == "plugins")
                    if i + 1 < len(parts):
                        folder = parts[i + 1]
                except Exception:
                    folder = ""

                try:
                    txt = z.read(n).decode("utf-8", errors="ignore")
                except Exception:
                    continue

                meta = _extract_plugin_meta(txt)
                if meta:
                    meta["folder"] = folder or meta.get("folder") or ""
                    out.append(meta)

    out.sort(key=lambda d: ((d.get("name") or d.get("plugin_id") or "").lower(), (d.get("plugin_id") or "").lower()))

    seen: set[str] = set()
    uniq: list[dict] = []
    for it in out:
        pid = (it.get("plugin_id") or "").strip()
        if not pid or pid in seen:
            continue
        seen.add(pid)
        uniq.append(it)
    return uniq


def _extract_plugin_meta(py_text: str) -> Optional[dict]:
    if not py_text:
        return None

    m_id = re.search(r"\bplugin_id\s*=\s*['\"]([^'\"]+)['\"]", py_text)
    if not m_id:
        return None
    plugin_id = (m_id.group(1) or "").strip()

    m_name = re.search(r"\bname\s*=\s*['\"]([^'\"]+)['\"]", py_text)
    name = (m_name.group(1) or "").strip() if m_name else plugin_id

    exts: list[str] = []
    m_ext = re.search(r"\bextensions\s*=\s*\{([^\}]*)\}", py_text, re.DOTALL)
    if m_ext:
        body = m_ext.group(1)
        exts = re.findall(r"['\"]\.(\w+)['\"]", body)
        exts = ["." + e for e in exts if e]
    else:
        m_ext2 = re.search(r"\bextensions\s*=\s*\[([^\]]*)\]", py_text, re.DOTALL)
        if m_ext2:
            body = m_ext2.group(1)
            exts = re.findall(r"['\"]\.(\w+)['\"]", body)
            exts = ["." + e for e in exts if e]

    return {"plugin_id": plugin_id, "name": name, "extensions": sorted(set(exts))}
