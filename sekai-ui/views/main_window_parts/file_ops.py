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


class FileOpsMixin:
    # Extensões mínimas para o explorador/CTRL+F quando não houver parsers disponíveis
    FALLBACK_EXTENSIONS: tuple[str, ...] = (
        ".ks", ".ast", ".txt", ".json", ".csv", ".ini", ".xml", ".yml", ".yaml"
    )

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
            if size > 5 * 1024 * 1024:
                return False
        except Exception:
            pass
        return True


    def _on_tree_double_clicked(self, index):
        self._open_file(index)


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


    def _current_file_tab(self) -> FileTab | None:
        w = self.tabs.currentWidget()
        if isinstance(w, FileTab):
            return w
        return None

    def _undo_current(self):
        tab = self._current_file_tab()
        if tab and hasattr(tab, "undo"):
            tab.undo()

    def _redo_current(self):
        tab = self._current_file_tab()
        if tab and hasattr(tab, "redo"):
            tab.redo()


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


    def _open_file(self, index):
        # Delegated to keep this file smaller and easier to debug
        from services.file_ops_service import open_file
        return open_file(self, index)


    def closeEvent(self, event):
        try:
            if self._ai_thread is not None:
                QMessageBox.information(self, "Tradução", "Aguarde a tradução terminar antes de fechar.")
                event.ignore()
                return

            if self.current_project:
                def _tab_has_unsaved(tab: FileTab) -> bool:
                    if getattr(tab, "is_dirty", False):
                        return True

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
            pass

        super().closeEvent(event)


