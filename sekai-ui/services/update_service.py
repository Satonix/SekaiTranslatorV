from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import urllib.request
from dataclasses import dataclass
from typing import Optional


def _norm_ver(v: str) -> str:
    v = (v or "").strip()
    if v.startswith("v"):
        v = v[1:]
    return v


def _ver_tuple(v: str) -> tuple[int, ...]:
    v = _norm_ver(v)
    parts = re.split(r"[.+\-]", v)
    out: list[int] = []
    for p in parts:
        try:
            out.append(int(p))
        except Exception:
            out.append(0)
    return tuple(out)


def is_newer(remote: str, local: str) -> bool:
    return _ver_tuple(remote) > _ver_tuple(local)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    notes: str
    installer_url: str
    sha256_url: str


class GitHubReleaseUpdater:
    """Busca update via GitHub Releases (latest) e executa instalador Inno Setup."""

    def __init__(self, owner: str, repo: str, current_version: str):
        self.owner = owner
        self.repo = repo
        self.current_version = current_version

    def fetch_latest(self) -> Optional[UpdateInfo]:
        api = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/latest"
        req = urllib.request.Request(api, headers={"User-Agent": "SekaiTranslatorV"})
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))

        tag = (data.get("tag_name") or "").strip()
        remote_ver = _norm_ver(tag)
        if not remote_ver:
            return None
        if not is_newer(remote_ver, self.current_version):
            return None

        notes = data.get("body") or ""
        assets = data.get("assets") or []

        installer = ""
        sha = ""
        
        for a in assets:
            name = (a.get("name") or "").lower()
            url = (a.get("browser_download_url") or "").strip()
            if not url:
                continue
            if name.endswith(".exe") and ("setup" in name or "installer" in name):
                installer = url
            elif name.endswith(".sha256"):
                sha = url

        if not installer or not sha:
            return None

        return UpdateInfo(
            version=remote_ver,
            notes=notes,
            installer_url=installer,
            sha256_url=sha,
        )

    def download_and_install(self, info: UpdateInfo) -> None:
        tmpdir = tempfile.mkdtemp(prefix="sekai_update_")
        installer_path = os.path.join(tmpdir, f"SekaiTranslatorV_Setup_{info.version}.exe")
        sha_path = os.path.join(tmpdir, f"SekaiTranslatorV_Setup_{info.version}.sha256")

        urllib.request.urlretrieve(info.installer_url, installer_path)
        urllib.request.urlretrieve(info.sha256_url, sha_path)

        expected = ""
        with open(sha_path, "r", encoding="utf-8", errors="replace") as f:
            expected = (f.read().strip().split() or [""])[0].lower()

        got = sha256_file(installer_path).lower()
        if not expected or got != expected:
            raise RuntimeError("Falha na verificação SHA256 do instalador.")

        
        subprocess.Popen(
            [installer_path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
            close_fds=True,
        )
