from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any


class ThemeStorage:
    APP_DIR_NAME = "SekaiTranslatorV"
    USER_THEMES_DIRNAME = "themes"

    @classmethod
    def base_dir(cls) -> Path:
        local = (os.environ.get("LOCALAPPDATA") or "").strip()
        if local:
            return Path(local) / cls.APP_DIR_NAME
        return Path.home() / f".{cls.APP_DIR_NAME.lower()}"

    @classmethod
    def themes_dir(cls) -> Path:
        path = cls.base_dir() / cls.USER_THEMES_DIRNAME
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def slugify(cls, value: str) -> str:
        raw = re.sub(r"[^a-zA-Z0-9_-]+", "_", (value or "").strip().lower())
        raw = re.sub(r"_+", "_", raw).strip("_")
        return raw or "tema_personalizado"

    @classmethod
    def unique_theme_id(cls, base_name: str) -> str:
        base = cls.slugify(base_name)
        candidate = base
        index = 2
        root = cls.themes_dir()
        while (root / candidate).exists():
            candidate = f"{base}_{index}"
            index += 1
        return candidate

    @classmethod
    def theme_dir(cls, theme_id: str) -> Path:
        return cls.themes_dir() / cls.slugify(theme_id)

    @classmethod
    def manifest_path(cls, theme_id: str) -> Path:
        return cls.theme_dir(theme_id) / "manifest.json"

    @classmethod
    def tokens_path(cls, theme_id: str) -> Path:
        return cls.theme_dir(theme_id) / "tokens.json"

    @classmethod
    def custom_qss_path(cls, theme_id: str) -> Path:
        return cls.theme_dir(theme_id) / "custom.qss"

    @classmethod
    def read_manifest(cls, theme_id: str) -> dict[str, Any] | None:
        path = cls.manifest_path(theme_id)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    @classmethod
    def read_tokens(cls, theme_id: str) -> dict[str, Any]:
        path = cls.tokens_path(theme_id)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    @classmethod
    def read_custom_qss(cls, theme_id: str) -> str:
        path = cls.custom_qss_path(theme_id)
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""

    @classmethod
    def write_theme(
        cls,
        *,
        theme_id: str,
        display_name: str,
        base_theme_id: str,
        style: str,
        palette_mode: str,
        tokens: dict[str, Any],
        custom_qss: str = "",
    ) -> None:
        folder = cls.theme_dir(theme_id)
        folder.mkdir(parents=True, exist_ok=True)

        manifest = {
            "id": cls.slugify(theme_id),
            "display_name": (display_name or theme_id).strip() or theme_id,
            "base_theme_id": (base_theme_id or "dark").strip() or "dark",
            "style": (style or "Fusion").strip() or "Fusion",
            "palette_mode": (palette_mode or "dark").strip() or "dark",
            "tokens_file": "tokens.json",
            "custom_qss_file": "custom.qss",
            "version": 1,
            "custom": True,
        }

        (folder / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (folder / "tokens.json").write_text(
            json.dumps(tokens or {}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (folder / "custom.qss").write_text(custom_qss or "", encoding="utf-8")

    @classmethod
    def update_custom_qss(cls, theme_id: str, custom_qss: str) -> None:
        folder = cls.theme_dir(theme_id)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "custom.qss").write_text(custom_qss or "", encoding="utf-8")

    @classmethod
    def delete_theme(cls, theme_id: str) -> bool:
        path = cls.theme_dir(theme_id)
        if not path.exists():
            return False
        shutil.rmtree(path, ignore_errors=True)
        return True

    @classmethod
    def export_theme(cls, theme_id: str, target_path: str) -> None:
        src = cls.theme_dir(theme_id)
        if not src.exists():
            raise FileNotFoundError(f"Tema não encontrado: {theme_id}")

        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in src.rglob("*"):
                if path.is_file():
                    zf.write(path, path.relative_to(src))

    @classmethod
    def import_theme(cls, source_path: str) -> str:
        src = Path(source_path)
        if not src.exists():
            raise FileNotFoundError(source_path)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            with zipfile.ZipFile(src, "r") as zf:
                zf.extractall(tmp)

            manifest_path = tmp / "manifest.json"
            if not manifest_path.exists():
                raise ValueError("O arquivo ZIP não contém manifest.json")

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            theme_id = cls.unique_theme_id(
                manifest.get("display_name") or manifest.get("id") or "tema_importado"
            )

            dest = cls.theme_dir(theme_id)
            dest.mkdir(parents=True, exist_ok=True)

            for path in tmp.rglob("*"):
                if path.is_file():
                    target = dest / path.relative_to(tmp)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)

            fixed = cls.read_manifest(theme_id) or {}
            fixed["id"] = theme_id
            fixed["custom"] = True

            (dest / "manifest.json").write_text(
                json.dumps(fixed, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            return theme_id

    @classmethod
    def list_theme_dirs(cls) -> list[Path]:
        root = cls.themes_dir()
        result: list[Path] = []
        try:
            for path in root.iterdir():
                if path.is_dir():
                    result.append(path)
        except Exception:
            return []
        return result