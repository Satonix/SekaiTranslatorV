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
    QMessageBox,
    QApplication,
    QCheckBox,
    QAbstractScrollArea,
)

from themes.theme_manager import ThemeManager
from views.background_canvas import BackgroundCanvas
from views.file_tab import FileTab
from views.project_tree_model import ProjectTreeModel

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


class UIMixin:
    def _settings(self) -> QSettings:
        return QSettings(self.app_name, self.app_name)

    def _apply_saved_theme(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        applied = ThemeManager.apply_saved_theme(app, self.app_name)
        self.setProperty("sekai_theme_name", applied)
        self._apply_background_settings()
        try:
            self.style().unpolish(self)
            self.style().polish(self)
        except Exception:
            pass
        try:
            self.update()
        except Exception:
            pass

    def _default_background_path(self) -> str:
        try:
            base_dir = Path(__file__).resolve().parents[2]
            path = base_dir / "assets" / "backgrounds" / "sekai_default_bg.png"
            if path.exists():
                return str(path)
        except Exception:
            pass
        return ""

    def _background_overlay_qss(self, enabled: bool) -> str:
        if not enabled:
            return ""

        try:
            overlay = int(self._settings().value("ui/background_overlay", 140) or 140)
        except Exception:
            overlay = 140

        return ThemeManager.build_overlay_stylesheet(
            enabled=enabled,
            overlay=overlay,
            app=QApplication.instance(),
        )

    def _refresh_background_overlay_targets(self, enabled: bool) -> None:
        try:
            targets = []
            for area in self.findChildren(QAbstractScrollArea):
                try:
                    area.setAttribute(Qt.WA_StyledBackground, True)
                except Exception:
                    pass
                viewport = getattr(area, "viewport", lambda: None)()
                if viewport is not None:
                    targets.append(viewport)
            for widget in targets:
                try:
                    widget.setProperty("sekaiOverlayViewport", bool(enabled))
                    widget.setAttribute(Qt.WA_StyledBackground, True)
                    widget.setAutoFillBackground(False)
                    widget.style().unpolish(widget)
                    widget.style().polish(widget)
                    widget.update()
                except Exception:
                    pass
        except Exception:
            pass

    def _apply_background_settings(self) -> None:
        host = getattr(self, "central_host", None)
        if host is None or not hasattr(host, "configure"):
            return
        s = self._settings()
        enabled = bool(s.value("ui/background_enabled", False, type=bool))
        image_path = (s.value("ui/background_path", "", type=str) or "").strip()
        overlay = s.value("ui/background_overlay", 140)
        try:
            overlay = int(overlay)
        except Exception:
            overlay = 140
        try:
            app = QApplication.instance()
            if app is not None:
                app.setProperty("sekai_background_enabled", bool(enabled))
                app.setProperty("sekai_background_overlay", int(overlay))
        except Exception:
            pass

        try:
            host.configure(
                enabled=enabled,
                image_path=image_path,
                overlay_opacity=overlay,
                fallback_path=self._default_background_path(),
                overlay_color=ThemeManager.background_overlay_color(
                    overlay=overlay,
                    app=QApplication.instance(),
                ),
            )
        except Exception:
            pass

        try:
            self.setStyleSheet(self._background_overlay_qss(enabled))
        except Exception:
            pass

        self._refresh_background_overlay_targets(enabled)


    def _refresh_tree_progress(self, file_path: str | None = None) -> None:
        try:
            if not file_path:
                self._tree_progress_refresh_all = True
            else:
                self._pending_tree_progress_paths.add(file_path)
            if not self._tree_progress_refresh_timer.isActive():
                self._tree_progress_refresh_timer.start()
        except Exception:
            pass

    def _flush_tree_progress_refresh(self) -> None:
        try:
            model = getattr(self, "fs_model", None)
            if model is None or not hasattr(model, "refresh_progress"):
                return
            if self._tree_progress_refresh_all:
                self._pending_tree_progress_paths.clear()
                self._tree_progress_refresh_all = False
                model.refresh_progress(None)
                return
            paths = list(self._pending_tree_progress_paths)
            self._pending_tree_progress_paths.clear()
            for path in paths:
                model.refresh_progress(path)
        except Exception:
            pass

    def _live_tree_progress_payload(self, file_path: str) -> dict[str, Any] | None:
        try:
            path = (file_path or '').strip()
            if not path:
                return None
            open_files = getattr(self, '_open_files', None) or {}
            tab = open_files.get(path)
            if tab is None:
                return None
            rev = int(getattr(tab, '_progress_revision', 0) or 0)
            cached = self._live_tree_progress_cache.get(path)
            if cached and cached[0] == rev:
                return {'signature': rev, 'progress': cached[1]}
            entries = getattr(tab, '_entries', None) or []
            from services.file_progress_service import compute_entries_progress
            done, total, percent = compute_entries_progress(entries)
            progress = {
                'has_state': True,
                'done': done,
                'total': total,
                'percent': percent,
                'is_full': percent >= 100,
            }
            self._live_tree_progress_cache[path] = (rev, progress)
            return {'signature': rev, 'progress': progress}
        except Exception:
            return None

    def _build_ui(self):
        self._pending_tree_progress_paths: set[str] = set()
        self._tree_progress_refresh_all = False
        self._tree_progress_refresh_timer = QTimer(self)
        self._tree_progress_refresh_timer.setSingleShot(True)
        self._tree_progress_refresh_timer.setInterval(120)
        self._tree_progress_refresh_timer.timeout.connect(self._flush_tree_progress_refresh)

        self._live_tree_progress_cache: dict[str, tuple[int, dict[str, Any]]] = {}
        self.central_host = BackgroundCanvas()
        self.central_host.setObjectName("mainBackgroundHost")
        self.central_layout = QVBoxLayout(self.central_host)
        self.central_layout.setContentsMargins(0, 0, 0, 0)
        self.central_layout.setSpacing(0)

        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setObjectName("mainSplitter")
        self.central_layout.addWidget(self.main_splitter)
        self.setCentralWidget(self.central_host)

        tree_container = QWidget()
        tree_container.setObjectName("projectTreePanel")
        tree_layout = QVBoxLayout(tree_container)
        tree_layout.setContentsMargins(6, 6, 6, 6)
        tree_layout.setSpacing(0)

        self.tree_header = QLabel("Nenhum projeto aberto")
        self.tree_header.setObjectName("sectionHeader")
        self.tree_header.setContentsMargins(0, 0, 0, 0)
        tree_layout.addWidget(self.tree_header)

        self.fs_model = ProjectTreeModel(
            project_getter=lambda: getattr(self, "current_project", None),
            supported_exts_getter=self._supported_extensions,
            live_progress_getter=self._live_tree_progress_payload,
            parent=self,
        )
        self.fs_model.setRootPath("")

        self.tree = QTreeView()
        self.tree.setModel(self.fs_model)
        self.tree.setHeaderHidden(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setMinimumWidth(220)
        self.tree.setMaximumWidth(400)
        self.tree.setEnabled(False)

        for i in range(1, 4):
            self.tree.hideColumn(i)

        self.tree.doubleClicked.connect(self._on_tree_double_clicked)

        tree_layout.addWidget(self.tree)
        self.main_splitter.addWidget(tree_container)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)

        self.main_splitter.addWidget(self.tabs)
        self.main_splitter.setSizes([300, 1200])
        self._apply_background_settings()


    def _build_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("Arquivo")
        self.action_open_project = file_menu.addAction("Abrir Projeto", self._open_project)
        self.action_create_project = file_menu.addAction("Criar Projeto", self._create_project)

        file_menu.addSeparator()
        self.action_project_settings = file_menu.addAction(
            "Configurações do Projeto...",
            self._open_project_settings,
        )
        self.action_project_settings.setShortcut(QKeySequence("Ctrl+,"))

        self.action_export_sync = file_menu.addAction(
            "Exportar Sincronização...",
            self._export_sync,
        )
        self.action_import_sync = file_menu.addAction(
            "Importar Sincronização...",
            self._import_sync,
        )

        file_menu.addSeparator()
        self.action_save_project = file_menu.addAction(
            "Salvar Projeto (Todos Abertos)",
            self._save_all_open_files_state,
        )
        file_menu.addSeparator()
        self.action_export_file = file_menu.addAction("Exportar Arquivo", self._export_current_file)
        self.action_export_batch = file_menu.addAction("Exportar Projeto (Lote)", self._export_project_batch)
        file_menu.addSeparator()
        self.action_exit = file_menu.addAction("Sair", self.close)

        edit_menu = menubar.addMenu("Editar")

        self.action_undo = edit_menu.addAction("Desfazer", self._undo_current)
        self.action_undo.setShortcut(QKeySequence.Undo)
        self.action_undo.setShortcutContext(Qt.ApplicationShortcut)

        self.action_redo = edit_menu.addAction("Refazer", self._redo_current)
        self.action_redo.setShortcut(QKeySequence("Ctrl+Shift+Z"))
        self.action_redo.setShortcutContext(Qt.ApplicationShortcut)

        edit_menu.addSeparator()
        self.action_search = edit_menu.addAction("Buscar...", self._open_search)
        self.action_search.setShortcut(QKeySequence.Find)
        self.action_search.setShortcutContext(Qt.ApplicationShortcut)

        tools_menu = menubar.addMenu("Ferramentas")

        self.action_translate_ai = tools_menu.addAction(
            "Traduzir com IA (Linhas Selecionadas)",
            self._translate_current_file_with_ai,
        )
        tools_menu.addSeparator()
        self.action_open_qa = tools_menu.addAction("QA (Arquivo / Projeto)", self._open_qa)
        tools_menu.addSeparator()
        self.action_glossary = tools_menu.addAction("Glossário", self._open_glossary)
        self.action_tm = tools_menu.addAction("Memória de Tradução", self._open_tm)

        plugins_menu = menubar.addMenu("Extensões")
        self.action_plugins = plugins_menu.addAction("Gerenciar Extensões", self._open_plugins)

        prefs_menu = menubar.addMenu("Preferências")
        self.action_prefs = prefs_menu.addAction("Configurações...", self._open_preferences)

        help_menu = menubar.addMenu("Ajuda")
        self.action_about = help_menu.addAction("Sobre", self._open_about)
        self.action_check_updates = help_menu.addAction("Verificar atualizações...", self._check_updates_now)

        self.account_menu = menubar.addMenu("Conta")
        self.action_login = self.account_menu.addAction("Login", self._login)
        self.action_logout = self.account_menu.addAction("Logout", self._logout)


    def _build_status_bar(self):
        self.statusBar().showMessage("Pronto")


