from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QLineEdit, QPushButton, QColorDialog


class ColorField(QWidget):
    colorChanged = Signal(str, str)

    def __init__(self, key: str, title: str, parent=None):
        super().__init__(parent)
        self._key = key
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.label = QLabel(title)
        self.label.setMinimumWidth(160)
        layout.addWidget(self.label)

        self.preview = QLabel()
        self.preview.setFixedSize(22, 22)
        self.preview.setStyleSheet('border: 1px solid rgba(127,127,127,0.5); border-radius: 4px;')
        layout.addWidget(self.preview)

        self.edit = QLineEdit()
        self.edit.setPlaceholderText('#RRGGBB')
        layout.addWidget(self.edit, 1)

        self.btn_pick = QPushButton('Escolher...')
        layout.addWidget(self.btn_pick)

        self.btn_pick.clicked.connect(self._pick)
        self.edit.editingFinished.connect(self._emit_if_valid)
        self.edit.textChanged.connect(self._update_preview)

    def setColor(self, value: str) -> None:
        self.edit.setText((value or '').strip())
        self._update_preview(self.edit.text())

    def _pick(self) -> None:
        color = QColorDialog.getColor(QColor(self.edit.text().strip() or '#000000'), self, 'Escolher cor')
        if color.isValid():
            value = color.name(QColor.HexRgb)
            self.edit.setText(value)
            self.colorChanged.emit(self._key, value)

    def _emit_if_valid(self) -> None:
        color = QColor(self.edit.text().strip())
        if color.isValid():
            self.colorChanged.emit(self._key, color.name(QColor.HexRgb))

    def _update_preview(self, value: str) -> None:
        color = QColor((value or '').strip())
        fill = color.name(QColor.HexRgb) if color.isValid() else 'transparent'
        self.preview.setStyleSheet(f'border: 1px solid rgba(127,127,127,0.5); border-radius: 4px; background: {fill};')
