from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPalette, QPen
from PySide6.QtCore import QRect, Qt, QEvent, QSettings

from themes.theme_manager import ThemeManager

MAX_SPEAKER_LEN = 14


class EditorGutter(QWidget):
    """
    Gutter fiel ao SekaiTranslator antigo.

    Mostra:
    - número GLOBAL da tabela
    - speaker (se existir)
    """

    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.editor = editor
        self._background_enabled = False
        self._overlay = 140
        self._cached_bg = QColor()
        self._cached_fg = QColor()
        self._cached_divider = QColor()
        self._visual_cache_key: tuple[str, str, bool, int] | None = None
        self.setFont(editor.font())
        self.editor.installEventFilter(self)
        self.update_width()

    def update_width(self, *_):
        self.setFixedWidth(120)

    def update_area(self, rect, dy):
        if dy:
            self.scroll(0, dy)
        else:
            self.update(rect)

    def update_scroll(self, _):
        self.update()

    def eventFilter(self, obj, event):
        if obj is self.editor and event is not None:
            et = event.type()
            if et in (QEvent.FontChange, QEvent.PaletteChange, QEvent.StyleChange):
                self.setFont(self.editor.font())
                self.update_width()
                self.refresh_visual_cache()
                self.update()
        return super().eventFilter(obj, event)

    def refresh_visual_cache(self) -> None:
        pal = self.palette()
        theme_id = ""
        try:
            from PySide6.QtWidgets import QApplication
            inst = QApplication.instance()
        except Exception:
            inst = None
        try:
            background_enabled = bool(inst.property("sekai_background_enabled")) if inst is not None else False
        except Exception:
            background_enabled = False
        try:
            overlay = int(inst.property("sekai_background_overlay")) if inst is not None and inst.property("sekai_background_overlay") is not None else 140
        except Exception:
            overlay = 140
        if inst is None or inst.property("sekai_background_overlay") is None:
            try:
                settings = QSettings("SekaiTranslatorV", "SekaiTranslatorV")
                background_enabled = bool(settings.value("ui/background_enabled", background_enabled, type=bool))
                overlay = int(settings.value("ui/background_overlay", overlay) or overlay)
            except Exception:
                background_enabled = False
                overlay = 140
        overlay = max(0, min(220, overlay))
        try:
            theme_id = str(inst.property("sekai_theme") or "").strip() if inst is not None else ""
        except Exception:
            theme_id = ""
        try:
            theme_signature = str(inst.property("sekai_theme_signature") or "").strip() if inst is not None else ""
        except Exception:
            theme_signature = ""
        cache_key = (theme_id, theme_signature, background_enabled, overlay)
        if self._visual_cache_key == cache_key and self._cached_bg.isValid() and self._cached_fg.isValid() and self._cached_divider.isValid():
            return

        bg = pal.color(QPalette.AlternateBase)
        if not bg.isValid():
            bg = pal.color(QPalette.Base)

        fg = pal.color(QPalette.PlaceholderText)
        if not fg.isValid() or fg.alpha() == 0:
            fg = pal.color(QPalette.Mid)
        if not fg.isValid() or fg.alpha() == 0:
            fg = pal.color(QPalette.WindowText)
        if not fg.isValid() or fg.alpha() == 0:
            fg = pal.color(QPalette.Text)

        divider = pal.color(QPalette.Mid)
        if not divider.isValid():
            divider = fg

        self._background_enabled = background_enabled
        self._overlay = overlay
        self._cached_bg = ThemeManager.gutter_background_color(background_enabled=background_enabled, overlay=overlay, palette=pal)
        self._cached_fg = fg
        self._cached_divider = ThemeManager.gutter_divider_color(background_enabled=background_enabled, overlay=overlay, fallback=divider)
        self._visual_cache_key = cache_key

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setFont(self.editor.font())

        self.refresh_visual_cache()

        painter.fillRect(event.rect(), self._cached_bg)
        painter.setPen(QPen(self._cached_divider))
        painter.drawLine(self.width() - 1, event.rect().top(), self.width() - 1, event.rect().bottom())

        editor = self.editor
        block = editor.firstVisibleBlock()
        block_number = block.blockNumber()

        offset = editor.contentOffset()
        top = int(
            editor.blockBoundingGeometry(block)
            .translated(offset)
            .top()
        )

        line_height = editor.fontMetrics().height()

        while block.isValid() and top <= event.rect().bottom():
            height = int(editor.blockBoundingRect(block).height())
            bottom = top + height

            if block.isVisible() and bottom >= event.rect().top():
                number_text = ""
                speaker_text = ""

                if hasattr(editor, "get_meta_for_block"):
                    row, speaker = editor.get_meta_for_block(block_number)
                    if row is not None:
                        number_text = f"{row + 1}."
                    if speaker:
                        speaker_text = speaker[:MAX_SPEAKER_LEN]

                text = number_text
                if speaker_text:
                    text += f" {speaker_text}"

                painter.setPen(self._cached_fg)
                painter.drawText(
                    QRect(
                        0,
                        top,
                        self.width() - 6,
                        line_height,
                    ),
                    Qt.AlignRight | Qt.AlignVCenter,
                    text,
                )

            block = block.next()
            block_number += 1
            top = bottom
