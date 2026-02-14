# views/dialogs/translation_preview_dialog.py

from __future__ import annotations

from typing import List, Dict

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableView,
    QHeaderView,
    QWidget,
)


class _PreviewModel(QAbstractTableModel):
    COLUMNS = ["Linha", "Original", "Tradução (IA)"]

    def __init__(self, rows: List[dict], parent=None):
        super().__init__(parent)
        self._rows = rows or []

    def rowCount(self, parent=QModelIndex()):
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()):
        return len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            if 0 <= section < len(self.COLUMNS):
                return self.COLUMNS[section]
            return None
        return section + 1

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        row = self._rows[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                return row.get("line", "")
            if col == 1:
                return row.get("original", "")
            if col == 2:
                return row.get("translation", "")

        if role == Qt.TextAlignmentRole:
            if col == 0:
                return Qt.AlignCenter
            return Qt.AlignLeft | Qt.AlignVCenter

        return None


class TranslationPreviewDialog(QDialog):
    """
    Preview antes de aplicar traduções.
    Read-only, confirma/cancela.

    Inputs:
      - entries: lista ALL entries (tab._entries)
      - source_rows: rows (SOURCE) selecionadas
      - translations_by_id: {entry_id: translation} (ids usados no batch)
    """

    def __init__(
        self,
        parent,
        *,
        entries: List[dict],
        source_rows: List[int],
        translations_by_id: Dict[str, str],
        title: str = "Preview de Tradução (IA)",
    ):
        super().__init__(parent)

        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(980, 520)

        self.confirmed: bool = False

        # Monta rows de preview (apenas as que possuem tradução retornada)
        preview_rows: List[dict] = []
        for r in source_rows or []:
            if not (0 <= r < len(entries)):
                continue
            e = entries[r]
            if not e.get("is_translatable", True):
                continue

            eid = e.get("entry_id") or str(r)
            tr = translations_by_id.get(str(eid))
            if tr is None:
                continue

            ln = e.get("line_number")
            line_display = ln if isinstance(ln, int) and ln > 0 else (r + 1)

            preview_rows.append(
                {
                    "line": line_display,
                    "original": e.get("original", "") or "",
                    "translation": tr,
                }
            )

        main = QVBoxLayout(self)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(10)

        header = QLabel("<b>Confira a tradução antes de aplicar</b>")
        main.addWidget(header)

        sub = QLabel(
            "As traduções abaixo serão aplicadas apenas nas linhas selecionadas.\n"
            "Clique em <b>Aplicar</b> para confirmar, ou <b>Cancelar</b> para descartar."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("color: #a0a0a0;")
        main.addWidget(sub)

        table_wrap = QWidget()
        table_l = QVBoxLayout(table_wrap)
        table_l.setContentsMargins(0, 0, 0, 0)

        self.table = QTableView(self)
        self.model = _PreviewModel(preview_rows, self)
        self.table.setModel(self.model)

        self.table.setSelectionBehavior(QTableView.SelectRows)
        self.table.setSelectionMode(QTableView.SingleSelection)
        self.table.setWordWrap(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)

        header_h = self.table.horizontalHeader()
        header_h.setStretchLastSection(True)
        header_h.setHighlightSections(False)
        header_h.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        header_h.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Linha
        header_h.setSectionResizeMode(1, QHeaderView.Stretch)           # Original
        header_h.setSectionResizeMode(2, QHeaderView.Stretch)           # Tradução

        table_l.addWidget(self.table)
        main.addWidget(table_wrap, 1)

        btns = QHBoxLayout()
        btns.addStretch()

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_apply = QPushButton("Aplicar")

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_apply.clicked.connect(self._apply)

        btns.addWidget(self.btn_cancel)
        btns.addWidget(self.btn_apply)

        main.addLayout(btns)

    def _apply(self):
        self.confirmed = True
        self.accept()
