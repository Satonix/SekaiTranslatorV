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
from urllib.parse import urlparse


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

    def _download_file(
        self,
        url: str,
        dest_path: str,
        *,
        progress_cb=None,
        cancel_cb=None,
        chunk_size: int = 262144,
    ) -> None:
        req = urllib.request.Request(url, headers={"User-Agent": "SekaiTranslatorV"})
        with urllib.request.urlopen(req, timeout=60) as r:
            total = getattr(r, "length", None)
            if total is None:
                try:
                    total = int(r.headers.get("Content-Length") or 0)
                except Exception:
                    total = 0

            downloaded = 0
            os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)

            with open(dest_path, "wb") as f:
                while True:
                    if cancel_cb and cancel_cb():
                        raise RuntimeError("cancelled")

                    chunk = r.read(chunk_size)
                    if not chunk:
                        break

                    f.write(chunk)
                    downloaded += len(chunk)

                    if progress_cb and total:
                        pct = int(downloaded * 100 / total)
                        progress_cb(max(0, min(100, pct)))

        if progress_cb and total:
            progress_cb(100)

    def download_and_install(
        self,
        info: UpdateInfo,
        *,
        progress_cb=None,
        cancel_cb=None,
        chunk_size: int = 262144,
    ) -> None:
        tmpdir = tempfile.mkdtemp(prefix="sekai_upd_")
        exe_url = info.installer_url
        sha_url = info.sha256_url

        exe_name = os.path.basename(urlparse(exe_url).path) or f"SekaiTranslatorV_Setup_{info.version}.exe"
        sha_name = os.path.basename(urlparse(sha_url).path) or f"{exe_name}.sha256"

        exe_path = os.path.join(tmpdir, exe_name)
        sha_path = os.path.join(tmpdir, sha_name)

        self._download_file(
            exe_url,
            exe_path,
            progress_cb=progress_cb,
            cancel_cb=cancel_cb,
            chunk_size=chunk_size,
        )
        self._download_file(
            sha_url,
            sha_path,
            progress_cb=None,
            cancel_cb=cancel_cb,
            chunk_size=chunk_size,
        )

        expected = (
            open(sha_path, "r", encoding="utf-8", errors="ignore")
            .read()
            .strip()
            .split()
            or [""]
        )[0].lower()

        if expected:
            got = sha256_file(exe_path).lower()
            if got != expected:
                raise RuntimeError("SHA256 mismatch")

        subprocess.Popen([exe_path])
