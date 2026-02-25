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


class UIMixin:
    def _settings(self) -> QSettings:
        return QSettings(self.app_name, self.app_name)


    def _build_ui(self):
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(self.main_splitter)

        tree_container = QWidget()
        tree_layout = QVBoxLayout(tree_container)
        tree_layout.setContentsMargins(6, 6, 6, 6)

        self.tree_header = QLabel("Nenhum projeto aberto")
        self.tree_header.setStyleSheet("font-weight: bold; font-size: 14px;")
        tree_layout.addWidget(self.tree_header)

        self.fs_model = QFileSystemModel()
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
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)

        self.main_splitter.addWidget(self.tabs)
        self.main_splitter.setSizes([300, 1200])


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


