from __future__ import annotations

from typing import Any

from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import QMainWindow, QMessageBox

from services.search_replace_service import SearchReplaceService
from services.update_service import GitHubReleaseUpdater

from views.file_tab import FileTab
from views.main_window_parts import (
    UIMixin,
    ProjectMixin,
    FileOpsMixin,
    ExportOpsMixin,
    AuthMixin,
    ToolsMixin,
    UpdatesMixin,
    ParserUtilsMixin,
    MiscMixin,
)


class MainWindow(
    MiscMixin,
    ParserUtilsMixin,
    UIMixin,
    ProjectMixin,
    FileOpsMixin,
    ExportOpsMixin,
    AuthMixin,
    ToolsMixin,
    UpdatesMixin,
    QMainWindow,
):
    def __init__(self, core_client, app_version: str = "0.0.0", app_name: str = "SekaiTranslatorV"):
        super().__init__()

        self.core = core_client
        self.app_version = (app_version or "0.0.0").strip() or "0.0.0"
        self.app_name = (app_name or "SekaiTranslatorV").strip() or "SekaiTranslatorV"
        self.current_project: dict | None = None

        self.search_service = SearchReplaceService(self)

        try:
            from version import UPDATE_OWNER, UPDATE_REPO
        except Exception:
            UPDATE_OWNER, UPDATE_REPO = "Satonix", "SekaiTranslatorV"
        self.update_service = GitHubReleaseUpdater(
            owner=UPDATE_OWNER,
            repo=UPDATE_REPO,
            current_version=self.app_version,
        )

        self.current_user: str | None = None
        self.api_token: str | None = None
        self.user_data: dict | None = None

        self._open_files: dict[str, FileTab] = {}

        self._ai_thread: QThread | None = None
        self._ai_worker: Any = None
        self._ai_progress: Any = None

        self._ai_ctx: dict | None = None

        self.setWindowTitle(self.app_name)
        self.resize(1500, 900)

        self._build_ui()
        self._build_menu()
        self._build_status_bar()

        self._restore_login_from_settings()

        self._refresh_account_menu()
        self._refresh_project_state()

        self._auto_open_last_project()

        self.tabs.currentChanged.connect(lambda *_: self._refresh_project_state())

        QTimer.singleShot(1500, self._auto_check_updates)

