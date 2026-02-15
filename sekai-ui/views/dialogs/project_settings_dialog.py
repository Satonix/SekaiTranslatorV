
from __future__ import annotations

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

    Salva no dicionário do projeto (self.project) e chama callback opcional.
    """

    PRESET_LABELS = {
        "default": "Padrão",
        "literal": "Literal (mais fiel)",
        "natural": "Natural (pt-BR fluido)",
        "custom": "Personalizado (texto livre)",
    }

    def __init__(self, parent=None, *, project: dict | None = None, on_save=None):
        super().__init__(parent)

        self.project = project if isinstance(project, dict) else {}
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

        self._inject_parser_picker(self.project_tab)

        self.ai_tab = self._build_ai_tab()
        self.tabs.addTab(self.ai_tab, "IA")

        self.tabs.addTab(
            self._placeholder_tab(
                "Configurações específicas da engine do jogo.\n\n"
                "Parsers, flags e opções avançadas."
            ),
            "Engine",
        )

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

    def _inject_parser_picker(self, tab: QWidget) -> None:
        """
        Adiciona um seletor de parser_id na aba Projeto.
        Salva em project["parser_id"].
        """
        layout = tab.layout()
        if layout is None:
            layout = QVBoxLayout(tab)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(10)

        box = QGroupBox("Parser do projeto")
        form = QFormLayout(box)
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        self.cmb_parser_id = QComboBox()
        self.cmb_parser_id.setToolTip(
            "Define qual parser será usado por padrão neste projeto.\n"
            "Se estiver em Auto, o app tentará detectar o melhor parser para cada arquivo."
        )

        self.cmb_parser_id.addItem("Auto-detect (recomendado)", "")

        mgr = get_parser_manager()
        plugins = []
        for p in mgr.all_plugins():
            pid = (getattr(p, "plugin_id", "") or "").strip()
            name = (getattr(p, "name", "") or "").strip()
            if pid:
                plugins.append((pid, name or pid))

        plugins.sort(key=lambda x: x[1].lower())

        for pid, name in plugins:
            self.cmb_parser_id.addItem(f"{name}  ({pid})", pid)

        form.addRow("Parser:", self.cmb_parser_id)

        hint = QLabel(
            "Se você instalar/atualizar parsers via Plugins → Parsers, eles aparecem aqui.\n"
            "O valor é salvo no projeto como parser_id."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888;")
        form.addRow("", hint)

        layout.addWidget(box)

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

    def _placeholder_tab(self, text: str) -> QWidget:
        w = QWidget()
        l = QVBoxLayout(w)
        l.setContentsMargins(12, 12, 12, 12)
        l.setSpacing(8)

        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet("color: #888;")

        l.addWidget(label)
        l.addStretch()
        return w

    def _load_from_project(self) -> None:
        if hasattr(self, "project_tab"):
            self.project_tab.load_project(self.project)

        if hasattr(self, "cmb_parser_id"):
            pid = (self.project.get("parser_id") or "").strip()
            idx = self.cmb_parser_id.findData(pid)
            if idx < 0:
                idx = self.cmb_parser_id.findData("")
            self.cmb_parser_id.setCurrentIndex(max(0, idx))

        preset = (self.project.get("ai_prompt_preset") or "default").strip() or "default"
        custom = (self.project.get("ai_custom_prompt_text") or "").strip()

        idx = self.cmb_prompt_preset.findData(preset)
        if idx < 0:
            idx = self.cmb_prompt_preset.findData("default")
        self.cmb_prompt_preset.setCurrentIndex(max(0, idx))
        self.txt_custom_prompt.setPlainText(custom)

        self._refresh_ai_ui()

    def _refresh_ai_ui(self) -> None:
        preset = self.cmb_prompt_preset.currentData()
        is_custom = (preset == "custom")
        self.txt_custom_prompt.setEnabled(is_custom)
        self.txt_custom_prompt.setVisible(is_custom)

    def _collect_to_project(self) -> None:
        if hasattr(self, "project_tab"):
            self.project_tab.apply_to_project(self.project)

        if hasattr(self, "cmb_parser_id"):
            pid = str(self.cmb_parser_id.currentData() or "").strip()
            self.project["parser_id"] = pid

        preset = str(self.cmb_prompt_preset.currentData() or "default").strip() or "default"
        custom = self.txt_custom_prompt.toPlainText().strip()

        self.project["ai_prompt_preset"] = preset
        self.project["ai_custom_prompt_text"] = custom if preset == "custom" else ""

    def _save(self):
        """
        Salva no dict do projeto e chama callback opcional.
        """
        try:
            self._collect_to_project()

            if callable(self._on_save):
                self._on_save(self.project)

            QMessageBox.information(
                self,
                "Configurações do Projeto",
                "Configurações salvas.",
            )
            self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
