from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QApplication, QMessageBox

from services.update_service import GitHubReleaseUpdater
from views.dialogs.progress_dialog import ProgressDialog

if TYPE_CHECKING:
    from views.dialogs.search_dialog import SearchResult
else:
    SearchResult = Any


class _UpdateWorker(QObject):
    progress = Signal(int)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, update_service: GitHubReleaseUpdater, info):
        super().__init__()
        self._svc = update_service
        self._info = info
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            def _progress(pct):
                try:
                    pct = int(pct)
                except Exception:
                    pct = 0

                if pct < 0:
                    pct = 0
                elif pct > 100:
                    pct = 100

                self.progress.emit(pct)

            self._svc.download_and_install(
                self._info,
                progress_cb=_progress,
                cancel_cb=lambda: self._cancel,
            )

            if self._cancel:
                self.failed.emit("Atualização cancelada pelo usuário.")
                return

            self.finished.emit()

        except Exception as e:
            self.failed.emit(str(e))


class UpdatesMixin:
    def _auto_check_updates(self):
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

            if res == QMessageBox.Yes:
                self._start_update_install(info)

        except Exception:
            return

    def _check_updates_now(self):
        try:
            info = self.update_service.fetch_latest()
            if not info:
                QMessageBox.information(
                    self,
                    "Atualizações",
                    "Você já está na versão mais recente.",
                )
                return

            notes = (info.notes or "").strip()
            details = (
                f"Nova versão disponível: {info.version}\n"
                f"Você está usando: {self.app_version}\n\n"
            )

            if notes:
                details += notes[:2000] + ("..." if len(notes) > 2000 else "") + "\n\n"

            res = QMessageBox.question(
                self,
                "Atualização disponível",
                details + "Deseja baixar e instalar agora?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )

            if res == QMessageBox.Yes:
                self._start_update_install(info)

        except Exception as e:
            QMessageBox.critical(
                self,
                "Erro ao verificar atualizações",
                str(e),
            )

    def _start_update_install(self, info) -> None:
        if not getattr(self, "update_service", None):
            QMessageBox.critical(
                self,
                "Atualizações",
                "Serviço de atualização não inicializado.",
            )
            return

        dlg = ProgressDialog(
            title="Atualização",
            message="Baixando atualização...",
            parent=self,
            cancellable=True,
        )
        dlg.set_total(100)
        dlg.set_progress(0)
        dlg.show()

        worker = _UpdateWorker(self.update_service, info)
        thread = QThread(self)
        worker.moveToThread(thread)

        dlg.canceled.connect(worker.cancel)
        worker.progress.connect(dlg.set_progress)

        def _cleanup():
            try:
                thread.quit()
            except Exception:
                pass
            try:
                thread.wait(2000)
            except Exception:
                pass
            try:
                worker.deleteLater()
            except Exception:
                pass
            try:
                thread.deleteLater()
            except Exception:
                pass

        def _on_failed(msg: str):
            try:
                dlg.close()
            except Exception:
                pass

            _cleanup()

            QMessageBox.critical(
                self,
                "Erro ao atualizar",
                msg,
            )

        def _on_finished():
            try:
                dlg.close()
            except Exception:
                pass

            _cleanup()

            QMessageBox.information(
                self,
                "Atualização",
                "O instalador foi iniciado. O aplicativo será fechado para concluir a atualização.",
            )
            QApplication.quit()

        worker.failed.connect(_on_failed)
        worker.finished.connect(_on_finished)
        thread.started.connect(worker.run)
        thread.start()