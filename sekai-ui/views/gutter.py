from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor
from PySide6.QtCore import QRect, Qt

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

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor(24, 24, 24))

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

                painter.setPen(QColor(156, 163, 175))
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
