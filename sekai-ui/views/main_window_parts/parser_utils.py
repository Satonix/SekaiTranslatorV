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


class ParserUtilsMixin:
    def _select_parser_with_fallback(self, ctx: ParseContext, text: str, parser_id: str | None):
        """
        Tenta parser_id exato; se falhar e tiver sufixo (profiles), tenta o base.
        Por fim, tenta autodetect (parser_id=None).
        """
        # 1) tentativa direta
        if parser_id:
            try:
                return select_parser(ctx, text, parser_id=parser_id)
            except Exception:
                pass

            # 2) fallback: tira sufixos (.yandere / .default etc.)
            if "." in parser_id:
                base = parser_id.rsplit(".", 1)[0]
                try:
                    return select_parser(ctx, text, parser_id=base)
                except Exception:
                    pass

        # 3) autodetect puro
        return select_parser(ctx, text, parser_id=None)


