from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QButtonGroup,
    QCheckBox,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressDialog,
)


@dataclass(frozen=True)
class SearchResult:
    scope: str
    file_path: str
    source_row: int
    entry_id: str
    field: str
    snippet: str


class SearchDialog(QDialog):
    """Ctrl+F dialog (Localizar/Substituir).

    The dialog is UI-only; it depends on callables injected by MainWindow to:
    - do_search(query, params) -> list[SearchResult]
    - open_result(SearchResult) -> None
    - replace_one(SearchResult, query, replace_text, params) -> bool
    - replace_all(query, replace_text, params) -> int
    """

    def __init__(
        self,
        parent,
        *,
        default_scope: str = "file",
        do_search: Callable[[str, dict], list[SearchResult]],
        open_result: Callable[[SearchResult], None],
        replace_one: Callable[[SearchResult, str, str, dict], bool],
        replace_all: Callable[[str, str, dict], int],
    ):
        super().__init__(parent)

        self._do_search = do_search
        self._open_result = open_result
        self._replace_one = replace_one
        self._replace_all = replace_all

        self._last_query: str = ""
        self._last_params: dict = {}

        self.setWindowTitle("Buscar")
        self.resize(900, 520)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        row_q = QHBoxLayout()
        row_q.addWidget(QLabel("Texto:"))
        self.query = QLineEdit()
        self.query.setPlaceholderText("Digite para buscar…")
        row_q.addWidget(self.query, 1)

        self.btn_find = QPushButton("Localizar")
        self.btn_find.clicked.connect(self._on_search_clicked)
        row_q.addWidget(self.btn_find)

        root.addLayout(row_q)

        row_r = QHBoxLayout()
        row_r.addWidget(QLabel("Substituir por:"))
        self.replace = QLineEdit()
        self.replace.setPlaceholderText("Texto de substituição…")
        row_r.addWidget(self.replace, 1)

        self.btn_replace = QPushButton("Substituir")
        self.btn_replace.clicked.connect(self._on_replace_clicked)
        row_r.addWidget(self.btn_replace)

        self.btn_replace_all = QPushButton("Substituir tudo")
        self.btn_replace_all.clicked.connect(self._on_replace_all_clicked)
        row_r.addWidget(self.btn_replace_all)

        root.addLayout(row_r)

        row_scope = QHBoxLayout()
        row_scope.addWidget(QLabel("Escopo:"))

        self.scope_group = QButtonGroup(self)
        self.rb_file = QRadioButton("Arquivo atual")
        self.rb_project = QRadioButton("Projeto inteiro")
        self.scope_group.addButton(self.rb_file)
        self.scope_group.addButton(self.rb_project)
        row_scope.addWidget(self.rb_file)
        row_scope.addWidget(self.rb_project)
        row_scope.addStretch(1)

        if (default_scope or "file") == "project":
            self.rb_project.setChecked(True)
        else:
            self.rb_file.setChecked(True)

        root.addLayout(row_scope)

        row_opts = QHBoxLayout()
        self.ck_original = QCheckBox("Original")
        self.ck_original.setChecked(False)
        self.ck_translation = QCheckBox("Tradução")
        self.ck_translation.setChecked(True)
        self.ck_case = QCheckBox("Case-sensitive")
        self.ck_regex = QCheckBox("Regex")
        row_opts.addWidget(QLabel("Buscar em:"))
        row_opts.addWidget(self.ck_original)
        row_opts.addWidget(self.ck_translation)
        row_opts.addSpacing(12)
        row_opts.addWidget(self.ck_case)
        row_opts.addWidget(self.ck_regex)
        row_opts.addStretch(1)
        root.addLayout(row_opts)

        self.results = QListWidget()
        self.results.itemDoubleClicked.connect(self._open_selected)
        root.addWidget(self.results, 1)

        hint = QLabel("Dica: duplo-clique em um resultado para abrir e selecionar a linha.")
        hint.setStyleSheet("color: #999;")
        root.addWidget(hint)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.btn_close = QPushButton("Fechar")
        self.btn_close.clicked.connect(self.reject)
        bottom.addWidget(self.btn_close)
        root.addLayout(bottom)

        self.query.returnPressed.connect(self._on_search_clicked)
        self.replace.returnPressed.connect(self._on_replace_clicked)

    def _params(self) -> dict:
        scope = "project" if self.rb_project.isChecked() else "file"
        return {
            "scope": scope,
            "in_original": bool(self.ck_original.isChecked()),
            "in_translation": bool(self.ck_translation.isChecked()),
            "case_sensitive": bool(self.ck_case.isChecked()),
            "regex": bool(self.ck_regex.isChecked()),
        }

    def _on_search_clicked(self) -> None:
        q = (self.query.text() or "").strip()
        if not q:
            return

        params = self._params()
        if not params["in_original"] and not params["in_translation"]:
            QMessageBox.information(self, "Buscar", "Marque pelo menos 'Original' ou 'Tradução'.")
            return

        pd: Optional[QProgressDialog] = None
        if params.get("scope") == "project":
            pd = QProgressDialog("Buscando no projeto…", "Cancelar", 0, 0, self)
            pd.setWindowModality(Qt.WindowModal)
            pd.setAutoClose(True)
            pd.setAutoReset(True)
            pd.show()
            QApplication.processEvents()

        try:
            found = self._do_search(q, params)
        except Exception as e:
            if pd:
                try:
                    pd.close()
                except Exception:
                    pass
            QMessageBox.critical(self, "Buscar", str(e))
            return
        finally:
            if pd:
                try:
                    pd.close()
                except Exception:
                    pass

        self.results.clear()

        self._last_query = q
        self._last_params = dict(params)

        if not found:
            it = QListWidgetItem("Nenhum resultado.")
            it.setFlags(it.flags() & ~Qt.ItemIsSelectable)
            self.results.addItem(it)
            return

        for r in found:
            base = os.path.basename(r.file_path)
            field = "Orig" if r.field == "original" else "Tr"
            text = f"{base}  •  linha {r.source_row + 1}  •  {field}: {r.snippet}"
            it = QListWidgetItem(text)
            it.setData(Qt.UserRole, r)
            self.results.addItem(it)

        self.results.setCurrentRow(0)

    def _ensure_results(self) -> list[SearchResult]:
        """Ensures results are present and up-to-date for current query/params."""
        q = (self.query.text() or "").strip()
        if not q:
            return []

        params = self._params()
        if q != self._last_query or params != self._last_params or self.results.count() == 0:
            self._on_search_clicked()

        out: list[SearchResult] = []
        for i in range(self.results.count()):
            it = self.results.item(i)
            if not it:
                continue
            r = it.data(Qt.UserRole)
            if isinstance(r, SearchResult):
                out.append(r)
        return out

    def _current_result(self) -> Optional[SearchResult]:
        it = self.results.currentItem()
        if not it:
            return None
        r = it.data(Qt.UserRole)
        return r if isinstance(r, SearchResult) else None

    def _on_replace_clicked(self) -> None:
        q = (self.query.text() or "").strip()
        if not q:
            return

        repl = self.replace.text() or ""
        params = self._params()

        found = self._ensure_results()
        if not found:
            return

        r = self._current_result() or (found[0] if found else None)
        if not r:
            return

        try:
            changed = self._replace_one(r, q, repl, params)
        except Exception as e:
            QMessageBox.critical(self, "Substituir", str(e))
            return

        if not changed:
            QMessageBox.information(self, "Substituir", "Nada para substituir neste resultado.")
            return

        cur_row = max(self.results.currentRow(), 0)
        self._on_search_clicked()
        if self.results.count() > 0:
            self.results.setCurrentRow(min(cur_row, self.results.count() - 1))

    def _on_replace_all_clicked(self) -> None:
        q = (self.query.text() or "").strip()
        if not q:
            return

        repl = self.replace.text() or ""
        params = self._params()

        try:
            n = int(self._replace_all(q, repl, params) or 0)
        except Exception as e:
            QMessageBox.critical(self, "Substituir tudo", str(e))
            return

        QMessageBox.information(self, "Substituir tudo", f"Substituições aplicadas: {n}")
        self._on_search_clicked()

    def _open_selected(self) -> None:
        it = self.results.currentItem()
        if not it:
            return

        r = it.data(Qt.UserRole)
        if not isinstance(r, SearchResult):
            return

        try:
            self._open_result(r)
        except Exception as e:
            QMessageBox.critical(self, "Buscar", str(e))

