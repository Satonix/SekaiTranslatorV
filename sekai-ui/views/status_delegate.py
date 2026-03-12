from PySide6.QtWidgets import QApplication, QStyledItemDelegate, QStyle, QStyleOptionViewItem
from PySide6.QtGui import QBrush, QColor, QPainter, QPalette
from PySide6.QtCore import Qt


class StatusDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        base_bg = index.data(Qt.BackgroundRole)
        if isinstance(base_bg, QBrush):
            base_bg = base_bg.color()
        elif not isinstance(base_bg, QColor):
            base_bg = None

        painter.save()

        final_bg = None
        if isinstance(base_bg, QColor) and base_bg.isValid():
            final_bg = QColor(base_bg)
            if opt.state & QStyle.State_Selected:
                highlight = opt.palette.color(QPalette.ColorRole.Highlight)
                final_bg = self._blend(final_bg, highlight, 0.32)
        elif opt.state & QStyle.State_Selected:
            final_bg = opt.palette.color(QPalette.ColorRole.Highlight)

        if isinstance(final_bg, QColor) and final_bg.isValid():
            painter.fillRect(opt.rect, final_bg)

        if opt.state & QStyle.State_Selected:
            text_color = opt.palette.color(QPalette.ColorRole.HighlightedText)
        else:
            text_color = opt.palette.color(QPalette.ColorRole.Text)
        opt.palette.setColor(QPalette.ColorRole.Text, text_color)
        opt.palette.setColor(QPalette.ColorRole.WindowText, text_color)

        opt.backgroundBrush = QBrush(Qt.NoBrush)
        opt.state &= ~QStyle.State_Selected

        style = opt.widget.style() if opt.widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)

        painter.restore()

    @staticmethod
    def _blend(base: QColor, overlay: QColor, amount: float) -> QColor:
        t = max(0.0, min(1.0, float(amount)))
        inv = 1.0 - t
        return QColor(
            round(base.red() * inv + overlay.red() * t),
            round(base.green() * inv + overlay.green() * t),
            round(base.blue() * inv + overlay.blue() * t),
            max(base.alpha(), overlay.alpha()),
        )
