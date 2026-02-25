from __future__ import annotations

import os
from pathlib import Path
import json
import copy
import re
import time
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt, QSettings, QThread, QTimer, QObject, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QSplitter,
    QTreeView,
    QTabWidget,
    QVBoxLayout,
    QLabel,
    QFileSystemModel,
    QMessageBox,
    QApplication,
    QCheckBox,
)

from views.file_tab import FileTab

if TYPE_CHECKING:
    from views.dialogs.search_dialog import SearchResult
else:
    SearchResult = Any

from services.search_replace_service import SearchReplaceService
from services.update_service import GitHubReleaseUpdater
from services.encoding_service import EncodingService
from services import sync_service
from views.dialogs.translation_preview_dialog import TranslationPreviewDialog

from parsers.autodetect import select_parser
from parsers.manager import get_parser_manager
from parsers.base import ParseContext


class _UpdateWorker(QObject):
    progress = Signal(int)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, update_service: GitHubReleaseUpdater, info):
        super().__init__()
        self._svc = update_service
        self._info = info
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            def _progress(done: int, total: int):
                if total <= 0:
                    return
                p = int((done * 100) / total)
                if p < 0:
                    p = 0
                elif p > 100:
                    p = 100
                self.progress.emit(p)

            self._svc.download_and_install(
                self._info,
                progress_cb=_progress,
                cancel_cb=lambda: self._cancel,
            )
            self.finished.emit()
        except Exception as e:
            self.failed.emit(str(e))


class UpdatesMixin:
    def _auto_check_updates(self):
        """
        Checa updates automaticamente no início, mas sempre pergunta antes de instalar.
        Nunca deve quebrar o app.
        """
        try:
            info = self.update_service.fetch_latest()
            if not info:
                return

            notes = (info.notes or "").strip()

            details = (
                f"Nova versão disponível: {info.version}\n"
                f"Você está usando: {self.app_version}\n\n"
            )

            if notes:
                details += notes[:1200] + ("..." if len(notes) > 1200 else "") + "\n\n"

            res = QMessageBox.question(
                self,
                "Atualização disponível",
                details + "Deseja baixar e instalar agora?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )

            if res != QMessageBox.Yes:
                return

            self._start_update_install(info)
            return

        except Exception:
            return


    def _check_updates_now(self):
        """
        Checagem manual via menu Ajuda -> Verificar atualizações...
        """
        try:
            info = self.update_service.fetch_latest()
            if not info:
                QMessageBox.information(
                    self,
                    "Atualizações",
                    "Você já está na versão mais recente."
                )
                return

            notes = (info.notes or "").strip()

            details = (
                f"Nova versão disponível: {info.version}\n"
                f"Você está usando: {self.app_version}\n\n"
            )

            if notes:
                details += (
                    notes[:2000] +
                    ("..." if len(notes) > 2000 else "") +
                    "\n\n"
                )

            res = QMessageBox.question(
                self,
                "Atualização disponível",
                details + "Deseja baixar e instalar agora?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )

            if res != QMessageBox.Yes:
                return

            self._start_update_install(info)
            return

        except Exception as e:
            QMessageBox.critical(
                self,
                "Erro ao verificar atualizações",
                str(e)
            )


    def _start_update_install(self, info) -> None:
        if not getattr(self, "update_service", None):
            QMessageBox.critical(self, "Atualizações", "Update service não inicializado.")
            return

        dlg = ProgressDialog(self, title="Atualização", message="Baixando atualização...", show_cancel=True)
        dlg.set_range(0, 100)
        dlg.set_value(0)
        dlg.show()

        worker = _UpdateWorker(self.update_service, info)
        th = QThread(self)
        worker.moveToThread(th)

        dlg.canceled.connect(worker.cancel)
        worker.progress.connect(dlg.set_value)

        def _fail(msg: str):
            try:
                dlg.close()
            except Exception:
                pass
            QMessageBox.critical(self, "Erro ao atualizar", msg)
            try:
                th.quit()
                th.wait(2000)
            except Exception:
                pass

        def _done():
            try:
                dlg.close()
            except Exception:
                pass
            try:
                th.quit()
            except Exception:
                pass
            QApplication.quit()

        worker.failed.connect(_fail)
        worker.finished.connect(_done)
        th.started.connect(worker.run)
        th.start()


