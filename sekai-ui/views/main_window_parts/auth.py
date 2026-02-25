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


class AuthMixin:
    def _restore_login_from_settings(self) -> None:
        """
        Restaura token + dados básicos (se existirem).
        Não valida no servidor; apenas restaura.
        """
        try:
            s = self._settings()
            token = (s.value("auth/api_token", "") or "").strip()
            if not token:
                self.api_token = None
                self.current_user = None
                self.user_data = None
                return

            self.api_token = token
            self.current_user = (s.value("auth/username", "") or "").strip() or "Usuário"
            self.user_data = {
                "full_name": (s.value("auth/full_name", "") or "").strip(),
                "role": (s.value("auth/role", "") or "").strip(),
            }
        except Exception:
            self.api_token = None
            self.current_user = None
            self.user_data = None


    def _proxy_url(self) -> str:
        """
        Default:
        https://green-gaur-846876.hostingersite.com/api/proxy.php

        Override:
        - env SEKAI_PROXY_URL
        - QSettings auth/proxy_url
        """
        try:
            s = self._settings()
            v = (s.value("auth/proxy_url", "") or "").strip()
            if v:
                return v
        except Exception:
            pass

        env = (os.environ.get("SEKAI_PROXY_URL") or "").strip()
        if env:
            return env

        return "https://green-gaur-846876.hostingersite.com/api/proxy.php"


    def _login(self):
        from views.dialogs.login_dialog import LoginDialog
        dlg = LoginDialog(self)
        if dlg.exec():
            self.current_user = dlg.username
            self.api_token = getattr(dlg, "api_token", None)
            self.user_data = getattr(dlg, "user_data", None)
            self._refresh_account_menu()
            self._refresh_project_state()


    def _logout(self):
        self.current_user = None
        self.api_token = None
        self.user_data = None

        try:
            s = self._settings()
            s.remove("auth/api_token")
            s.remove("auth/username")
            s.remove("auth/full_name")
            s.remove("auth/role")
        except Exception:
            pass

        self._refresh_account_menu()
        self._refresh_project_state()


    def _refresh_account_menu(self):
        if self.current_user:
            self.account_menu.setTitle(f"👤 {self.current_user}")
            self.action_login.setVisible(False)
            self.action_logout.setVisible(True)
        else:
            self.account_menu.setTitle("Conta")
            self.action_login.setVisible(True)
            self.action_logout.setVisible(False)


