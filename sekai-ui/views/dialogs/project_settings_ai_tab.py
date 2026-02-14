from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QComboBox,
    QTextEdit,
    QLabel,
)


class ProjectSettingsAITab(QWidget):
    """
    Aba IA das configurações do projeto.
    Guarda:
      - ai_prompt_key (ex: "default", "literal", "natural", etc.)
      - custom_prompt_text (texto do prompt alternativo)
      - user_prompt (prompt complementar do usuário)
    """

    # Por enquanto, lista local (você troca depois pra carregar do repo/schema.json)
    PROMPT_PRESETS: dict[str, str] = {
        "default": "",  # usa só o SYSTEM_PROMPT_BASE do servidor
        "natural": "Traduza de forma natural e fluida, mantendo sentido e emoção.",
        "literal": "Traduza de forma mais literal possível, preservando estrutura e termos.",
        "formal": "Traduza com tom mais formal, sem gírias, mantendo clareza.",
    }

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        hint = QLabel(
            "Selecione um prompt alternativo para definir o estilo.\n"
            "Você também pode complementar com regras adicionais (opcional)."
        )
        hint.setStyleSheet("color: #888;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        form = QFormLayout()
        layout.addLayout(form)

        self.combo_prompt = QComboBox()
        for key in self.PROMPT_PRESETS.keys():
            self.combo_prompt.addItem(key, userData=key)
        form.addRow("Prompt (preset):", self.combo_prompt)

        self.txt_custom_prompt = QTextEdit()
        self.txt_custom_prompt.setPlaceholderText(
            "Prompt alternativo (custom_prompt_text). "
            "Se vazio, o preset selecionado será usado."
        )
        self.txt_custom_prompt.setMinimumHeight(90)
        form.addRow("Prompt alternativo:", self.txt_custom_prompt)

        self.txt_user_prompt = QTextEdit()
        self.txt_user_prompt.setPlaceholderText(
            "Regras adicionais (user_prompt). Opcional (máx 500 chars no PHP)."
        )
        self.txt_user_prompt.setMinimumHeight(90)
        form.addRow("Prompt complementar:", self.txt_user_prompt)

        layout.addStretch()

    def load_project(self, project: dict) -> None:
        key = (project.get("ai_prompt_key") or "default").strip() or "default"
        idx = self.combo_prompt.findData(key)
        if idx >= 0:
            self.combo_prompt.setCurrentIndex(idx)
        else:
            self.combo_prompt.setCurrentIndex(0)

        self.txt_custom_prompt.setPlainText(project.get("custom_prompt_text") or "")
        self.txt_user_prompt.setPlainText(project.get("user_prompt") or "")

    def collect_settings(self) -> dict:
        key = str(self.combo_prompt.currentData() or "default")
        custom = self.txt_custom_prompt.toPlainText().strip()
        userp = self.txt_user_prompt.toPlainText().strip()

        # Se custom estiver vazio, usamos o texto do preset (exceto default)
        if not custom:
            custom = self.PROMPT_PRESETS.get(key, "") or ""

        return {
            "ai_prompt_key": key,
            "custom_prompt_text": custom,
            "user_prompt": userp,
        }
