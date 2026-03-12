from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QWidget


class BackgroundCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._enabled = False
        self._image_path = ""
        self._fallback_path = ""
        self._overlay_opacity = 140
        self._overlay_color = QColor(0, 0, 0, 140)
        self._pixmap_cache: dict[str, QPixmap] = {}
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAutoFillBackground(False)

    def configure(self, *, enabled: bool, image_path: str = "", overlay_opacity: int = 140, fallback_path: str = "", overlay_color: QColor | None = None) -> None:
        self._enabled = bool(enabled)
        self._image_path = (image_path or "").strip()
        self._fallback_path = (fallback_path or "").strip()
        try:
            self._overlay_opacity = max(0, min(255, int(overlay_opacity)))
        except Exception:
            self._overlay_opacity = 140
        base_color = QColor(0, 0, 0) if overlay_color is None else QColor(overlay_color)
        base_color.setAlpha(self._overlay_opacity)
        self._overlay_color = base_color
        self.update()

    def _resolved_image_path(self) -> str:
        for raw in (self._image_path, self._fallback_path):
            if not raw:
                continue
            p = Path(raw)
            try:
                if p.exists() and p.is_file():
                    return str(p)
            except Exception:
                continue
        return ""

    def _pixmap_for_path(self, path: str) -> QPixmap | None:
        if not path:
            return None
        if path not in self._pixmap_cache:
            self._pixmap_cache[path] = QPixmap(path)
        pix = self._pixmap_cache.get(path)
        if pix is None or pix.isNull():
            return None
        return pix

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        if self._enabled:
            pix = self._pixmap_for_path(self._resolved_image_path())
            if pix is not None:
                target = self.rect()
                scaled = pix.scaled(target.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                x = (scaled.width() - target.width()) // 2
                y = (scaled.height() - target.height()) // 2
                painter.drawPixmap(target, scaled, QRect(x, y, target.width(), target.height()))
            else:
                painter.fillRect(self.rect(), self.palette().window())
        else:
            painter.fillRect(self.rect(), self.palette().window())

        if self._enabled and self._overlay_opacity > 0:
            painter.fillRect(self.rect(), self._overlay_color)
