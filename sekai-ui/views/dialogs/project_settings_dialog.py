from __future__ import annotations

import copy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTabWidget,
    QWidget,
    QLabel,
    QMessageBox,
    QGroupBox,
    QFormLayout,
    QComboBox,
    QPlainTextEdit,
)

from views.dialogs.project_settings_tab import ProjectSettingsTab
from parsers.manager import get_parser_manager


class ProjectSettingsDialog(QDialog):
    """
    Dialog container das configurações do projeto.

    Tabs:
      - Projeto
      - IA
      - Engine

    Salva em uma cópia do dicionário do projeto e chama callback opcional.
    """

    PRESET_LABELS = {
        "default": "Padrão",
        "literal": "Literal (mais fiel)",
        "natural": "Natural (pt-BR fluido)",
        "custom": "Personalizado (texto livre)",
    }

    def __init__(self, parent=None, *, project: dict | None = None, on_save=None):
        super().__init__(parent)

        # sempre trabalha com cópia interna para não corromper o dict do caller
        self._project: dict = copy.deepcopy(project) if isinstance(project, dict) else {}
        self._on_save = on_save

        self.setWindowTitle("Configurações do Projeto")
        self.resize(600, 520)
        self.setModal(True)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.project_tab = ProjectSettingsTab(self)
        self.tabs.addTab(self.project_tab, "Projeto")

        self.ai_tab = self._build_ai_tab()
        self.tabs.addTab(self.ai_tab, "IA")

        self.engine_tab = self._build_engine_tab()
        self.tabs.addTab(self.engine_tab, "Engine")

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_save = QPushButton("Salvar")

        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)

        main_layout.addLayout(btn_layout)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save.clicked.connect(self._save)

        self._load_from_project()

    # -----------------------
    # Engine tab
    # -----------------------
    def _build_engine_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        box = QGroupBox("Engine do projeto")
        form = QFormLayout(box)
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        self.cmb_engine = QComboBox()
        self.cmb_profile = QComboBox()
        self.cmb_profile.setEnabled(False)

        form.addRow("Engine:", self.cmb_engine)
        form.addRow("Perfis:", self.cmb_profile)

        hint = QLabel(
            "A engine define o formato do script (ex.: KiriKiri .ks).\n"
            "Perfis organizam variações por jogo (ex.: yandere)."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888;")
        form.addRow("", hint)

        outer.addWidget(box)
        outer.addStretch()

        self.cmb_engine.currentIndexChanged.connect(self._refresh_profiles)

        self._reload_engine_lists()
        return w

    def _reload_engine_lists(self) -> None:
        self.cmb_engine.clear()
        self.cmb_profile.clear()

        mgr = get_parser_manager()
        plugins = mgr.all_plugins() if mgr else []

        ids: set[str] = set()
        meta_by_id: dict[str, tuple[str, set[str]]] = {}
        for p in plugins:
            pid = (getattr(p, "plugin_id", "") or "").strip()
            if not pid:
                continue
            name = (getattr(p, "name", "") or "").strip() or pid
            exts = set(str(e).lower() for e in (getattr(p, "extensions", None) or set()) if str(e).strip())
            ids.add(pid)
            meta_by_id[pid] = (name, exts)

        self._engine_ids = ids
        base_to_profiles: dict[str, list[str]] = {}
        for eid in sorted(ids):
            if "." in eid:
                candidate = eid.rsplit(".", 1)[0]
                if candidate in ids:
                    prof = eid[len(candidate) + 1 :]
                    base_to_profiles.setdefault(candidate, []).append(prof)
                    continue
            base_to_profiles.setdefault(eid, [])

        self._base_to_profiles = {k: sorted(set(v)) for k, v in base_to_profiles.items()}

        self.cmb_engine.addItem("Auto-detect (recomendado)", "")

        items: list[tuple[str, str]] = []
        for base_id in base_to_profiles.keys():
            name, exts = meta_by_id.get(base_id, (base_id, set()))
            label = name
            if exts:
                label = f"{label}  ({', '.join(sorted(exts))})"
            items.append((label, base_id))

        items.sort(key=lambda t: t[0].lower())
        for label, base_id in items:
            self.cmb_engine.addItem(label, base_id)

        self._refresh_profiles()

    def _refresh_profiles(self) -> None:
        base_id = str(self.cmb_engine.currentData() or "").strip()
        self.cmb_profile.blockSignals(True)
        try:
            self.cmb_profile.clear()
            if not base_id:
                self.cmb_profile.addItem("(Auto)", "")
                self.cmb_profile.setEnabled(False)
                return

            profiles = list((getattr(self, "_base_to_profiles", {}) or {}).get(base_id, []) or [])
            if not profiles:
                self.cmb_profile.addItem("(Sem perfis)", "")
                self.cmb_profile.setEnabled(False)
                return

            self.cmb_profile.addItem("Padrão", "")
            for p in profiles:
                self.cmb_profile.addItem(str(p), str(p))
            self.cmb_profile.setEnabled(True)
        finally:
            self.cmb_profile.blockSignals(False)

    # -----------------------
    # AI tab
    # -----------------------
    def _build_ai_tab(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        box = QGroupBox("Tradução com IA")
        form = QFormLayout(box)
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        self.cmb_prompt_preset = QComboBox()
        self.cmb_prompt_preset.addItem(self.PRESET_LABELS["default"], "default")
        self.cmb_prompt_preset.addItem(self.PRESET_LABELS["literal"], "literal")
        self.cmb_prompt_preset.addItem(self.PRESET_LABELS["natural"], "natural")
        self.cmb_prompt_preset.addItem(self.PRESET_LABELS["custom"], "custom")
        form.addRow("Prompt do projeto:", self.cmb_prompt_preset)

        self.txt_custom_prompt = QPlainTextEdit()
        self.txt_custom_prompt.setPlaceholderText(
            "Escreva aqui o prompt personalizado.\n"
            "Ex.: regras de estilo, termos, tom, etc."
        )
        self.txt_custom_prompt.setMinimumHeight(140)
        form.addRow("Prompt personalizado:", self.txt_custom_prompt)

        hint = QLabel(
            "Dica: se o preset for \"Personalizado\", o texto acima será enviado no request como custom_prompt_text."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888;")
        form.addRow("", hint)

        outer.addWidget(box)
        outer.addStretch()

        self.cmb_prompt_preset.currentIndexChanged.connect(self._refresh_ai_ui)
        return w

    def _refresh_ai_ui(self) -> None:
        preset = self.cmb_prompt_preset.currentData()
        is_custom = (preset == "custom")
        self.txt_custom_prompt.setEnabled(is_custom)
        self.txt_custom_prompt.setVisible(is_custom)

    # -----------------------
    # Load / collect
    # -----------------------
    def _load_from_project(self) -> None:
        # Projeto tab
        self.project_tab.load_project(self._project)

        # Engine/Profile (derivados de parser_id)
        pid = (self._project.get("parser_id") or "").strip()
        if not pid:
            self.cmb_engine.setCurrentIndex(max(0, self.cmb_engine.findData("")))
            self._refresh_profiles()
        else:
            ids = getattr(self, "_engine_ids", set()) or set()
            base = pid
            prof = ""

            if pid not in ids and "." in pid:
                cand = pid.rsplit(".", 1)[0]
                if cand in ids:
                    base = cand
                    prof = pid[len(cand) + 1 :]
            else:
                if "." in pid:
                    cand = pid.rsplit(".", 1)[0]
                    if cand in ids and pid != cand:
                        base = cand
                        prof = pid[len(cand) + 1 :]

            idx = self.cmb_engine.findData(base)
            if idx < 0:
                idx = self.cmb_engine.findData("")
            self.cmb_engine.setCurrentIndex(max(0, idx))
            self._refresh_profiles()

            pidx = self.cmb_profile.findData(prof)
            if pidx < 0:
                pidx = self.cmb_profile.findData("")
            self.cmb_profile.setCurrentIndex(max(0, pidx))

        preset = (self._project.get("ai_prompt_preset") or "default").strip() or "default"
        custom = (self._project.get("ai_custom_prompt_text") or "").strip()

        idx = self.cmb_prompt_preset.findData(preset)
        if idx < 0:
            idx = self.cmb_prompt_preset.findData("default")
        self.cmb_prompt_preset.setCurrentIndex(max(0, idx))
        self.txt_custom_prompt.setPlainText(custom)

        self._refresh_ai_ui()

    def _collect_updated_project(self) -> dict:
        """
        Coleta valores das tabs e devolve um dict NOVO pronto para salvar.
        Não modifica o dict do caller.
        """
        updated = copy.deepcopy(self._project)

        # Projeto tab (valida e escreve no dict)
        self.project_tab.apply_to_project(updated)

        # parser_id (engine/profile)
        base = str(self.cmb_engine.currentData() or "").strip()
        prof = str(self.cmb_profile.currentData() or "").strip()
        updated["parser_id"] = "" if not base else (f"{base}.{prof}" if prof else base)

        # IA
        preset = str(self.cmb_prompt_preset.currentData() or "default").strip() or "default"
        custom = self.txt_custom_prompt.toPlainText().strip()
        updated["ai_prompt_preset"] = preset
        updated["ai_custom_prompt_text"] = custom if preset == "custom" else ""

        # garante que project_path nunca some
        if not updated.get("project_path") and self._project.get("project_path"):
            updated["project_path"] = self._project.get("project_path")

        return updated

    def _save(self) -> None:
        """
        Coleta + salva via callback.
        """
        try:
            updated = self._collect_updated_project()

            if not callable(self._on_save):
                raise RuntimeError("Callback on_save não definido.")

            # Salva e recebe o projeto REAL persistido (dict final)
            saved = self._on_save(updated)
            if not isinstance(saved, dict):
                saved = updated

            # Atualiza o estado interno do dialog
            self._project = copy.deepcopy(saved)

            # Recarrega as tabs (garante que o combo reflita export_encoding/export_bom)
            self._load_from_project()

            QMessageBox.information(self, "Configurações do Projeto", "Configurações salvas.")
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))