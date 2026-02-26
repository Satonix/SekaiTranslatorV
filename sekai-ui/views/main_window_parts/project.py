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
    QFileDialog,
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


class ProjectMixin:
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

    def _normalize_project_paths(self, project: dict) -> dict:
        pp = (project.get("project_path") or "").strip()
        if pp:
            project["project_path"] = os.path.abspath(pp)

        rp = (project.get("root_path") or "").strip()
        if rp:
            project["root_path"] = os.path.abspath(rp)

        return project

    def _open_project(self):
        from views.dialogs.open_project_dialog import OpenProjectDialog

        dlg = OpenProjectDialog(self.core, self)
        if not dlg.exec():
            return
        self._load_project(dlg.project_path)

    def _create_project(self):
        from views.dialogs.create_project_dialog import CreateProjectDialog

        dlg = CreateProjectDialog(self.core, self)
        if not dlg.exec():
            return
        self._load_project(dlg.project_path)

    def _load_project(self, project_path: str):
        from services.local_project_service import LocalProjectService

        try:
            project = LocalProjectService(app_name=self.app_name).open_project(project_path)
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return

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

        # Sempre lembrar a pasta do projeto (estável), não o input do diálogo
        self._remember_last_project(project.get("project_path") or project_path)

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

    def _open_project_settings(self):
        import copy
        from PySide6.QtWidgets import QMessageBox
        from views.dialogs.project_settings_dialog import ProjectSettingsDialog
        from services.local_project_service import LocalProjectService

        if not self.current_project:
            QMessageBox.information(
                self,
                "Configurações do Projeto",
                "Abra um projeto antes de editar as configurações.",
            )
            return

        # Evita abrir múltiplas instâncias (duplo clique / shortcut repetido)
        dlg = getattr(self, "_project_settings_dlg", None)
        try:
            if dlg is not None:
                dlg.raise_()
                dlg.activateWindow()
                return
        except Exception:
            pass

        project_copy = copy.deepcopy(self.current_project)

        def _on_save(updated_project: dict):
            saved = LocalProjectService(app_name=self.app_name).save_project(updated_project)
            saved = self._normalize_project_paths(saved)
            self.current_project = saved
            self._refresh_project_state()
            return saved

        dlg = ProjectSettingsDialog(self, project=project_copy, on_save=_on_save)
        self._project_settings_dlg = dlg
        try:
            dlg.exec()
        finally:
            self._project_settings_dlg = None
    def _refresh_project_state(self):
        has_project = self.current_project is not None
        has_tab = self._current_file_tab() is not None
        logged_in = bool(self.api_token)

        # "Salvar Projeto" deve ficar disponível mesmo sem abas abertas.
        # Caso contrário, dá a impressão de que o projeto/configurações não salvam.
        self.action_save_project.setEnabled(has_project)
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
            rep_path = path + ".conflicts.json"
            try:
                with open(rep_path, "w", encoding="utf-8") as f:
                    json.dump([c.__dict__ for c in report.conflicts], f, ensure_ascii=False, indent=2)
                msg += f"\n\nConflitos exportados em:\n{rep_path}"
            except Exception:
                pass

        QMessageBox.information(self, "Sincronização", msg)

        self._refresh_open_tabs_from_state()

    def _refresh_open_tabs_from_state(self):
        try:
            for i in range(self.tabs.count()):
                tab = self.tabs.widget(i)
                if hasattr(tab, "load_project_state_if_exists") and getattr(tab, "file_path", None):
                    tab.load_project_state_if_exists(self.current_project)
        except Exception:
            pass

    def _save_all_open_files_state(self):
        if not self.current_project:
            return

        # Sempre persiste o project.json também (mesmo sem abas abertas),
        # para garantir que qualquer mudança em memória não se perca.
        try:
            from services.local_project_service import LocalProjectService

            saved = LocalProjectService(app_name=self.app_name).save_project(self.current_project)
            self.current_project = self._normalize_project_paths(saved)
        except Exception as e:
            QMessageBox.warning(self, "Salvar Projeto", f"Falha ao salvar project.json:\n\n{e}")

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