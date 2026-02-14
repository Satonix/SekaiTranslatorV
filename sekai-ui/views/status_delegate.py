from PySide6.QtWidgets import QStyledItemDelegate
from PySide6.QtGui import QPainter
from PySide6.QtCore import Qt


class StatusDelegate(QStyledItemDelegate):
    """
    Delegate neutro de compatibilidade.

    - NÃO assume coluna de status
    - NÃO desenha badge
    - NÃO interfere nas cores do model
    - Mantém pintura padrão do Qt
    """

    def paint(self, painter: QPainter, option, index):
        super().paint(painter, option, index)
