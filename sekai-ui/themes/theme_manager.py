from __future__ import annotations

from copy import deepcopy
import hashlib
from dataclasses import dataclass
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict

from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from themes.theme_storage import ThemeStorage


@dataclass(frozen=True)
class ThemeSpec:
    id: str
    display_name: str
    style: str
    palette_mode: str
    qss_file: str
    overlay_file: str
    tokens_file: str
    is_custom: bool = False
    base_theme_id: str = ""
    root_dir: str = ""
    custom_qss_file: str = ""


class ThemeManager:
    SETTINGS_KEY = "ui/theme"
    DEFAULT_THEME_NAME = "Escuro"
    _native_style_name: str | None = None
    _qss_cache: dict[tuple[str, str], str] = {}
    _tokens_cache: dict[tuple[str, str], dict[str, Any]] = {}
    _overlay_cache: dict[tuple[str, int], str] = {}
    _custom_themes_cache: dict[str, ThemeSpec] | None = None
    _builtin_source_dir_cache: Path | None = None
    _final_stylesheet_cache: dict[str, str] = {}
    _theme_signature_cache: dict[str, str] = {}
    _builtin_source_dir_cache: Path | None = None
    _effective_tokens_cache: dict[str, dict[str, Any]] = {}
    _final_qss_cache: dict[str, str] = {}

    THEMES: Dict[str, ThemeSpec] = {
        "Escuro": ThemeSpec(
            "dark",
            "Escuro",
            "Fusion",
            "dark",
            "dark.qss",
            "dark.overlay.qss.in",
            "dark.json",
        ),
        "Branco": ThemeSpec(
            "light",
            "Branco",
            "Fusion",
            "light",
            "light.qss",
            "light.overlay.qss.in",
            "light.json",
        ),
        "Sekai": ThemeSpec(
            "sekai_future",
            "Sekai",
            "Fusion",
            "future",
            "sekai_future.qss",
            "sekai_future.overlay.qss.in",
            "sekai_future.json",
        ),
    }

    BUILTIN_ID_MAP = {spec.id: name for name, spec in THEMES.items()}
    LEGACY_MAP = {
        "dark": "Escuro",
        "escuro": "Escuro",
        "dark (padrão)": "Escuro",
        "dark (default)": "Escuro",
        "dark_classic": "Escuro",
        "light": "Branco",
        "branco": "Branco",
        "white": "Branco",
        "sekai": "Sekai",
        "future": "Sekai",
        "sekai future": "Sekai",
        "sistema": "Escuro",
        "system": "Escuro",
    }

    @classmethod
    def builtin_source_dir(cls) -> Path:
        if cls._builtin_source_dir_cache is not None and cls._builtin_source_dir_cache.exists():
            return cls._builtin_source_dir_cache
        found = cls._find_builtin_source_dir()
        if found is None:
            found = Path(__file__).resolve().parent
        cls._builtin_source_dir_cache = found
        return found

    @classmethod
    def themes_dir(cls) -> Path:
        return cls.builtin_source_dir()

    @classmethod
    def builtin_display_names(cls) -> list[str]:
        return list(cls.THEMES.keys())

    @classmethod
    def display_names(cls) -> list[str]:
        names = list(cls.THEMES.keys())
        names.extend(sorted(cls._custom_themes().keys(), key=str.lower))
        return names

    @classmethod
    def normalize_theme_name(cls, name: str | None) -> str:
        raw = (name or "").strip()
        if raw in cls.THEMES or raw in cls._custom_themes():
            return raw
        return cls.LEGACY_MAP.get(raw.lower(), cls.DEFAULT_THEME_NAME)

    @classmethod
    def theme_spec(cls, name: str | None) -> ThemeSpec:
        normalized = cls.normalize_theme_name(name)
        if normalized in cls.THEMES:
            return cls.THEMES[normalized]
        return cls._custom_themes().get(normalized, cls.THEMES[cls.DEFAULT_THEME_NAME])

    @classmethod
    def theme_spec_from_id(cls, theme_id: str | None) -> ThemeSpec:
        normalized = (theme_id or "").strip().lower()
        builtin_name = cls.BUILTIN_ID_MAP.get(normalized)
        if builtin_name:
            return cls.THEMES[builtin_name]
        if normalized == "dark_classic":
            return cls.THEMES["Escuro"]
        for spec in cls._custom_themes().values():
            if spec.id.lower() == normalized:
                return spec
        return cls.THEMES[cls.DEFAULT_THEME_NAME]

    @classmethod
    def current_theme_spec(cls, app: QApplication | None = None) -> ThemeSpec:
        inst = app or QApplication.instance()
        try:
            theme_id = str(inst.property("sekai_theme") or "").strip() if inst is not None else ""
        except Exception:
            theme_id = ""
        return cls.theme_spec_from_id(theme_id)

    @classmethod
    def load_saved_theme_name(cls, app_name: str = "SekaiTranslatorV") -> str:
        s = QSettings(app_name, app_name)
        return cls.normalize_theme_name(s.value(cls.SETTINGS_KEY, cls.DEFAULT_THEME_NAME))

    @classmethod
    def save_theme_name(cls, name: str, app_name: str = "SekaiTranslatorV") -> str:
        normalized = cls.normalize_theme_name(name)
        s = QSettings(app_name, app_name)
        s.setValue(cls.SETTINGS_KEY, normalized)
        return normalized

    @classmethod
    def apply_saved_theme(cls, app: QApplication, app_name: str = "SekaiTranslatorV") -> str:
        return cls.apply_theme(app, cls.load_saved_theme_name(app_name))

    @classmethod
    def apply_theme(cls, app: QApplication, name: str | None) -> str:
        spec = cls.theme_spec(name)
        cls._ensure_native_style_name(app)

        try:
            style_name = cls._resolved_style_name(spec)
            if style_name:
                app.setStyle(style_name)
        except Exception:
            pass

        qss = cls._build_final_stylesheet(spec)
        palette = cls._build_palette(spec.palette_mode, app)
        signature = cls._theme_signature(spec, qss)

        app.setPalette(palette)
        if app.styleSheet() != qss:
            app.setStyleSheet(qss)

        app.setProperty("sekai_theme", spec.id)
        app.setProperty("sekai_theme_name", spec.display_name)
        app.setProperty("sekai_theme_signature", signature)
        cls._refresh_top_level_widgets(app)
        return spec.display_name

    @classmethod
    def build_preview_stylesheet(cls, base_theme_name: str, preview_tokens: dict[str, Any]) -> str:
        spec = cls.theme_spec(base_theme_name)
        return cls._load_qss(spec) + "\n\n" + cls._build_override_qss(preview_tokens)

    @classmethod
    def build_preview_palette(cls, base_theme_name: str, app: QApplication | None = None) -> QPalette:
        spec = cls.theme_spec(base_theme_name)
        return cls._build_palette(spec.palette_mode, app)

    @classmethod
    def preview_status_colors(cls, preview_tokens: dict[str, Any]) -> dict[str, str]:
        return {
            "in_progress": str(preview_tokens.get("status_in_progress") or "#d97706"),
            "translated": str(preview_tokens.get("status_translated") or "#22c55e"),
            "reviewed": str(preview_tokens.get("status_reviewed") or "#8b5cf6"),
        }


    @classmethod
    def preview_status_overlay_colors(cls, preview_tokens: dict[str, Any]) -> dict[str, str]:
        return {
            "in_progress": str(preview_tokens.get("status_overlay_in_progress") or preview_tokens.get("status_in_progress") or "#d97706"),
            "translated": str(preview_tokens.get("status_overlay_translated") or preview_tokens.get("status_translated") or "#22c55e"),
            "reviewed": str(preview_tokens.get("status_overlay_reviewed") or preview_tokens.get("status_reviewed") or "#8b5cf6"),
        }
    @classmethod
    def build_overlay_stylesheet(
        cls,
        *,
        enabled: bool,
        overlay: int,
        app: QApplication | None = None,
        theme_id: str | None = None,
    ) -> str:
        if not enabled:
            return ""

        ov = max(0, min(220, int(overlay)))

        def a(value: int, minimum: int = 0, maximum: int = 255) -> int:
            return max(minimum, min(maximum, int(value)))

        values = {
            "PANEL_ALPHA": a(round(8 + ov * 0.42), 0, 150),
            "VIEWPORT_ALPHA": a(round(4 + ov * 0.34), 0, 124),
            "ALT_ROW_ALPHA": a(round(6 + ov * 0.28), 0, 110),
            "GUTTER_ALPHA": a(round(6 + ov * 0.30), 0, 112),
            "TAB_ALPHA": a(round(10 + ov * 0.40), 0, 150),
            "TAB_SELECTED_ALPHA": a(round(14 + ov * 0.46), 0, 168),
            "TAB_HOVER_ALPHA": a(round(12 + ov * 0.43), 0, 160),
            "INPUT_ALPHA": a(round(10 + ov * 0.38), 0, 150),
            "MENU_ALPHA": a(round(16 + ov * 0.50), 0, 176),
            "SPLITTER_ALPHA": a(round(2 + ov * 0.18), 0, 88),
            "BORDER_ALPHA": a(round(26 + ov * 0.24), 18, 108),
            "BORDER_STRONG_ALPHA": a(round(34 + ov * 0.26), 24, 124),
            "BORDER_FOCUS_ALPHA": a(round(46 + ov * 0.30), 32, 148),
            "BORDER_HOVER_ALPHA": a(round(40 + ov * 0.28), 28, 136),
        }

        spec = cls.theme_spec_from_id(theme_id) if theme_id else cls.current_theme_spec(app)
        cache_key = (spec.id, ov)
        cached = cls._overlay_cache.get(cache_key)
        if cached is not None:
            return cached

        qss = cls._load_overlay(spec)
        if not qss:
            qss = cls._load_overlay(cls.THEMES[cls.DEFAULT_THEME_NAME])
            if not qss:
                return ""

        for key, value in values.items():
            qss = qss.replace("{{" + key + "}}", str(value))

        cls._overlay_cache[cache_key] = qss
        return qss

    @classmethod
    def background_overlay_color(cls, *, overlay: int, app: QApplication | None = None) -> QColor:
        spec = cls.current_theme_spec(app)
        tokens = cls._effective_tokens(spec)
        bg_overlay = tokens.get("background_overlay", {})
        rgb = bg_overlay.get("color", [0, 0, 0])
        alpha = cls._scaled_alpha(
            overlay,
            factor=bg_overlay.get("alpha_factor", 1.0),
            minimum=bg_overlay.get("alpha_min", 0),
            maximum=bg_overlay.get("alpha_max", 255),
        )
        color = QColor(*rgb[:3])
        color.setAlpha(alpha)
        return color

    @classmethod
    def gutter_background_color(
        cls,
        *,
        background_enabled: bool,
        overlay: int,
        palette: QPalette | None = None,
        app: QApplication | None = None,
    ) -> QColor:
        inst = app or QApplication.instance()
        pal = palette or (inst.palette() if inst is not None else QPalette())
        bg = pal.color(QPalette.AlternateBase)
        if not bg.isValid():
            bg = pal.color(QPalette.Base)
        if not background_enabled:
            return bg

        spec = cls.current_theme_spec(inst)
        tokens = cls._effective_tokens(spec)
        gutter = tokens.get("gutter", {})
        rgb = gutter.get("background", [18, 22, 30])
        alpha = cls._scaled_alpha(
            overlay,
            factor=gutter.get("background_alpha_factor", 0.38),
            minimum=gutter.get("background_alpha_min", 16),
            maximum=gutter.get("background_alpha_max", 92),
        )
        color = QColor(*rgb[:3])
        color.setAlpha(alpha)
        return color

    @classmethod
    def gutter_divider_color(
        cls,
        *,
        background_enabled: bool,
        overlay: int,
        fallback: QColor,
        app: QApplication | None = None,
    ) -> QColor:
        divider = QColor(fallback)
        if not background_enabled:
            return divider

        spec = cls.current_theme_spec(app)
        tokens = cls._effective_tokens(spec)
        gutter = tokens.get("gutter", {})
        divider.setAlpha(
            cls._scaled_alpha(
                overlay,
                factor=gutter.get("divider_alpha_factor", 0.46),
                minimum=gutter.get("divider_alpha_min", 34),
                maximum=gutter.get("divider_alpha_max", 110),
            )
        )
        return divider

    @classmethod
    def status_color(
        cls,
        status: str,
        *,
        background_enabled: bool,
        overlay: int,
        app: QApplication | None = None,
    ) -> QColor | None:
        spec = cls.current_theme_spec(app)
        tokens = cls._effective_tokens(spec)
        key = cls._normalize_status(status)
        base = cls._base_status_colors(spec.id, tokens)

        if not background_enabled or key == "untranslated":
            return base.get(key)

        status_overlay = tokens.get("status_overlay", {})
        colors = status_overlay.get("colors", {})
        overlay_color = cls._coerce_color(colors.get(key))
        if overlay_color is None:
            return base.get(key)

        overlay_color.setAlpha(
            cls._scaled_alpha(
                overlay,
                factor=status_overlay.get("alpha_factor", 0.52),
                minimum=status_overlay.get("alpha_min", 28),
                maximum=status_overlay.get("alpha_max", 120),
            )
        )
        return overlay_color

    @classmethod
    def create_custom_theme(cls, display_name: str, base_theme_name: str) -> str:
        base = cls.theme_spec(base_theme_name)
        display_name = cls._unique_display_name(display_name or "Novo Tema")
        theme_id = ThemeStorage.unique_theme_id(display_name)
        tokens = cls._effective_tokens(base)
        ThemeStorage.write_theme(
            theme_id=theme_id,
            display_name=display_name,
            base_theme_id=base.id,
            style=base.style,
            palette_mode=base.palette_mode,
            tokens=tokens,
        )
        cls.refresh_custom_themes()
        return display_name

    @classmethod
    def duplicate_theme(cls, theme_name: str) -> str:
        spec = cls.theme_spec(theme_name)
        display_name = cls._unique_display_name(f"{spec.display_name} (Cópia)")
        base = cls.theme_spec_from_id(spec.base_theme_id or spec.id)
        tokens = cls._effective_tokens(spec)
        theme_id = ThemeStorage.unique_theme_id(display_name)
        ThemeStorage.write_theme(
            theme_id=theme_id,
            display_name=display_name,
            base_theme_id=base.id,
            style=base.style,
            palette_mode=base.palette_mode,
            tokens=tokens,
        )
        cls.refresh_custom_themes()
        return display_name

    @classmethod
    def update_custom_theme(
        cls,
        *,
        existing_name: str,
        display_name: str,
        base_theme_name: str,
        tokens: dict[str, Any],
    ) -> str:
        spec = cls.theme_spec(existing_name)
        if not spec.is_custom:
            raise ValueError("Somente temas personalizados podem ser editados.")

        base = cls.theme_spec(base_theme_name)
        final_name = display_name.strip() or spec.display_name
        if final_name != spec.display_name:
            final_name = cls._unique_display_name(final_name, excluding=spec.display_name)

        full_tokens = cls._inflate_editor_tokens(base, tokens)

        ThemeStorage.write_theme(
            theme_id=spec.id,
            display_name=final_name,
            base_theme_id=base.id,
            style=base.style,
            palette_mode=base.palette_mode,
            tokens=full_tokens,
            custom_qss=ThemeStorage.read_custom_qss(spec.id),
        )
        cls.refresh_custom_themes()
        return final_name

    @classmethod
    def delete_custom_theme(cls, theme_name: str) -> bool:
        spec = cls.theme_spec(theme_name)
        if not spec.is_custom:
            return False
        ok = ThemeStorage.delete_theme(spec.id)
        cls.refresh_custom_themes()
        return ok

    @classmethod
    def import_custom_theme(cls, source_path: str) -> str:
        theme_id = ThemeStorage.import_theme(source_path)
        cls.refresh_custom_themes()
        return cls.theme_spec_from_id(theme_id).display_name

    @classmethod
    def export_custom_theme(cls, theme_name: str, target_path: str) -> None:
        spec = cls.theme_spec(theme_name)
        if not spec.is_custom:
            raise ValueError("Tema nativo não pode ser exportado.")
        ThemeStorage.export_theme(spec.id, target_path)

    @classmethod
    def editable_tokens_for_theme(cls, theme_name: str) -> dict[str, Any]:
        spec = cls.theme_spec(theme_name)
        return cls._flatten_tokens_for_editor(cls._effective_tokens(spec), spec.palette_mode)

    @classmethod
    def refresh_custom_themes(cls) -> None:
        cls._custom_themes_cache = None
        cls._builtin_source_dir_cache = None
        cls._qss_cache.clear()
        cls._tokens_cache.clear()
        cls._overlay_cache.clear()
        cls._effective_tokens_cache.clear()
        cls._final_qss_cache.clear()

    @classmethod
    def _custom_themes(cls) -> dict[str, ThemeSpec]:
        if cls._custom_themes_cache is not None:
            return cls._custom_themes_cache

        result: dict[str, ThemeSpec] = {}
        try:
            for path in ThemeStorage.themes_dir().iterdir():
                if not path.is_dir():
                    continue
                if path.name == getattr(ThemeStorage, "BUILTIN_DIR_NAME", "_builtin"):
                    continue

                try:
                    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
                except Exception:
                    continue

                display_name = str(manifest.get("display_name") or manifest.get("id") or path.name).strip() or path.name
                base_theme_id = str(manifest.get("base_theme_id") or "dark").strip() or "dark"
                base_name = cls.BUILTIN_ID_MAP.get(base_theme_id, cls.DEFAULT_THEME_NAME)
                base_spec = cls.THEMES[base_name]

                result[display_name] = ThemeSpec(
                    id=str(manifest.get("id") or path.name),
                    display_name=display_name,
                    style=str(manifest.get("style") or base_spec.style),
                    palette_mode=str(manifest.get("palette_mode") or base_spec.palette_mode),
                    qss_file=base_spec.qss_file,
                    overlay_file=base_spec.overlay_file,
                    tokens_file=str(manifest.get("tokens_file") or "tokens.json"),
                    is_custom=True,
                    base_theme_id=base_spec.id,
                    root_dir=str(path),
                    custom_qss_file=str(manifest.get("custom_qss_file") or "custom.qss"),
                )
        except Exception:
            result = {}

        cls._custom_themes_cache = result
        return result

    @classmethod
    def _effective_tokens(cls, spec: ThemeSpec) -> dict[str, Any]:
        cache_key = spec.id
        cached = cls._effective_tokens_cache.get(cache_key)
        if cached is not None:
            return deepcopy(cached)

        if not spec.is_custom:
            tokens = deepcopy(cls._load_tokens(spec))
        else:
            base_spec = cls.theme_spec_from_id(spec.base_theme_id or spec.id)
            base_tokens = deepcopy(cls._load_tokens(base_spec))
            custom_tokens = ThemeStorage.read_tokens(spec.id)
            tokens = cls._deep_merge(base_tokens, custom_tokens) if custom_tokens else base_tokens

        cls._effective_tokens_cache[cache_key] = deepcopy(tokens)
        return tokens

    @classmethod
    def _flatten_tokens_for_editor(cls, tokens: dict[str, Any], palette_mode: str) -> dict[str, str]:
        palette = cls._build_palette(palette_mode)
        ui = tokens.get("ui", {}) if isinstance(tokens, dict) else {}
        status = tokens.get("status", {}) if isinstance(tokens, dict) else {}
        overlay = tokens.get("status_overlay", {}) if isinstance(tokens, dict) else {}
        colors = overlay.get("colors", {}) if isinstance(overlay, dict) else {}
        background_overlay = tokens.get("background_overlay", {}) if isinstance(tokens, dict) else {}

        return {
            "menu_bg": ui.get("menu_bg") or palette.color(QPalette.Base).name(),
            "menu_hover": ui.get("menu_hover") or palette.color(QPalette.Highlight).name(),
            "window_bg": ui.get("window_bg") or palette.color(QPalette.Window).name(),
            "panel_bg": ui.get("panel_bg") or palette.color(QPalette.Base).name(),
            "text": ui.get("text") or palette.color(QPalette.WindowText).name(),
            "muted_text": ui.get("muted_text") or palette.color(QPalette.PlaceholderText).name(),
            "accent": ui.get("accent") or palette.color(QPalette.Highlight).name(),
            "input_bg": ui.get("input_bg") or palette.color(QPalette.Base).name(),
            "input_border": ui.get("input_border") or "#3f4a5d",
            "background_overlay_color": cls._color_to_hex(cls._coerce_color(background_overlay.get("color"))) or "#000000",
            "status_in_progress": cls._color_to_hex(cls._coerce_color(status.get("in_progress"))) or "#d97706",
            "status_translated": cls._color_to_hex(cls._coerce_color(status.get("translated"))) or "#22c55e",
            "status_reviewed": cls._color_to_hex(cls._coerce_color(status.get("reviewed"))) or "#8b5cf6",
            "status_overlay_in_progress": cls._color_to_hex(cls._coerce_color(colors.get("in_progress"))) or "#d97706",
            "status_overlay_translated": cls._color_to_hex(cls._coerce_color(colors.get("translated"))) or "#22c55e",
            "status_overlay_reviewed": cls._color_to_hex(cls._coerce_color(colors.get("reviewed"))) or "#8b5cf6",
        }

    @classmethod
    def _inflate_editor_tokens(cls, base_spec: ThemeSpec, editable: dict[str, Any]) -> dict[str, Any]:
        tokens = deepcopy(cls._load_tokens(base_spec))
        ui = tokens.setdefault("ui", {})
        status = tokens.setdefault("status", {})
        status_overlay = tokens.setdefault("status_overlay", {})
        colors = status_overlay.setdefault("colors", {})

        ui["menu_bg"] = editable.get("menu_bg") or ui.get("menu_bg")
        ui["menu_hover"] = editable.get("menu_hover") or ui.get("menu_hover")
        ui["window_bg"] = editable.get("window_bg") or ui.get("window_bg")
        ui["panel_bg"] = editable.get("panel_bg") or ui.get("panel_bg")
        ui["text"] = editable.get("text") or ui.get("text")
        ui["muted_text"] = editable.get("muted_text") or ui.get("muted_text")
        ui["accent"] = editable.get("accent") or ui.get("accent")
        ui["input_bg"] = editable.get("input_bg") or ui.get("input_bg")
        ui["input_border"] = editable.get("input_border") or ui.get("input_border")

        background_overlay = tokens.setdefault("background_overlay", {})
        overlay_rgb = cls._coerce_color(editable.get("background_overlay_color"))
        if overlay_rgb is not None:
            background_overlay["color"] = [overlay_rgb.red(), overlay_rgb.green(), overlay_rgb.blue()]

        status["in_progress"] = editable.get("status_in_progress") or status.get("in_progress")
        status["translated"] = editable.get("status_translated") or status.get("translated")
        status["reviewed"] = editable.get("status_reviewed") or status.get("reviewed")

        colors["in_progress"] = editable.get("status_overlay_in_progress") or colors.get("in_progress")
        colors["translated"] = editable.get("status_overlay_translated") or colors.get("translated")
        colors["reviewed"] = editable.get("status_overlay_reviewed") or colors.get("reviewed")

        return tokens

    @classmethod
    def _build_override_qss(cls, tokens: dict[str, Any]) -> str:
        def val(key: str, fallback: str) -> str:
            raw = str(tokens.get(key, "") or "").strip()
            color = QColor(raw)
            return color.name() if color.isValid() else fallback

        return f"""
QWidget {{
    color: {val('text', '#edf2f7')};
}}
QMainWindow, QDialog, QWidget#ThemePreviewRoot {{
    background-color: {val('window_bg', '#1b1e24')};
}}
QGroupBox, QFrame, QTabWidget::pane {{
    background-color: {val('panel_bg', '#11141a')};
}}
QLabel[mutedText='true'] {{
    color: {val('muted_text', '#94a3b8')};
}}
QMenuBar, QMenu {{
    background-color: {val('menu_bg', '#20252d')};
    color: {val('text', '#edf2f7')};
}}
QMenuBar::item:selected, QMenuBar::item:hover,
QMenu::item:selected, QMenu::item:hover {{
    background-color: {val('menu_hover', '#4f8cff')};
}}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QListWidget, QTreeView, QTableView, QTabWidget::pane {{
    background-color: {val('input_bg', '#11141a')};
    border: 1px solid {val('input_border', '#3f4a5d')};
}}
QPushButton {{
    border: 1px solid {val('input_border', '#3f4a5d')};
}}
QPushButton:hover, QTabBar::tab:selected {{
    border-color: {val('accent', '#4f8cff')};
}}
"""

    @classmethod
    def _base_status_colors(cls, theme_id: str, tokens: dict[str, Any] | None = None) -> dict[str, QColor | None]:
        theme_tokens = tokens or {}
        status_tokens = theme_tokens.get("status", {}) if isinstance(theme_tokens, dict) else {}
        from_tokens = {
            "untranslated": cls._coerce_color(status_tokens.get("untranslated")),
            "in_progress": cls._coerce_color(status_tokens.get("in_progress")),
            "translated": cls._coerce_color(status_tokens.get("translated")),
            "reviewed": cls._coerce_color(status_tokens.get("reviewed")),
        }
        if any(value is not None for key, value in from_tokens.items() if key != "untranslated"):
            return from_tokens

        if theme_id == "light":
            return {
                "untranslated": None,
                "in_progress": QColor(244, 234, 154),
                "translated": QColor(201, 234, 210),
                "reviewed": QColor(220, 208, 244),
            }
        if theme_id == "sekai_future":
            return {
                "untranslated": None,
                "in_progress": QColor(96, 90, 18, 255),
                "translated": QColor(26, 64, 48, 255),
                "reviewed": QColor(73, 62, 120, 255),
            }
        return {
            "untranslated": None,
            "in_progress": QColor(116, 120, 18, 255),
            "translated": QColor(42, 79, 49, 255),
            "reviewed": QColor(140, 110, 180, 255),
        }

    @staticmethod
    def _normalize_status(status: str | None) -> str:
        s = str(status or "untranslated").strip().lower().replace(" ", "_")
        if s in ("untranslated", "not_translated"):
            return "untranslated"
        if s in ("inprogress", "in_progress"):
            return "in_progress"
        if s in ("translated", "done"):
            return "translated"
        if s in ("reviewed", "approved"):
            return "reviewed"
        return "untranslated"

    @staticmethod
    def _scaled_alpha(overlay: int, *, factor: float, minimum: int, maximum: int) -> int:
        return max(int(minimum), min(int(maximum), round(int(overlay) * float(factor))))

    @staticmethod
    def _coerce_color(value: Any) -> QColor | None:
        if value is None:
            return None
        if isinstance(value, QColor):
            return QColor(value)
        if isinstance(value, (list, tuple)) and len(value) >= 3:
            try:
                if len(value) >= 4:
                    return QColor(int(value[0]), int(value[1]), int(value[2]), int(value[3]))
                return QColor(int(value[0]), int(value[1]), int(value[2]))
            except Exception:
                return None
        if isinstance(value, str):
            raw = value.strip()
            if not raw or raw.lower() in {"none", "transparent", "null"}:
                return None
            if raw.startswith("#"):
                color = QColor(raw)
                return color if color.isValid() else None
            m = re.fullmatch(r"rgba?\(([^)]+)\)", raw, re.IGNORECASE)
            if m:
                parts = [p.strip() for p in m.group(1).split(",")]
                try:
                    nums = [float(p) for p in parts]
                except Exception:
                    nums = []
                if len(nums) == 3:
                    return QColor(int(nums[0]), int(nums[1]), int(nums[2]))
                if len(nums) >= 4:
                    alpha = nums[3]
                    if alpha <= 1:
                        alpha = round(alpha * 255)
                    return QColor(int(nums[0]), int(nums[1]), int(nums[2]), int(alpha))
            color = QColor(raw)
            return color if color.isValid() else None
        return None

    @staticmethod
    def _color_to_hex(color: QColor | None) -> str:
        if color is None or not color.isValid():
            return ""
        return color.name(QColor.HexRgb)

    @classmethod
    def _load_tokens(cls, spec: ThemeSpec) -> dict[str, Any]:
        if spec.is_custom:
            return ThemeStorage.read_tokens(spec.id)

        source_dir = cls.builtin_source_dir()
        cache_key = (str(source_dir), spec.tokens_file)
        cached = cls._tokens_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            data = json.loads((source_dir / spec.tokens_file).read_text(encoding="utf-8"))
        except Exception:
            data = {}

        cls._tokens_cache[cache_key] = data
        return data

    @classmethod
    def _load_qss(cls, spec: ThemeSpec) -> str:
        if spec.is_custom:
            base_spec = cls.theme_spec_from_id(spec.base_theme_id or spec.id)
            return cls._load_qss(base_spec)

        source_dir = cls.builtin_source_dir()
        cache_key = (str(source_dir), spec.qss_file)
        cached = cls._qss_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            data = (source_dir / spec.qss_file).read_text(encoding="utf-8")
        except Exception:
            data = ""

        cls._qss_cache[cache_key] = data
        return data

    @classmethod
    def _load_overlay(cls, spec: ThemeSpec) -> str:
        if spec.is_custom:
            base_spec = cls.theme_spec_from_id(spec.base_theme_id or spec.id)
            return cls._load_overlay(base_spec)

        source_dir = cls.builtin_source_dir()
        cache_key = (spec.id, 0)
        cached = cls._overlay_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            data = (source_dir / spec.overlay_file).read_text(encoding="utf-8")
        except Exception:
            data = ""

        cls._overlay_cache[cache_key] = data
        return data

    @classmethod
    def _find_builtin_source_dir(cls) -> Path | None:
        checked: list[Path] = []

        def add(path: Path | None) -> None:
            if path is None:
                return
            try:
                resolved = path.resolve()
            except Exception:
                resolved = path
            if resolved not in checked:
                checked.append(resolved)

        module_dir = Path(__file__).resolve().parent
        add(module_dir)

        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).resolve().parent
            add(exe_dir / "themes")
            add(exe_dir / "_internals" / "themes")
            add(exe_dir / "_internal" / "themes")
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                base = Path(meipass)
                add(base / "themes")
                add(base / "_internals" / "themes")
                add(base / "_internal" / "themes")

        for parent in module_dir.parents:
            add(parent / "themes")
            add(parent / "_internals" / "themes")
            add(parent / "_internal" / "themes")

        for candidate in checked:
            if not candidate.is_dir():
                continue
            has_qss = any(candidate.glob("*.qss"))
            has_json = any(candidate.glob("*.json"))
            if has_qss and has_json:
                return candidate

        return None

    @classmethod
    def _ensure_native_style_name(cls, app: QApplication) -> None:
        if cls._native_style_name:
            return
        try:
            cls._native_style_name = app.style().objectName() or "windowsvista"
        except Exception:
            cls._native_style_name = "windowsvista"

    @classmethod
    def _resolved_style_name(cls, spec: ThemeSpec) -> str:
        return spec.style

    @classmethod
    def _refresh_top_level_widgets(cls, app: QApplication) -> None:
        for widget in app.topLevelWidgets():
            try:
                widget.update()
                central = getattr(widget, "centralWidget", lambda: None)()
                if central is not None:
                    central.update()
            except Exception:
                continue


    @classmethod
    def _build_final_stylesheet(cls, spec: ThemeSpec) -> str:
        cache_key = f"{spec.id}|{spec.display_name}|{cls._color_to_hex(None) if False else ''}"
        if spec.is_custom:
            tokens = cls.editable_tokens_for_theme(spec.display_name)
            custom_qss = ThemeStorage.read_custom_qss(spec.id)
            payload = {"id": spec.id, "tokens": tokens, "custom_qss": custom_qss}
            raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
            cache_key = f"custom:{hashlib.sha1(raw.encode('utf-8', errors='replace')).hexdigest()}"
            cached = cls._final_stylesheet_cache.get(cache_key)
            if cached is not None:
                return cached
            qss = cls._load_qss(spec) + "\n\n" + cls._build_override_qss(tokens)
            if custom_qss:
                qss += "\n\n" + custom_qss
            cls._final_stylesheet_cache[cache_key] = qss
            return qss
        cache_key = f"builtin:{spec.qss_file}:{spec.id}"
        cached = cls._final_stylesheet_cache.get(cache_key)
        if cached is not None:
            return cached
        qss = cls._load_qss(spec)
        cls._final_stylesheet_cache[cache_key] = qss
        return qss

    @classmethod
    def _theme_signature(cls, spec: ThemeSpec, qss: str) -> str:
        payload = {
            "id": spec.id,
            "name": spec.display_name,
            "qss": qss,
            "tokens": cls._effective_tokens(spec),
        }
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        cache_key = hashlib.sha1(raw.encode("utf-8", errors="replace")).hexdigest()
        cached = cls._theme_signature_cache.get(cache_key)
        if cached is not None:
            return cached
        cls._theme_signature_cache[cache_key] = cache_key
        return cache_key

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(base)
        for key, value in (override or {}).items():
            if isinstance(result.get(key), dict) and isinstance(value, dict):
                result[key] = ThemeManager._deep_merge(result[key], value)
            else:
                result[key] = deepcopy(value)
        return result

    @classmethod
    def _unique_display_name(cls, display_name: str, excluding: str | None = None) -> str:
        candidate = (display_name or "Novo Tema").strip() or "Novo Tema"
        existing = {name.lower() for name in cls.display_names() if name != excluding}
        if candidate.lower() not in existing:
            return candidate

        index = 2
        while True:
            probe = f"{candidate} {index}"
            if probe.lower() not in existing:
                return probe
            index += 1

    @staticmethod
    def _build_palette(mode: str, app: QApplication | None = None) -> QPalette:
        palette = QPalette()

        if mode == "light":
            window = QColor(245, 247, 250)
            base = QColor(255, 255, 255)
            alt_base = QColor(248, 250, 252)
            text = QColor(31, 41, 55)
            button = QColor(255, 255, 255)
            highlight = QColor(59, 130, 246)
            highlighted_text = QColor(255, 255, 255)
            tool_tip_base = QColor(255, 255, 255)
            tool_tip_text = QColor(17, 24, 39)
            bright_text = QColor(17, 24, 39)
            placeholder = QColor(100, 116, 139)
            disabled_text = QColor(148, 163, 184)
        elif mode == "future":
            window = QColor(17, 19, 24)
            base = QColor(23, 26, 33)
            alt_base = QColor(29, 35, 48)
            text = QColor(230, 234, 242)
            button = QColor(29, 35, 48)
            highlight = QColor(77, 163, 255)
            highlighted_text = QColor(255, 255, 255)
            tool_tip_base = QColor(29, 35, 48)
            tool_tip_text = QColor(255, 255, 255)
            bright_text = QColor(255, 255, 255)
            placeholder = QColor(152, 162, 179)
            disabled_text = QColor(119, 129, 145)
        else:
            window = QColor(30, 33, 38)
            base = QColor(36, 40, 46)
            alt_base = QColor(43, 48, 55)
            text = QColor(229, 231, 235)
            button = QColor(43, 48, 55)
            highlight = QColor(120, 138, 160)
            highlighted_text = QColor(255, 255, 255)
            tool_tip_base = QColor(43, 48, 55)
            tool_tip_text = QColor(255, 255, 255)
            bright_text = QColor(255, 255, 255)
            placeholder = QColor(156, 163, 175)
            disabled_text = QColor(107, 114, 128)

        palette.setColor(QPalette.Window, window)
        palette.setColor(QPalette.WindowText, text)
        palette.setColor(QPalette.Base, base)
        palette.setColor(QPalette.AlternateBase, alt_base)
        palette.setColor(QPalette.ToolTipBase, tool_tip_base)
        palette.setColor(QPalette.ToolTipText, tool_tip_text)
        palette.setColor(QPalette.Text, text)
        palette.setColor(QPalette.Button, button)
        palette.setColor(QPalette.ButtonText, text)
        palette.setColor(QPalette.BrightText, bright_text)
        palette.setColor(QPalette.Highlight, highlight)
        palette.setColor(QPalette.HighlightedText, highlighted_text)
        palette.setColor(QPalette.PlaceholderText, placeholder)
        palette.setColor(QPalette.Disabled, QPalette.WindowText, disabled_text)
        palette.setColor(QPalette.Disabled, QPalette.Text, disabled_text)
        palette.setColor(QPalette.Disabled, QPalette.ButtonText, disabled_text)
        palette.setColor(QPalette.Disabled, QPalette.PlaceholderText, disabled_text)

        return palette