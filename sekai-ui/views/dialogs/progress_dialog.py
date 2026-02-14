# views/dialogs/progress_dialog.py
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
)


class ProgressDialog(QDialog):
    canceled = Signal()

    def __init__(self, title: str, message: str, parent=None, *, cancellable: bool = False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.resize(460, 150)

        self._total = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self.label = QLabel(message)
        self.label.setWordWrap(True)
        layout.addWidget(self.label)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(True)
        layout.addWidget(self.bar)

        self._btn_cancel = None
        if cancellable:
            btn_row = QHBoxLayout()
            btn_row.addStretch()

            self._btn_cancel = QPushButton("Cancelar")
            self._btn_cancel.clicked.connect(self._on_cancel)
            btn_row.addWidget(self._btn_cancel)

            layout.addLayout(btn_row)

        self._update_text()

    def set_message(self, message: str) -> None:
        self.label.setText(message)

    def set_total(self, total: int) -> None:
        total = int(total or 0)
        self._total = max(0, total)

        if self._total <= 0:
            # fallback: indeterminado (se você quiser usar em outros lugares)
            self.bar.setRange(0, 0)
            self.bar.setValue(0)
        else:
            self.bar.setRange(0, self._total)
            self.bar.setValue(0)

        self._update_text()

    def set_progress(self, done: int) -> None:
        done = int(done or 0)

        if self._total <= 0:
            # se estiver em indeterminado, só muda texto
            self._update_text(done=done)
            return

        done = max(0, min(done, self._total))
        self.bar.setValue(done)
        self._update_text(done=done)

    def _update_text(self, done: int | None = None) -> None:
        if done is None:
            done = self.bar.value()

        if self._total > 0:
            self.bar.setFormat(f"{done}/{self._total}")
        else:
            self.bar.setFormat("Processando...")

    def _on_cancel(self) -> None:
        self.canceled.emit()
        # NÃO fecha aqui se você quer esperar o worker realmente cancelar;
        # mas pode fechar se preferir:
        # self.close()
