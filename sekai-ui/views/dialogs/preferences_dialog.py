from __future__ import annotations

from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QCheckBox,
    QPushButton,
    QGroupBox,
    QMessageBox,
    QLineEdit,
    QFileDialog,
    QSlider,
    QTabWidget,
    QWidget,
)

from themes.theme_manager import ThemeManager
from views.widgets.theme_editor_widget import ThemeEditorWidget


class PreferencesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Preferências")
        self.resize(980, 760)
        self.setMinimumSize(900, 680)

        self._initial_theme_name = ThemeManager.load_saved_theme_name()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        appearance_tab = QWidget()
        appearance_tab_layout = QVBoxLayout(appearance_tab)
        appearance_tab_layout.setSpacing(12)

        appearance_box = QGroupBox("Aparência")
        appearance_layout = QVBoxLayout(appearance_box)
        appearance_layout.setSpacing(8)

        appearance_layout.addWidget(QLabel("Tema da interface"))
        self.theme_box = QComboBox()
        self.theme_box.addItems(ThemeManager.display_names())
        appearance_layout.addWidget(self.theme_box)

        self.chk_custom_colors = QCheckBox("Usar cores personalizadas")
        appearance_layout.addWidget(self.chk_custom_colors)

        self.chk_background_enabled = QCheckBox("Usar plano de fundo")
        appearance_layout.addWidget(self.chk_background_enabled)

        bg_path_row = QHBoxLayout()
        self.background_path_edit = QLineEdit()
        self.background_path_edit.setPlaceholderText("Opcional: escolha uma imagem personalizada")
        self.btn_browse_background = QPushButton("Procurar...")
        self.btn_clear_background = QPushButton("Limpar")
        bg_path_row.addWidget(self.background_path_edit, 1)
        bg_path_row.addWidget(self.btn_browse_background)
        bg_path_row.addWidget(self.btn_clear_background)
        appearance_layout.addLayout(bg_path_row)

        appearance_layout.addWidget(QLabel("Intensidade do overlay escuro"))
        overlay_row = QHBoxLayout()
        self.overlay_slider = QSlider(Qt.Horizontal)
        self.overlay_slider.setRange(0, 220)
        self.overlay_slider.setValue(140)
        self.overlay_value_label = QLabel("140")
        self.overlay_value_label.setMinimumWidth(36)
        overlay_row.addWidget(self.overlay_slider, 1)
        overlay_row.addWidget(self.overlay_value_label)
        appearance_layout.addLayout(overlay_row)

        bg_hint = QLabel(
            "Quando ativado, o SekaiTranslator usa a imagem escolhida ou um fundo interno padrão, "
            "sempre com um overlay por cima para manter a leitura confortável."
        )
        bg_hint.setProperty("mutedText", True)
        bg_hint.setWordWrap(True)
        appearance_layout.addWidget(bg_hint)

        appearance_tab_layout.addWidget(appearance_box)
        appearance_tab_layout.addStretch()
        self.tabs.addTab(appearance_tab, "Geral")

        themes_tab = QWidget()
        themes_tab_layout = QVBoxLayout(themes_tab)
        themes_tab_layout.setContentsMargins(0, 0, 0, 0)
        self.theme_editor = ThemeEditorWidget(self)
        themes_tab_layout.addWidget(self.theme_editor, 1)
        self.tabs.addTab(themes_tab, "Temas")

        behavior_tab = QWidget()
        behavior_tab_layout = QVBoxLayout(behavior_tab)

        behavior_box = QGroupBox("Comportamento")
        behavior_layout = QVBoxLayout(behavior_box)
        behavior_layout.setSpacing(6)

        self.chk_autosave = QCheckBox("Salvar automaticamente projetos")
        self.chk_confirm_exit = QCheckBox("Confirmar ao sair com alterações não salvas")
        behavior_layout.addWidget(self.chk_autosave)
        behavior_layout.addWidget(self.chk_confirm_exit)

        behavior_tab_layout.addWidget(behavior_box)
        behavior_tab_layout.addStretch()
        self.tabs.addTab(behavior_tab, "Comportamento")

        server_tab = QWidget()
        server_tab_layout = QVBoxLayout(server_tab)

        server_box = QGroupBox("Servidor (Conta / IA)")
        server_layout = QVBoxLayout(server_box)
        server_layout.setSpacing(8)

        server_layout.addWidget(QLabel("URL do Auth (auth.php)"))
        self.auth_url_edit = QLineEdit()
        self.auth_url_edit.setPlaceholderText(
            "https://green-gaur-846876.hostingersite.com/api/auth.php"
        )
        server_layout.addWidget(self.auth_url_edit)

        server_layout.addWidget(QLabel("URL do Proxy IA (proxy.php)"))
        self.proxy_url_edit = QLineEdit()
        self.proxy_url_edit.setPlaceholderText(
            "https://green-gaur-846876.hostingersite.com/api/proxy.php"
        )
        server_layout.addWidget(self.proxy_url_edit)

        token_row = QHBoxLayout()
        self.btn_clear_token = QPushButton("Limpar token de login")
        self.btn_clear_token.clicked.connect(self._clear_token)
        token_row.addWidget(self.btn_clear_token)
        token_row.addStretch()
        server_layout.addLayout(token_row)

        hint = QLabel(
            "Dica: você também pode sobrescrever por variáveis de ambiente:\n"
            "- SEKAI_AUTH_URL\n"
            "- SEKAI_PROXY_URL"
        )
        hint.setProperty("mutedText", True)
        hint.setWordWrap(True)
        server_layout.addWidget(hint)

        server_tab_layout.addWidget(server_box)
        server_tab_layout.addStretch()
        self.tabs.addTab(server_tab, "Servidor")

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_apply = QPushButton("Aplicar")
        self.btn_ok = QPushButton("OK")

        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_apply)
        btn_layout.addWidget(self.btn_ok)
        layout.addLayout(btn_layout)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_apply.clicked.connect(self._apply)
        self.btn_ok.clicked.connect(self._ok)
        self.btn_browse_background.clicked.connect(self._browse_background)
        self.btn_clear_background.clicked.connect(lambda: self.background_path_edit.setText(""))
        self.overlay_slider.valueChanged.connect(self._update_overlay_label)
        self.chk_background_enabled.toggled.connect(self._update_background_controls)

        self._load()

    def _load(self) -> None:
        s = QSettings("SekaiTranslatorV", "SekaiTranslatorV")

        self.theme_box.clear()
        self.theme_box.addItems(ThemeManager.display_names())

        theme = ThemeManager.normalize_theme_name(
            s.value("ui/theme", ThemeManager.DEFAULT_THEME_NAME)
        )
        idx = self.theme_box.findText(theme)
        if idx >= 0:
            self.theme_box.setCurrentIndex(idx)

        self.theme_editor.reload(theme)

        self.chk_custom_colors.setChecked(str(s.value("ui/use_custom_colors", "false")).lower() == "true")
        self.chk_background_enabled.setChecked(str(s.value("ui/background_enabled", "true")).lower() == "true")
        self.background_path_edit.setText(str(s.value("ui/background_path", "") or ""))
        self.overlay_slider.setValue(int(s.value("ui/background_overlay", 140) or 140))
        self._update_overlay_label(self.overlay_slider.value())
        self._update_background_controls(self.chk_background_enabled.isChecked())

        self.chk_autosave.setChecked(str(s.value("project/autosave", "true")).lower() == "true")
        self.chk_confirm_exit.setChecked(str(s.value("ui/confirm_exit", "true")).lower() == "true")

        self.auth_url_edit.setText(str(s.value("network/auth_url", "") or ""))
        self.proxy_url_edit.setText(str(s.value("network/proxy_url", "") or ""))

    def _apply(self) -> None:
        s = QSettings("SekaiTranslatorV", "SekaiTranslatorV")

        selected_theme = ThemeManager.normalize_theme_name(self.theme_editor.apply_to_settings())

        self.theme_box.clear()
        self.theme_box.addItems(ThemeManager.display_names())
        idx = self.theme_box.findText(selected_theme)
        if idx >= 0:
            self.theme_box.setCurrentIndex(idx)

        s.setValue("ui/theme", selected_theme)
        s.setValue("ui/use_custom_colors", self.chk_custom_colors.isChecked())
        s.setValue("ui/background_enabled", self.chk_background_enabled.isChecked())
        s.setValue("ui/background_path", self.background_path_edit.text().strip())
        s.setValue("ui/background_overlay", int(self.overlay_slider.value()))
        s.setValue("project/autosave", self.chk_autosave.isChecked())
        s.setValue("ui/confirm_exit", self.chk_confirm_exit.isChecked())
        s.setValue("network/auth_url", self.auth_url_edit.text().strip())
        s.setValue("network/proxy_url", self.proxy_url_edit.text().strip())

        parent = self.parent()
        if parent is not None and hasattr(parent, "_apply_saved_theme"):
            try:
                parent._apply_saved_theme()
            except Exception as exc:
                QMessageBox.warning(self, "Preferências", f"Falha ao aplicar tema:\n{exc}")

    def _ok(self) -> None:
        self._apply()
        self.accept()

    def reject(self) -> None:
        try:
            parent = self.parent()
            ThemeManager.save_theme_name(self._initial_theme_name)
            if parent is not None and hasattr(parent, "_apply_saved_theme"):
                parent._apply_saved_theme()
        except Exception:
            pass
        super().reject()

    def _browse_background(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Escolher imagem de fundo",
            "",
            "Imagens (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if path:
            self.background_path_edit.setText(path)

    def _update_overlay_label(self, value: int) -> None:
        self.overlay_value_label.setText(str(int(value)))

    def _update_background_controls(self, enabled: bool) -> None:
        self.background_path_edit.setEnabled(enabled)
        self.btn_browse_background.setEnabled(enabled)
        self.btn_clear_background.setEnabled(enabled)
        self.overlay_slider.setEnabled(enabled)

    def _clear_token(self) -> None:
        s = QSettings("SekaiTranslatorV", "SekaiTranslatorV")
        s.remove("auth/token")
        QMessageBox.information(self, "Servidor", "Token removido com sucesso.")