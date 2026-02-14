from __future__ import annotations

import os
import json
import copy
import re
import time

from PySide6.QtCore import Qt, QSettings, QThread, QTimer
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

# File tabs
from views.file_tab import FileTab

# Dialogs
from views.dialogs.login_dialog import LoginDialog
from views.dialogs.plugin_manager_dialog import PluginManagerDialog
from views.dialogs.open_project_dialog import OpenProjectDialog
from views.dialogs.create_project_dialog import CreateProjectDialog
from views.dialogs.project_settings_dialog import ProjectSettingsDialog
from views.dialogs.qa_dialog import QADialog
from views.dialogs.glossary_dialog import GlossaryDialog
from views.dialogs.translation_memory_dialog import TranslationMemoryDialog
from views.dialogs.about_dialog import AboutDialog
from views.dialogs.preferences_dialog import PreferencesDialog
from views.dialogs.search_dialog import SearchDialog, SearchResult

from services.search_replace_service import SearchReplaceService
from services.update_service import GitHubReleaseUpdater
from services import sync_service

from views.dialogs.translation_preview_dialog import TranslationPreviewDialog
from views.dialogs.progress_dialog import ProgressDialog
from views.workers.ai_translate_worker import AITranslateWorker

from parsers.autodetect import select_parser
from parsers.manager import get_parser_manager
from parsers.base import ParseContext


class MainWindow(QMainWindow):
    """
    MainWindow – layout clássico do SekaiTranslator.
    UI-first, integração com core via IPC (para projetos + IA),
    e parsers 100% no UI (plugins).
    """

    # fallback mínimo caso não haja parsers instalados
    FALLBACK_EXTENSIONS = {".ks", ".txt", ".ast"}

    def __init__(self, core_client, app_version: str = "0.0.0"):
        super().__init__()

        self.core = core_client
        self.app_version = (app_version or "0.0.0").strip() or "0.0.0"
        self.current_project: dict | None = None

        # services
        self.search_service = SearchReplaceService(self)

        # auth state
        self.current_user: str | None = None
        self.api_token: str | None = None
        self.user_data: dict | None = None

        # path -> FileTab
        self._open_files: dict[str, FileTab] = {}

        # Async AI translation state (evita GC)
        self._ai_thread: QThread | None = None
        self._ai_worker: AITranslateWorker | None = None
        self._ai_progress: ProgressDialog | None = None

        # Contexto do batch atual
        self._ai_ctx: dict | None = None

        self.setWindowTitle("SekaiTranslator")
        self.resize(1500, 900)

        self._build_ui()
        self._build_menu()
        self._build_status_bar()

        # restaura login salvo (se existir)
        self._restore_login_from_settings()

        self._refresh_account_menu()
        self._refresh_project_state()

        # tenta abrir o último projeto automaticamente
        self._auto_open_last_project()

        # Atualiza estado de ações quando trocar de tab
        self.tabs.currentChanged.connect(lambda *_: self._refresh_project_state())

        # Auto-update (GitHub Releases)
        QTimer.singleShot(1500, self._auto_check_updates)

    # ============================================================
    # Settings
    # ============================================================
    def _entry_translation_text(self, e: dict) -> str:
        # Compat: após separar Search/Replace para SearchReplaceService,
        # algumas rotas ainda chamam este helper no MainWindow.
        return self.search_service._entry_translation_text(e)

    def _settings(self) -> QSettings:
        return QSettings("SekaiTranslator", "SekaiTranslator")

    def _remember_last_project(self, project_path: str) -> None:
        try:
            p = (project_path or "").strip()
            if not p:
                return
            self._settings().setValue("last_project_path", os.path.abspath(p))
        except Exception:
            pass

    def _get_last_project(self) -> str:
        try:
            v = self._settings().value("last_project_path", "")
            return (str(v) if v else "").strip()
        except Exception:
            return ""

    # ============================================================
    # Auth restore / URLs
    # ============================================================
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

    # ============================================================
    # UI
    # ============================================================
    def _build_ui(self):
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(self.main_splitter)

        # LEFT: Tree
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

        # RIGHT: Tabs
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)

        self.main_splitter.addWidget(self.tabs)
        self.main_splitter.setSizes([300, 1200])

    # ============================================================
    # Menu Bar
    # ============================================================
    def _build_menu(self):
        menubar = self.menuBar()

        # ---------- Arquivo ----------
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

        # ---------- Editar ----------
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

        # ---------- Ferramentas ----------
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

        # ---------- Plugins ----------
        plugins_menu = menubar.addMenu("Extensões")
        self.action_plugins = plugins_menu.addAction("Gerenciar Extensões", self._open_plugins)

        # ---------- Preferências ----------
        prefs_menu = menubar.addMenu("Preferências")
        self.action_prefs = prefs_menu.addAction("Configurações...", self._open_preferences)

        # ---------- Ajuda ----------
        help_menu = menubar.addMenu("Ajuda")
        self.action_about = help_menu.addAction("Sobre", self._open_about)

        # ---------- Conta ----------
        self.account_menu = menubar.addMenu("Conta")
        self.action_login = self.account_menu.addAction("Login", self._login)
        self.action_logout = self.account_menu.addAction("Logout", self._logout)

    # ============================================================
    # Status Bar
    # ============================================================
    def _build_status_bar(self):
        self.statusBar().showMessage("Pronto")

    # ============================================================
    # Parsers: supported extensions
    # ============================================================
    def _supported_extensions(self) -> set[str]:
        """
        Retorna extensões suportadas pelos parsers instalados (lowercase).
        Sempre inclui fallback.
        """
        exts: set[str] = set()
        try:
            mgr = get_parser_manager()
            for p in (mgr.all_plugins() if mgr else []):
                pexts = getattr(p, "extensions", None) or set()
                for e in pexts:
                    if not e:
                        continue
                    exts.add(str(e).lower())
        except Exception:
            exts = set()

        exts |= set(self.FALLBACK_EXTENSIONS)
        return exts

    def _is_openable_candidate(self, path: str) -> bool:
        """
        Heurística para evitar abrir binários enormes por engano.
        """
        try:
            if os.path.isdir(path):
                return False
            size = os.path.getsize(path)
            if size > 5 * 1024 * 1024:  # 5MB
                return False
        except Exception:
            pass
        return True

    # ============================================================
    # Tree handlers
    # ============================================================
    def _on_tree_double_clicked(self, index):
        self._open_file(index)

    # ============================================================
    # Tabs close
    # ============================================================
    def _close_tab(self, index: int):
        widget = self.tabs.widget(index)

        if self.current_project and isinstance(widget, FileTab):
            if getattr(widget, "is_dirty", False):
                res = QMessageBox.question(
                    self,
                    "Salvar alterações?",
                    f"O arquivo '{os.path.basename(widget.file_path)}' tem alterações não salvas.\n\nDeseja salvar antes de fechar?",
                    QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                    QMessageBox.Save,
                )

                if res == QMessageBox.Cancel:
                    return

                if res == QMessageBox.Save:
                    try:
                        widget.save_project_state(self.current_project)
                    except Exception as e:
                        QMessageBox.critical(self, "Erro", str(e))
                        return

        self.tabs.removeTab(index)

        for path, tab in list(self._open_files.items()):
            if tab is widget:
                del self._open_files[path]
                break

        self._refresh_project_state()

    # ============================================================
    # Helpers: current tab
    # ============================================================
    def _current_file_tab(self) -> FileTab | None:
        w = self.tabs.currentWidget()
        if isinstance(w, FileTab):
            return w
        return None

    def _get_tab_entries(self, tab: FileTab) -> list[dict]:
        if hasattr(tab, "_entries"):
            return tab._entries or []
        if hasattr(tab, "model") and hasattr(tab.model, "entries"):
            return tab.model.entries or []
        return []

    def _update_tab_title(self, tab: FileTab) -> None:
        idx = self.tabs.indexOf(tab)
        if idx < 0:
            return

        name = os.path.basename(getattr(tab, "file_path", "") or "Arquivo")
        if getattr(tab, "is_dirty", False):
            name = f"● {name}"
        self.tabs.setTabText(idx, name)

    # ============================================================
    # Project path normalization
    # ============================================================
    def _normalize_project_paths(self, project: dict) -> dict:
        pp = (project.get("project_path") or "").strip()
        if pp:
            project["project_path"] = os.path.abspath(pp)

        rp = (project.get("root_path") or "").strip()
        if rp:
            project["root_path"] = os.path.abspath(rp)

        return project

    # ============================================================
    # Project lifecycle
    # ============================================================
    def _open_project(self):
        dlg = OpenProjectDialog(self.core, self)
        if not dlg.exec():
            return
        self._load_project(dlg.project_path)

    def _create_project(self):
        dlg = CreateProjectDialog(self.core, self)
        if not dlg.exec():
            return
        self._load_project(dlg.project_path)

    def _load_project(self, project_path: str):
        resp = self.core.send("project.open", {"project_path": project_path})

        if resp.get("status") != "ok":
            QMessageBox.critical(self, "Erro", resp.get("message", "Falha ao abrir projeto"))
            return

        project = resp["payload"]["project"]
        project = self._normalize_project_paths(project)

        self.current_project = project
        self._open_files.clear()

        self.tree_header.setText(project.get("name", "Projeto"))

        root = project.get("root_path", "")
        src_index = self.fs_model.setRootPath(root)
        self.tree.setRootIndex(src_index)
        self.tree.setEnabled(True)

        self.tabs.clear()
        self._refresh_project_state()

        self._remember_last_project(project_path)

    def _auto_open_last_project(self) -> None:
        project_path = self._get_last_project()
        if not project_path:
            return

        project_path = os.path.abspath(project_path)

        if not os.path.exists(project_path):
            return

        if os.path.isdir(project_path):
            pj = os.path.join(project_path, "project.json")
            if not os.path.exists(pj):
                return

        try:
            self._load_project(project_path)
        except Exception:
            pass

    # ============================================================
    # Project settings dialog (salva no core: project.save)
    # ============================================================
    def _open_project_settings(self):
        if not self.current_project:
            QMessageBox.information(
                self,
                "Configurações do Projeto",
                "Abra um projeto antes de editar as configurações.",
            )
            return

        project_copy = copy.deepcopy(self.current_project)

        def _on_save(updated_project: dict):
            resp = self.core.send("project.save", {"project": updated_project})

            if resp.get("status") != "ok":
                QMessageBox.critical(
                    self,
                    "Erro",
                    resp.get("message", "Falha ao salvar configurações do projeto."),
                )
                return

            payload = resp.get("payload") or {}
            if isinstance(payload, dict) and payload.get("__error"):
                QMessageBox.critical(self, "Erro", str(payload["__error"]))
                return

            saved = payload.get("project")
            if isinstance(saved, dict):
                saved = self._normalize_project_paths(saved)
                self.current_project = saved

            self._refresh_project_state()

        dlg = ProjectSettingsDialog(
            self,
            project=project_copy,
            on_save=_on_save,
        )

        if dlg.exec():
            self._refresh_project_state()

    # ============================================================
    # File opening
    # ============================================================
    def _open_file(self, index):
        if not self.current_project:
            return

        path = self.fs_model.filePath(index)
        if not path or os.path.isdir(path):
            return

        if not self._is_openable_candidate(path):
            return

        ext = os.path.splitext(path)[1].lower()
        supported = self._supported_extensions()
        if ext and supported and ext not in supported:
            return

        if path in self._open_files:
            self.tabs.setCurrentWidget(self._open_files[path])
            return

        encoding = (self.current_project.get("encoding") or "utf-8").strip() or "utf-8"

        try:
            with open(path, "r", encoding=encoding, errors="replace") as f:
                text = f.read()
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return

        try:
            parser = select_parser(self.current_project, path, text)
            ctx = ParseContext(
                file_path=path,
                project=self.current_project,
                original_text=text,
            )
            entries = parser.parse(ctx, text)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Falha no parse: {e}")
            return

        # cria a aba ANTES de setar campos extras
        tab = FileTab(self)
        tab.file_path = path

        # trava parser/ctx usados no parse para export consistente
        tab.parser = parser
        tab.parse_ctx = ctx

        tab.set_entries(entries)

        # aplica estado salvo por cima do parse
        tab.load_project_state_if_exists(self.current_project)

        tab.dirtyChanged.connect(lambda *_: self._update_tab_title(tab))
        self._update_tab_title(tab)

        self.tabs.addTab(tab, os.path.basename(path))
        self.tabs.setCurrentWidget(tab)

        self._open_files[path] = tab
        self._refresh_project_state()


    # ============================================================
    # SAVE / EXPORT
    # ============================================================
    def _save_all_open_files_state(self):
        if not self.current_project:
            return

        errors: list[str] = []
        for path, tab in list(self._open_files.items()):
            try:
                tab.save_project_state(self.current_project)
            except Exception as e:
                errors.append(f"{os.path.basename(path)}: {e}")

        if errors:
            QMessageBox.warning(
                self,
                "Salvar Projeto",
                "Concluído com erros:\n\n" + "\n".join(errors[:30]),
            )
        else:
            self.statusBar().showMessage("Projeto salvo", 2500)

    def _export_current_file(self):
        tab = self._current_file_tab()
        if not tab or not self.current_project or not tab.file_path:
            return

        parser = getattr(tab, "parser", None)
        ctx = getattr(tab, "parse_ctx", None)

        # fallback defensivo, caso a aba venha de algum caminho antigo
        if parser is None or ctx is None:
            encoding = (self.current_project.get("encoding") or "utf-8").strip() or "utf-8"
            try:
                with open(tab.file_path, "r", encoding=encoding, errors="replace") as f:
                    text = f.read()
            except Exception:
                text = ""

            parser = select_parser(self.current_project, tab.file_path, text)
            ctx = ParseContext(file_path=tab.file_path, project=self.current_project, original_text=text)
            tab.parser = parser
            tab.parse_ctx = ctx

        try:
            out_path = tab.export_to_disk(self.current_project, parser=parser, ctx=ctx)
            self.statusBar().showMessage(f"Arquivo exportado: {os.path.basename(out_path)}", 2500)
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))


    def _export_project_batch(self):
        if not self.current_project:
            return

        root = (self.fs_model.rootPath() or "").strip()
        if not root or not os.path.isdir(root):
            QMessageBox.critical(self, "Erro", "Root do projeto inválido.")
            return

        encoding = (self.current_project.get("encoding") or "utf-8").strip() or "utf-8"
        supported = self._supported_extensions()

        errors: list[str] = []
        count_ok = 0

        for base, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d.lower() != "exports"]

            for fn in files:
                ext = os.path.splitext(fn)[1].lower()
                if ext and supported and ext not in supported:
                    continue

                src_path = os.path.join(base, fn)

                try:
                    with open(src_path, "r", encoding=encoding, errors="replace") as f:
                        text = f.read()

                    parser = select_parser(self.current_project, src_path, text)

                    try:
                        ctx = ParseContext(file_path=src_path, project=self.current_project, original_text=text)  # type: ignore
                    except TypeError:
                        ctx = ParseContext(file_path=src_path, project=self.current_project)

                    entries = parser.parse(ctx, text)

                    tmp = FileTab(self)
                    tmp.file_path = src_path
                    tmp.set_entries(entries)
                    tmp.load_project_state_if_exists(self.current_project)

                    out_text = parser.rebuild(ctx, tmp._entries)
                    out_path = FileTab.compute_export_path(self.current_project, src_path)

                    os.makedirs(os.path.dirname(out_path), exist_ok=True)
                    with open(out_path, "w", encoding=encoding, errors="strict") as f:
                        f.write(out_text)

                    count_ok += 1

                except Exception as e:
                    try:
                        rel = os.path.relpath(src_path, root)
                    except Exception:
                        rel = src_path
                    errors.append(f"{rel}: {e}")

        if errors:
            QMessageBox.warning(
                self,
                "Exportação em lote",
                f"Concluído com erros.\n\nOK: {count_ok}\nErros: {len(errors)}\n\n" + "\n".join(errors[:20]),
            )
        else:
            QMessageBox.information(self, "Exportação em lote", f"OK: {count_ok} arquivos exportados.")

        self.statusBar().showMessage("Exportação em lote finalizada", 3000)

    # ============================================================
    # Undo/Redo
    # ============================================================
    def _undo_current(self):
        tab = self._current_file_tab()
        if tab:
            tab.undo()

    def _redo_current(self):
        tab = self._current_file_tab()
        if tab:
            tab.redo()

    # ============================================================
    # AI translate (mantive como você enviou)
    # ============================================================
    def _translate_current_file_with_ai(self):
        tab = self._current_file_tab()
        if not tab or not self.current_project:
            return

        if not self.api_token:
            QMessageBox.information(self, "IA", "Faça login para usar Tradução com IA.")
            return

        entries = self._get_tab_entries(tab)
        if not entries:
            return

        if self._ai_thread is not None:
            return

        rows_visible = tab._visible_rows()
        if not rows_visible:
            QMessageBox.information(self, "IA", "Selecione pelo menos 1 linha na tabela para traduzir.")
            return

        source_rows: list[int] = []
        for vr in rows_visible:
            sr = tab._source_row_from_visible_row(vr)
            if sr is None:
                continue
            if 0 <= sr < len(entries):
                source_rows.append(sr)

        if not source_rows:
            QMessageBox.information(self, "IA", "Seleção inválida.")
            return

        items: list[dict] = []
        row_by_id: dict[str, int] = {}

        for sr in source_rows:
            e = entries[sr]
            if not e.get("is_translatable", True):
                continue

            text = (e.get("original") or "").strip()
            if not text:
                continue

            eid = e.get("entry_id") or str(sr)
            eid = str(eid)

            items.append({"id": eid, "text": text})
            row_by_id[eid] = sr

        if not items:
            QMessageBox.information(self, "IA", "Nenhuma linha selecionada é traduzível.")
            return

        target_lang = (self.current_project.get("target_language") or "pt-BR").strip() or "pt-BR"

        self._ai_progress = ProgressDialog(
            title="Tradução com IA",
            message="Traduzindo linhas selecionadas...",
            parent=self,
            cancellable=True,
        )
        self._ai_progress.set_total(len(items))
        self._ai_progress.show()

        self.action_translate_ai.setEnabled(False)
        self.statusBar().showMessage("Traduzindo com IA...", 0)

        payload: dict = {"items": items, "target_language": target_lang}

        preset = (self.current_project.get("ai_prompt_preset") or "default").strip() or "default"
        custom = (self.current_project.get("ai_custom_prompt_text") or "").strip()
        if preset == "custom" and custom:
            payload["custom_prompt_text"] = custom

        self._ai_ctx = {
            "tab": tab,
            "entries": entries,
            "items": items,
            "row_by_id": row_by_id,
            "source_rows": source_rows,
        }

        self._ai_thread = QThread(self)
        self._ai_worker = AITranslateWorker(self._proxy_url(), self.api_token, payload, timeout=120.0)
        self._ai_worker.moveToThread(self._ai_thread)

        self._ai_thread.started.connect(self._ai_worker.run)

        if hasattr(self._ai_worker, "progress"):
            self._ai_worker.progress.connect(self._on_ai_translate_progress)

        if hasattr(self._ai_worker, "cancel"):
            self._ai_progress.canceled.connect(self._ai_worker.cancel)

        if hasattr(self._ai_worker, "canceled"):
            self._ai_worker.canceled.connect(self._on_ai_translate_canceled)

        self._ai_worker.finished.connect(self._on_ai_translate_finished)
        self._ai_worker.failed.connect(self._on_ai_translate_failed)

        self._ai_worker.finished.connect(self._ai_thread.quit)
        self._ai_worker.failed.connect(self._ai_thread.quit)
        if hasattr(self._ai_worker, "canceled"):
            self._ai_worker.canceled.connect(self._ai_thread.quit)

        self._ai_thread.finished.connect(self._on_ai_translate_thread_finished)

        self._ai_thread.start()

    def _on_ai_translate_progress(self, done: int, total: int):
        if self._ai_progress:
            self._ai_progress.set_total(int(total or 0))
            self._ai_progress.set_progress(int(done or 0))

    def _on_ai_translate_canceled(self):
        try:
            if self._ai_progress:
                self._ai_progress.close()
        except Exception:
            pass
        self.statusBar().showMessage("Tradução cancelada", 2000)

    def _on_ai_translate_failed(self, msg: str):
        try:
            if self._ai_progress:
                self._ai_progress.close()
        except Exception:
            pass

        QMessageBox.critical(self, "Erro", msg)
        self.statusBar().showMessage("Erro na tradução", 3000)

    def _on_ai_translate_finished(self, resp: dict):
        try:
            if self._ai_progress:
                self._ai_progress.close()
        except Exception:
            pass
        self._ai_progress = None

        ctx = self._ai_ctx or {}
        tab: FileTab | None = ctx.get("tab")
        entries: list[dict] = ctx.get("entries") or []
        items: list[dict] = ctx.get("items") or []
        row_by_id: dict[str, int] = ctx.get("row_by_id") or {}
        source_rows: list[int] = ctx.get("source_rows") or []

        if not tab or not entries:
            return

        if isinstance(resp, dict) and resp.get("error"):
            QMessageBox.critical(self, "Erro", str(resp.get("error")))
            self.statusBar().showMessage("Erro na tradução", 3000)
            return

        if not (isinstance(resp, dict) and isinstance(resp.get("results"), list)):
            QMessageBox.critical(self, "Erro", "Resposta inesperada do proxy (batch).")
            self.statusBar().showMessage("Erro na tradução", 3000)
            return

        by_id: dict[str, str] = {}
        for r in resp["results"]:
            if not isinstance(r, dict):
                continue
            rid = str(r.get("id") or "").strip()
            tr = r.get("translation")
            if rid and isinstance(tr, str):
                by_id[rid] = tr

        if not by_id:
            QMessageBox.critical(self, "Erro", "Proxy retornou results vazio.")
            self.statusBar().showMessage("Erro na tradução", 3000)
            return

        preview_rows = [row_by_id[i["id"]] for i in items if str(i.get("id")) in row_by_id]
        preview = TranslationPreviewDialog(
            self,
            entries=entries,
            source_rows=preview_rows,
            translations_by_id=by_id,
        )
        if not preview.exec():
            self.statusBar().showMessage("Tradução cancelada", 2000)
            return

        changed_rows: list[int] = []
        before_snap: list[dict] = []

        for sr in source_rows:
            if not (0 <= sr < len(entries)):
                continue

            e = entries[sr]
            if not e.get("is_translatable", True):
                continue

            eid = str(e.get("entry_id") or str(sr))
            new_tr = by_id.get(eid)
            if new_tr is None:
                continue

            old_tr = e.get("translation") or ""
            old_status = e.get("status") or "untranslated"

            if old_tr == new_tr and old_status == "in_progress":
                continue

            changed_rows.append(sr)
            before_snap.append({"translation": old_tr, "status": old_status})

            e["translation"] = new_tr
            e["status"] = "in_progress"

        if not changed_rows:
            self.statusBar().showMessage("Nada para atualizar", 2500)
            return

        after_snap: list[dict] = []
        for sr in changed_rows:
            e = entries[sr]
            after_snap.append({"translation": e.get("translation") or "", "status": e.get("status") or "untranslated"})

        tab.record_undo_for_rows(changed_rows, before=before_snap, after=after_snap)

        for sr in changed_rows:
            vr = tab._visible_row_from_source_row(sr)
            if vr is not None:
                tab.model.refresh_row(vr)

        tab.set_dirty(True)
        tab._refresh_editor_from_selection()

        self.statusBar().showMessage("Tradução aplicada (em edição)", 2500)

    def _on_ai_translate_thread_finished(self):
        try:
            self.action_translate_ai.setEnabled(True)
        except Exception:
            pass

        self._ai_worker = None
        self._ai_thread = None
        self._ai_ctx = None

        try:
            if self._ai_progress:
                self._ai_progress.close()
        except Exception:
            pass
        self._ai_progress = None

        self._refresh_project_state()

    # ============================================================
    # Account
    # ============================================================
    def _login(self):
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

    # ============================================================
    # Dialogs
    # ============================================================
    def _open_plugins(self):
        PluginManagerDialog(self).exec()

    def _open_qa(self):
        QADialog(self).exec()

    def _open_glossary(self):
        GlossaryDialog(self).exec()

    def _open_tm(self):
        TranslationMemoryDialog(self).exec()

    def _open_about(self):
        AboutDialog(self).exec()

    def _open_preferences(self):
        PreferencesDialog(self).exec()

    # ============================================================
    # Search (Ctrl+F)
    # ============================================================
    def _open_search(self):
        """Abre o diálogo de busca (Ctrl+F)."""
        allow_project = bool(self.current_project)
        default_scope = "project" if allow_project else "file"

        dlg = SearchDialog(
            parent=self,
            do_search=self.search_service._search_run,
            replace_one=self.search_service._search_replace_one,
            replace_all=self.search_service._search_replace_all,
            open_result=self.search_service._search_open_result,
            default_scope=default_scope,
        )

        if not allow_project:
            try:
                dlg.rb_project.setEnabled(False)
                dlg.rb_file.setChecked(True)
            except Exception:
                pass

        dlg.exec()












    def _replace_all_in_open_tab(self, tab: FileTab, rx: re.Pattern, repl: str) -> int:
        entries = getattr(tab, "_entries", []) or []
        changed_rows: list[int] = []
        before: list[dict] = []
        after: list[dict] = []
        total_replacements = 0

        for i, e in enumerate(entries):
            if not isinstance(e, dict):
                continue

            old_v = self._entry_translation_text(e)
            if not isinstance(old_v, str) or not old_v:
                continue

            new_v, n = rx.subn(repl, old_v)
            if n <= 0 or new_v == old_v:
                continue

            total_replacements += int(n)
            changed_rows.append(i)
            before.append({"translation": old_v, "status": e.get("status") or "untranslated"})
            e["translation"] = new_v
            after.append({"translation": new_v, "status": e.get("status") or "untranslated"})

        if not changed_rows:
            return 0

        tab.record_undo_for_rows(changed_rows, before=before, after=after)
        tab.set_dirty(True)

        for r in changed_rows:
            vr = tab._visible_row_from_source_row(r)
            if vr is not None:
                tab.model.refresh_row(vr)

        tab._refresh_editor_from_selection()
        self._update_tab_title(tab)
        return total_replacements

    def _replace_all_in_project(self, rx: re.Pattern, repl: str) -> int:
        root = (self.current_project.get("root_path") or "").strip()
        if not root or not os.path.isdir(root):
            return 0

        supported = self._supported_extensions()
        encoding = (self.current_project.get("encoding") or "utf-8").strip() or "utf-8"

        total_replacements = 0
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            for base, dirs, files in os.walk(root):
                dirs[:] = [d for d in dirs if d.lower() != "exports"]

                for fn in files:
                    ext = os.path.splitext(fn)[1].lower()
                    if ext and supported and ext not in supported:
                        continue

                    path = os.path.join(base, fn)
                    if not self._is_openable_candidate(path):
                        continue

                    abs_path = os.path.abspath(path)

                    # If open, edit in-memory.
                    tab = self._open_files.get(abs_path)
                    if tab is not None:
                        total_replacements += int(self._replace_all_in_open_tab(tab, rx, repl) or 0)
                        continue

                    try:
                        with open(abs_path, "r", encoding=encoding, errors="replace") as f:
                            text = f.read()
                        parser = select_parser(self.current_project, abs_path, text)
                        ctx = ParseContext(file_path=abs_path, project=self.current_project, original_text=text)
                        entries = parser.parse(ctx, text)
                    except Exception:
                        continue

                    # apply saved state (so we can replace in translation field)
                    try:
                        st = project_state_store.load_file_state(self.current_project, abs_path)
                        if st and getattr(st, "entries", None):
                            by_id: dict[str, dict] = {}
                            for se in st.entries:
                                if not isinstance(se, dict):
                                    continue
                                se_eid = se.get("entry_id")
                                if se_eid is None:
                                    continue
                                by_id[str(se_eid)] = se
                            if by_id:
                                for ce in entries:
                                    if not isinstance(ce, dict):
                                        continue
                                    eid = ce.get("entry_id")
                                    key = str(eid) if eid is not None else ""
                                    if key and key in by_id:
                                        se = by_id[key]
                                        if "translation" in se:
                                            ce["translation"] = se.get("translation") or ""
                                        if "status" in se:
                                            ce["status"] = se.get("status") or "untranslated"
                    except Exception:
                        pass

                    changed_any = False
                    for e in entries:
                        if not isinstance(e, dict):
                            continue
                        old_v = self._entry_translation_text(e)
                        if not isinstance(old_v, str) or not old_v:
                            continue
                        new_v, n = rx.subn(repl, old_v)
                        if n > 0 and new_v != old_v:
                            e["translation"] = new_v
                            total_replacements += int(n)
                            changed_any = True

                    if changed_any:
                        try:
                            project_state_store.save_file_state(self.current_project, abs_path, entries)
                        except Exception:
                            pass
        finally:
            QApplication.restoreOverrideCursor()

        return total_replacements

    def _refresh_project_state(self):
        has_project = self.current_project is not None
        has_tab = self._current_file_tab() is not None
        logged_in = bool(self.api_token)

        self.action_save_project.setEnabled(has_project and len(self._open_files) > 0)
        self.action_export_file.setEnabled(has_project and has_tab)
        self.action_export_batch.setEnabled(has_project)

        self.action_undo.setEnabled(has_tab)
        self.action_redo.setEnabled(has_tab)

        try:
            self.action_search.setEnabled(has_tab or has_project)
        except Exception:
            pass

        self.action_translate_ai.setEnabled(has_project and has_tab and logged_in and self._ai_thread is None)
        self.action_open_qa.setEnabled(has_project)
        self.action_glossary.setEnabled(True)
        self.action_tm.setEnabled(True)

        try:
            self.action_project_settings.setEnabled(has_project)
        except Exception:
            pass

    # ============================================================
    # Close behavior
    # ============================================================
    
    # =================================================
    # Sync export/import (offline collaboration)
    # =================================================
    def _export_sync(self):
        if not self.current_project:
            QMessageBox.information(self, "Sincronização", "Nenhum projeto aberto.")
            return

        payload = sync_service.export_sync_snapshot(self.current_project)

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Sincronização",
            "",
            "Sekai Sync (*.sekai-sync.json);;JSON (*.json)",
        )
        if not path:
            return
        if not (path.lower().endswith(".json")):
            path += ".sekai-sync.json"

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "Sincronização", f"Exportado com sucesso:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))

    def _import_sync(self):
        if not self.current_project:
            QMessageBox.information(self, "Sincronização", "Nenhum projeto aberto.")
            return

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Importar Sincronização",
            "",
            "Sekai Sync (*.sekai-sync.json *.json);;Todos (*.*)",
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return

        try:
            report = sync_service.import_sync_snapshot(self.current_project, payload)
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return

        msg = f"Aplicadas: {report.applied}\nIgnoradas (mais antigas): {report.skipped_older}\nConflitos: {len(report.conflicts)}"
        if report.base_mismatch:
            msg = "Aviso: project_id diferente (possível projeto diferente).\n\n" + msg

        if report.conflicts:
            # write conflict report next to imported file
            rep_path = path + ".conflicts.json"
            try:
                with open(rep_path, "w", encoding="utf-8") as f:
                    json.dump([c.__dict__ for c in report.conflicts], f, ensure_ascii=False, indent=2)
                msg += f"\n\nConflitos exportados em:\n{rep_path}"
            except Exception:
                pass

        QMessageBox.information(self, "Sincronização", msg)

        # refresh current open tab state if any
        self._refresh_open_tabs_from_state()

    def _refresh_open_tabs_from_state(self):
        # Reload state into open tabs to reflect imported progress
        try:
            for i in range(self.tabs.count()):
                tab = self.tabs.widget(i)
                if hasattr(tab, "load_project_state_if_exists") and getattr(tab, "file_path", None):
                    tab.load_project_state_if_exists(self.current_project)
        except Exception:
            pass

    def closeEvent(self, event):
        try:
            # Bloqueia fechar durante tradução IA
            if self._ai_thread is not None:
                QMessageBox.information(self, "Tradução", "Aguarde a tradução terminar antes de fechar.")
                event.ignore()
                return

            if self.current_project:
                def _tab_has_unsaved(tab: FileTab) -> bool:
                    if getattr(tab, "is_dirty", False):
                        return True

                    # Fallback: sessão de edição ativa com mudanças pendentes
                    try:
                        ed = getattr(tab, "editor", None)
                        sess = getattr(ed, "_session", None)
                        if sess is not None and getattr(sess, "is_active", lambda: False)():
                            changed = getattr(sess, "_changed_indices", None)
                            if changed:
                                return True
                    except Exception:
                        pass

                    return False

                dirty_tabs = [
                    t for t in self._open_files.values()
                    if isinstance(t, FileTab) and _tab_has_unsaved(t)
                ]

                if dirty_tabs:
                    res = QMessageBox.question(
                        self,
                        "Salvar alterações?",
                        f"Existem {len(dirty_tabs)} arquivo(s) com alterações não salvas.\n\nDeseja salvar antes de sair?",
                        QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                        QMessageBox.Save,
                    )

                    if res == QMessageBox.Cancel:
                        event.ignore()
                        return

                    if res == QMessageBox.Save:
                        errors: list[str] = []
                        for tab in dirty_tabs:
                            try:
                                tab.save_project_state(self.current_project)
                                if hasattr(tab, "set_dirty"):
                                    tab.set_dirty(False)
                            except Exception as e:
                                errors.append(f"{os.path.basename(tab.file_path)}: {e}")

                        if errors:
                            QMessageBox.critical(
                                self,
                                "Erro ao salvar",
                                "Não foi possível salvar tudo:\n\n" + "\n".join(errors[:30]),
                            )
                            event.ignore()
                            return

        except Exception:
            # mantém o fechamento normal se algo inesperado ocorrer
            pass

        super().closeEvent(event)
        
    def _auto_check_updates(self):
        try:
            from services.update_service import GitHubUpdater

            # ajuste se você já tiver APP_VERSION em outro lugar
            current_version = getattr(self, "app_version", "0.1.0")

            updater = GitHubUpdater(
                owner="Satonix",
                repo="SekaiTranslator",
                current_version=current_version,
            )

            info = updater.fetch_latest()
            if not info:
                return

            from PySide6.QtWidgets import QMessageBox

            msg = QMessageBox(self)
            msg.setWindowTitle("Atualização disponível")
            msg.setText(
                f"Nova versão disponível: {info.version}\n\n"
                f"Você está usando: {current_version}\n\n"
                "Deseja atualizar agora?"
            )
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setDefaultButton(QMessageBox.Yes)

            if msg.exec() == QMessageBox.Yes:
                updater.download_and_install(info)
                from PySide6.QtWidgets import QApplication
                QApplication.quit()

        except Exception:
            # nunca deixar update quebrar o app
            pass

