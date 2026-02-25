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
)

EXPORT_ENCODINGS = [
    ("UTF-8", ("utf-8", False)),
    ("UTF-8 (com BOM)", ("utf-8", True)),
    ("UTF-16 LE (com BOM)", ("utf-16-le", True)),
    ("UTF-16 LE (sem BOM)", ("utf-16-le", False)),
    ("UTF-16 BE (com BOM)", ("utf-16-be", True)),
    ("UTF-16 BE (sem BOM)", ("utf-16-be", False)),
    ("Windows-1252", ("windows-1252", False)),
    ("Shift_JIS (CP932)", ("cp932", False)),
]


def _as_pair(v) -> tuple[str, bool] | None:
    """
    Qt/PySide pode devolver userData como list (QVariantList), não tuple.
    Aceita tuple/list de len==2.
    """
    if isinstance(v, (tuple, list)) and len(v) == 2:
        return (str(v[0] or "").strip(), bool(v[1]))
    return None


def _canonicalize_export(enc: str, bom: bool) -> tuple[str, bool]:
    enc = (enc or "").strip()
    low = enc.lower().replace("_", "-").strip()

    # compat: utf-16 genérico
    if low == "utf-16":
        return ("utf-16-le", True)

    # aliases comuns
    if low in ("utf-8-sig", "utf8-sig"):
        return ("utf-8", True)

    if low in ("utf-16-le-bom", "utf16-le-bom", "utf-16le-bom", "utf16le-bom"):
        return ("utf-16-le", True)

    if low in ("utf-16-be-bom", "utf16-be-bom", "utf-16be-bom", "utf16be-bom"):
        return ("utf-16-be", True)

    if low in ("utf-16le", "utf16le"):
        return ("utf-16-le", bool(bom))

    if low in ("utf-16be", "utf16be"):
        return ("utf-16-be", bool(bom))

    if not low:
        return ("utf-8", False)

    return (enc, bool(bom))


class ProjectSettingsTab(QWidget):
    """
    Tab "Projeto" das configurações.
    Responsável por editar:
      - name
      - root_path
      - encoding (entrada): sempre "auto"
      - export_encoding + export_bom (saída)
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

        box_info = QGroupBox("Projeto")
        form = QFormLayout(box_info)
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        self.lbl_project_path = QLabel("—")
        self.lbl_project_path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_project_path.setStyleSheet("color: #AAA;")
        form.addRow("Caminho do projeto:", self.lbl_project_path)

        self.ed_name = QLineEdit()
        self.ed_name.setPlaceholderText("Nome do projeto (exibição)")
        form.addRow("Nome:", self.ed_name)

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

        # Entrada sempre automática (detectada por arquivo)
        self.lbl_input_encoding = QLabel("Automático (sempre igual ao arquivo original)")
        self.lbl_input_encoding.setStyleSheet("color: #888;")
        self.lbl_input_encoding.setWordWrap(True)
        form.addRow("Encoding (entrada):", self.lbl_input_encoding)

        # Saída explícita (encoding + BOM)
        self.cmb_export_encoding = QComboBox()
        for label, (enc, bom) in EXPORT_ENCODINGS:
            self.cmb_export_encoding.addItem(label, [enc, bom])  # ✅ salva como list (mais estável no Qt)
        form.addRow("Encoding (saída):", self.cmb_export_encoding)

        self.cmb_engine = QComboBox()
        engines = [
            ("", "—"),
            ("kirikiri", "KiriKiri / KAG"),
            ("renpy", "Ren'Py"),
            ("unity", "Unity"),
            ("custom", "Custom"),
        ]
        for key, label in engines:
            self.cmb_engine.addItem(label, key)
        self.cmb_engine.setEditable(True)
        self.cmb_engine.setInsertPolicy(QComboBox.NoInsert)
        form.addRow("Engine:", self.cmb_engine)

        outer.addWidget(box_info)

        box_lang = QGroupBox("Idiomas")
        form2 = QFormLayout(box_lang)
        form2.setLabelAlignment(Qt.AlignLeft)
        form2.setFormAlignment(Qt.AlignTop)
        form2.setHorizontalSpacing(12)
        form2.setVerticalSpacing(8)

        self.cmb_source_lang = QComboBox()
        self.cmb_target_lang = QComboBox()

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

    def _browse_root(self):
        start = self.ed_root_path.text().strip()
        if not start or not os.path.isdir(start):
            start = os.path.expanduser("~")

        path = QFileDialog.getExistingDirectory(self, "Selecionar pasta do jogo", start)
        if path:
            self.ed_root_path.setText(path)

    def load_project(self, project: dict) -> None:
        project = project or {}

        self.lbl_project_path.setText((project.get("project_path") or "—").strip() or "—")
        self.ed_name.setText((project.get("name") or "").strip())
        self.ed_root_path.setText((project.get("root_path") or "").strip())

        enc_hint = (project.get("encoding") or "auto").strip() or "auto"
        if enc_hint.lower() != "auto":
            self.lbl_input_encoding.setText(f"Automático (hint atual: {enc_hint})")
        else:
            self.lbl_input_encoding.setText("Automático (sempre igual ao arquivo original)")

        exp_enc = (project.get("export_encoding") or "utf-8").strip() or "utf-8"
        exp_bom = bool(project.get("export_bom", False))
        exp_enc, exp_bom = _canonicalize_export(exp_enc, exp_bom)

        # match exato (encoding + bom)
        idx = -1
        for i in range(self.cmb_export_encoding.count()):
            pair = _as_pair(self.cmb_export_encoding.itemData(i))
            if not pair:
                continue
            enc_i, bom_i = pair
            if enc_i.lower() == exp_enc.lower() and bool(bom_i) == bool(exp_bom):
                idx = i
                break

        if idx >= 0:
            self.cmb_export_encoding.setCurrentIndex(idx)
        else:
            # fallback: match só pelo encoding
            fallback = -1
            for i in range(self.cmb_export_encoding.count()):
                pair = _as_pair(self.cmb_export_encoding.itemData(i))
                if not pair:
                    continue
                enc_i, _bom_i = pair
                if enc_i.lower() == exp_enc.lower():
                    fallback = i
                    break
            self.cmb_export_encoding.setCurrentIndex(fallback if fallback >= 0 else 0)

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

        # Entrada sempre "auto"
        encoding = "auto"

        # Saída: par (encoding, bom)
        export_encoding = ""
        export_bom = False

        pair = _as_pair(self.cmb_export_encoding.currentData())
        if pair:
            export_encoding, export_bom = pair
        else:
            export_encoding = str(self.cmb_export_encoding.currentText() or "").strip()
            export_bom = False

        export_encoding, export_bom = _canonicalize_export(export_encoding, export_bom)

        # Engine precisa salvar o ID (data), não o texto do combo
        engine = (self.cmb_engine.currentData() or self.cmb_engine.currentText() or "").strip()

        source_language = (self.cmb_source_lang.currentText() or "").strip()
        target_language = (self.cmb_target_lang.currentText() or "").strip()

        if not name:
            raise ValueError("Nome do projeto não pode ficar vazio.")

        if not root_path:
            raise ValueError("Root do jogo não pode ficar vazio.")
        if not os.path.isdir(root_path):
            raise ValueError("Root do jogo inválido (a pasta não existe).")

        if not export_encoding:
            raise ValueError("Encoding (saída) não pode ficar vazio.")

        project["name"] = name
        project["root_path"] = root_path

        # Entrada bloqueada
        project["encoding"] = encoding

        # Saída explícita
        project["export_encoding"] = export_encoding
        project["export_bom"] = export_bom

        project["engine"] = engine
        project["source_language"] = source_language
        project["target_language"] = target_language