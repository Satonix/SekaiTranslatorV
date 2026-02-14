# views/dialogs/project_settings_tab.py

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGroupBox,
    QFormLayout,
    QLineEdit,
    QLabel,
    QPushButton,
    QFileDialog,
    QHBoxLayout,
    QComboBox,
    QMessageBox,
)

# Lista pequena e prática (você pode expandir depois)
ENCODINGS = [
    "utf-8",
    "utf-8-sig",
    "utf-16",
    "utf-16-le",
    "utf-16-be",
    "cp932",
    "shift_jis",
    "euc-jp",
    "gbk",
    "gb2312",
    "big5",
    "euc-kr",
    "windows-1252",
    "windows-1250",
    "windows-1251",
]


class ProjectSettingsTab(QWidget):
    """
    Tab "Projeto" das configurações.
    Responsável por editar:
      - name
      - root_path
      - encoding
      - engine
      - source_language
      - target_language

    API esperada pelo dialog:
      - load_project(project_dict)
      - apply_to_project(project_dict)
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        # ----------------------------
        # Info / Paths
        # ----------------------------
        box_info = QGroupBox("Projeto")
        form = QFormLayout(box_info)
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        # project_path (read-only)
        self.lbl_project_path = QLabel("—")
        self.lbl_project_path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_project_path.setStyleSheet("color: #AAA;")
        form.addRow("Caminho do projeto:", self.lbl_project_path)

        # name
        self.ed_name = QLineEdit()
        self.ed_name.setPlaceholderText("Nome do projeto (exibição)")
        form.addRow("Nome:", self.ed_name)

        # root_path + browse
        root_row = QWidget()
        root_layout = QHBoxLayout(root_row)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(6)

        self.ed_root_path = QLineEdit()
        self.ed_root_path.setPlaceholderText("Pasta raiz do jogo / scripts")

        self.btn_browse_root = QPushButton("Procurar...")
        self.btn_browse_root.clicked.connect(self._browse_root)

        root_layout.addWidget(self.ed_root_path, 1)
        root_layout.addWidget(self.btn_browse_root, 0)

        form.addRow("Root do jogo:", root_row)

        # encoding
        self.cmb_encoding = QComboBox()
        for enc in ENCODINGS:
            self.cmb_encoding.addItem(enc, enc)
        self.cmb_encoding.setEditable(True)
        self.cmb_encoding.setInsertPolicy(QComboBox.NoInsert)
        form.addRow("Encoding:", self.cmb_encoding)

        # engine
        self.cmb_engine = QComboBox()
        # valores exemplos; ajuste para sua lista real (o core aceita string)
        engines = [
            ("", "—"),
            ("kirikiri", "KiriKiri / KAG"),
            ("renpy", "Ren'Py"),
            ("unity", "Unity"),
            ("custom", "Custom"),
        ]
        for key, label in engines:
            self.cmb_engine.addItem(label, key)
        self.cmb_engine.setEditable(True)  # permite digitar engine id manual
        self.cmb_engine.setInsertPolicy(QComboBox.NoInsert)
        form.addRow("Engine:", self.cmb_engine)

        outer.addWidget(box_info)

        # ----------------------------
        # Languages
        # ----------------------------
        box_lang = QGroupBox("Idiomas")
        form2 = QFormLayout(box_lang)
        form2.setLabelAlignment(Qt.AlignLeft)
        form2.setFormAlignment(Qt.AlignTop)
        form2.setHorizontalSpacing(12)
        form2.setVerticalSpacing(8)

        self.cmb_source_lang = QComboBox()
        self.cmb_target_lang = QComboBox()

        # lista básica (BCP-47 simplificado)
        langs = [
            ("", "—"),
            ("ja", "Japanese (ja)"),
            ("en", "English (en)"),
            ("zh", "Chinese (zh)"),
            ("zh-CN", "Chinese Simplified (zh-CN)"),
            ("zh-TW", "Chinese Traditional (zh-TW)"),
            ("ko", "Korean (ko)"),
            ("pt-BR", "Português (Brasil) (pt-BR)"),
            ("pt-PT", "Português (Portugal) (pt-PT)"),
            ("es", "Español (es)"),
            ("ru", "Русский (ru)"),
        ]
        for code, label in langs:
            self.cmb_source_lang.addItem(label, code)
            self.cmb_target_lang.addItem(label, code)

        self.cmb_source_lang.setEditable(True)
        self.cmb_target_lang.setEditable(True)
        self.cmb_source_lang.setInsertPolicy(QComboBox.NoInsert)
        self.cmb_target_lang.setInsertPolicy(QComboBox.NoInsert)

        form2.addRow("Idioma de origem:", self.cmb_source_lang)
        form2.addRow("Idioma de destino:", self.cmb_target_lang)

        outer.addWidget(box_lang)
        outer.addStretch()

    # ----------------------------
    # UI actions
    # ----------------------------
    def _browse_root(self):
        start = self.ed_root_path.text().strip()
        if not start or not os.path.isdir(start):
            start = os.path.expanduser("~")

        path = QFileDialog.getExistingDirectory(self, "Selecionar pasta do jogo", start)
        if path:
            self.ed_root_path.setText(path)

    # ----------------------------
    # Public API
    # ----------------------------
    def load_project(self, project: dict) -> None:
        project = project or {}

        self.lbl_project_path.setText((project.get("project_path") or "—").strip() or "—")
        self.ed_name.setText((project.get("name") or "").strip())
        self.ed_root_path.setText((project.get("root_path") or "").strip())

        enc = (project.get("encoding") or "utf-8").strip() or "utf-8"
        idx = self.cmb_encoding.findData(enc)
        if idx < 0:
            # se não estiver na lista, joga no texto editável
            self.cmb_encoding.setCurrentText(enc)
        else:
            self.cmb_encoding.setCurrentIndex(idx)

        eng = (project.get("engine") or "").strip()
        idx = self.cmb_engine.findData(eng)
        if idx < 0:
            self.cmb_engine.setCurrentText(eng)
        else:
            self.cmb_engine.setCurrentIndex(idx)

        src = (project.get("source_language") or "").strip()
        dst = (project.get("target_language") or "pt-BR").strip() or "pt-BR"

        idx = self.cmb_source_lang.findData(src)
        if idx < 0:
            self.cmb_source_lang.setCurrentText(src)
        else:
            self.cmb_source_lang.setCurrentIndex(idx)

        idx = self.cmb_target_lang.findData(dst)
        if idx < 0:
            self.cmb_target_lang.setCurrentText(dst)
        else:
            self.cmb_target_lang.setCurrentIndex(idx)

    def apply_to_project(self, project: dict) -> None:
        """
        Valida e escreve no dict.
        Levanta Exception se inválido (dialog mostra QMessageBox).
        """
        name = self.ed_name.text().strip()
        root_path = self.ed_root_path.text().strip()
        encoding = (self.cmb_encoding.currentText() or "").strip()
        engine = (self.cmb_engine.currentText() or "").strip()

        source_language = (self.cmb_source_lang.currentText() or "").strip()
        target_language = (self.cmb_target_lang.currentText() or "").strip()

        if not name:
            raise ValueError("Nome do projeto não pode ficar vazio.")

        if not root_path:
            raise ValueError("Root do jogo não pode ficar vazio.")
        if not os.path.isdir(root_path):
            raise ValueError("Root do jogo inválido (a pasta não existe).")

        if not encoding:
            raise ValueError("Encoding não pode ficar vazio.")

        # grava no dict
        project["name"] = name
        project["root_path"] = root_path
        project["encoding"] = encoding
        project["engine"] = engine

        project["source_language"] = source_language
        project["target_language"] = target_language
