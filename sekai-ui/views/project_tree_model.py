from __future__ import annotations

import os
from typing import Callable, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileSystemModel

from models import project_state_store
from services.file_progress_service import get_file_progress


class ProjectTreeModel(QFileSystemModel):
    def __init__(self, *, project_getter: Callable[[], dict | None], supported_exts_getter: Callable[[], set[str]], live_progress_getter: Callable[[str], dict[str, Any] | None] | None = None, parent=None):
        super().__init__(parent)
        self._project_getter = project_getter
        self._supported_exts_getter = supported_exts_getter
        self._live_progress_getter = live_progress_getter
        self._progress_cache: dict[str, tuple[tuple[Any, ...], dict[str, Any]]] = {}

    def _current_project(self) -> dict | None:
        try:
            return self._project_getter()
        except Exception:
            return None

    def _supported_exts(self) -> set[str]:
        try:
            return {str(x).lower() for x in (self._supported_exts_getter() or set())}
        except Exception:
            return set()

    def _is_progress_candidate(self, path: str) -> bool:
        if not path or os.path.isdir(path):
            return False
        ext = os.path.splitext(path)[1].lower()
        supported = self._supported_exts()
        return bool(ext and supported and ext in supported)


    def _live_progress(self, path: str) -> tuple[tuple[Any, ...], dict[str, Any]] | None:
        getter = self._live_progress_getter
        if getter is None:
            return None
        try:
            payload = getter(path)
        except Exception:
            payload = None
        if not payload:
            return None
        try:
            sig = payload.get('signature', None)
            progress = payload.get('progress', None)
            if sig is None or not isinstance(progress, dict):
                return None
            return (('live', sig), progress)
        except Exception:
            return None

    def _state_signature(self, project: dict, file_path: str) -> tuple[Any, ...]:
        try:
            state_path = project_state_store.state_path_for_file(project, file_path)
        except Exception:
            return ('missing',)
        if not os.path.exists(state_path):
            return ('missing',)
        try:
            st = os.stat(state_path)
            return ('exists', getattr(st, 'st_mtime_ns', int(st.st_mtime * 1_000_000_000)), st.st_size)
        except Exception:
            return ('exists',)

    def _get_progress(self, path: str) -> dict[str, Any] | None:
        project = self._current_project()
        if not project or not self._is_progress_candidate(path):
            return None

        live = self._live_progress(path)
        if live is not None:
            sig, progress = live
            cached = self._progress_cache.get(path)
            if cached and cached[0] == sig:
                return cached[1]
            self._progress_cache[path] = (sig, progress)
            return progress

        sig = self._state_signature(project, path)
        cached = self._progress_cache.get(path)
        if cached and cached[0] == sig:
            return cached[1]

        progress = get_file_progress(project, path)
        self._progress_cache[path] = (sig, progress)
        return progress

    def data(self, index, role=Qt.DisplayRole):
        value = super().data(index, role)
        if not index.isValid() or index.column() != 0:
            return value

        path = self.filePath(index)
        progress = self._get_progress(path)
        if progress is None:
            return value

        if role == Qt.DisplayRole:
            try:
                base = str(value)
            except Exception:
                base = os.path.basename(path)
            return f"{base} ({int(progress.get('percent', 0))}%)"

        if role == Qt.ToolTipRole:
            done = int(progress.get('done', 0))
            total = int(progress.get('total', 0))
            percent = int(progress.get('percent', 0))
            if not progress.get('has_state'):
                return f"{os.path.basename(path)}\nTradução: 0%\nAinda sem estado salvo para este arquivo."
            if total == 0:
                return f"{os.path.basename(path)}\nTradução: 100%\nArquivo sem conteúdo traduzível salvo."
            return f"{os.path.basename(path)}\nTradução: {done}/{total} ({percent}%)"

        return value

    def refresh_progress(self, file_path: str | None = None) -> None:
        if file_path:
            self._progress_cache.pop(file_path, None)
            idx = self.index(file_path)
            if idx.isValid():
                self.dataChanged.emit(idx, idx, [Qt.DisplayRole, Qt.ToolTipRole])
                return

        self._progress_cache.clear()
        try:
            self.layoutAboutToBeChanged.emit()
        except Exception:
            pass
        try:
            self.layoutChanged.emit()
        except Exception:
            pass
