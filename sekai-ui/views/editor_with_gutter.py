from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QPlainTextEdit,
    QSizePolicy,
)
from views.gutter import EditorGutter


class EditorWithGutter(QWidget):
    """
    Wrapper reutilizável: Editor + Gutter sincronizado.
    """

    GUTTER_SPACING = 8

    def __init__(self, editor_widget: QPlainTextEdit, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.editor = editor_widget
        self.editor.setAttribute(Qt.WA_StyledBackground, True)
        self.gutter = EditorGutter(self.editor, self)

        editor_name = self.editor.objectName() or "editor"
        self.gutter.setObjectName(f"{editor_name}Gutter")

        self.gutter.setVisible(True)
        self.gutter.setFixedWidth(120)
        self.gutter.setSizePolicy(
            QSizePolicy.Fixed,
            QSizePolicy.Expanding,
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self.gutter)
        layout.addSpacing(self.GUTTER_SPACING)
        layout.addWidget(self.editor)

        self.editor.setFrameStyle(QPlainTextEdit.NoFrame)
        self.editor.setViewportMargins(0, 0, 0, 0)

        try:
            self.editor.viewport().setProperty("sekaiOverlayViewport", True)
            self.editor.viewport().setAttribute(Qt.WA_StyledBackground, True)
            self.editor.viewport().setAutoFillBackground(False)
        except Exception:
            pass

        try:
            self.gutter.setProperty("sekaiOverlayInner", True)
        except Exception:
            pass

        self.editor.blockCountChanged.connect(
            self.gutter.update_width
        )

        self.editor.updateRequest.connect(
            lambda rect, dy: self.gutter.update_area(rect, dy)
        )

        self.editor.verticalScrollBar().valueChanged.connect(
            self.gutter.update_scroll
        )

        self.gutter.update_width()
        self.gutter.update()
        self.update()
