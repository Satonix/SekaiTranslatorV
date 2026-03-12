from __future__ import annotations

import os

from PySide6.QtCore import QSettings, Qt

from themes.theme_manager import ThemeManager
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

from views.widgets.theme_editor_widget import ThemeEditorWidget


class PreferencesDialog(QDialog):
    """
    Preferências do app.

    Agora com backend mínimo via QSettings para:
    - URLs do servidor (auth/proxy)
    - Preferências simples (tema/autosave/confirmar ao sair)
    - Ações utilitárias: limpar token de login
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Preferências")
        self.resize(980, 760)
        self.setMinimumSize(920, 700)
        self.setModal(True)


        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)

        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)
        general_layout.setContentsMargins(0, 0, 0, 0)
        general_layout.setSpacing(12)

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
        self.overlay_slider = QSlider()
        self.overlay_slider.setOrientation(Qt.Horizontal)
        self.overlay_slider.setRange(0, 220)
        self.overlay_slider.setValue(140)
        self.overlay_value_label = QLabel("140")
        self.overlay_value_label.setMinimumWidth(36)
        overlay_row.addWidget(self.overlay_slider, 1)
        overlay_row.addWidget(self.overlay_value_label)
        appearance_layout.addLayout(overlay_row)
        bg_hint = QLabel(
            "Quando ativado, o SekaiTranslator usa a imagem escolhida ou um fundo interno padrão, "
            "sempre com um overlay escuro por cima para manter a leitura confortável."
        )
        bg_hint.setProperty("mutedText", True)
        bg_hint.setWordWrap(True)
        appearance_layout.addWidget(bg_hint)
        general_layout.addWidget(appearance_box)
        general_layout.addStretch(1)
        self.tabs.addTab(general_tab, "Geral")

        themes_tab = QWidget()
        themes_layout = QVBoxLayout(themes_tab)
        themes_layout.setContentsMargins(0, 0, 0, 0)
        self.theme_editor = ThemeEditorWidget(self)
        themes_layout.addWidget(self.theme_editor, 1)
        self.tabs.addTab(themes_tab, "Temas")

        behavior_tab = QWidget()
        behavior_host = QVBoxLayout(behavior_tab)
        behavior_box = QGroupBox("Comportamento")
        behavior_layout = QVBoxLayout(behavior_box)
        behavior_layout.setSpacing(6)
        self.chk_autosave = QCheckBox("Salvar automaticamente projetos")
        self.chk_confirm_exit = QCheckBox("Confirmar ao sair com alterações não salvas")
        behavior_layout.addWidget(self.chk_autosave)
        behavior_layout.addWidget(self.chk_confirm_exit)
        behavior_host.addWidget(behavior_box)
        behavior_host.addStretch(1)
        self.tabs.addTab(behavior_tab, "Comportamento")

        server_tab = QWidget()
        server_host = QVBoxLayout(server_tab)
        server_box = QGroupBox("Servidor (Conta / IA)")
        server_layout = QVBoxLayout(server_box)
        server_layout.setSpacing(8)
        server_layout.addWidget(QLabel("URL do Auth (auth.php)"))
        self.auth_url_edit = QLineEdit()
        self.auth_url_edit.setPlaceholderText("https://green-gaur-846876.hostingersite.com/api/auth.php")
        server_layout.addWidget(self.auth_url_edit)
        server_layout.addWidget(QLabel("URL do Proxy IA (proxy.php)"))
        self.proxy_url_edit = QLineEdit()
        self.proxy_url_edit.setPlaceholderText("https://green-gaur-846876.hostingersite.com/api/proxy.php")
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
        server_host.addWidget(server_box)
        server_host.addStretch(1)
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
        self.btn_ok.clicked.connect(self._ok)
        self.btn_apply.clicked.connect(self._apply)
        self.btn_browse_background.clicked.connect(self._browse_background)
        self.btn_clear_background.clicked.connect(lambda: self.background_path_edit.setText(""))
        self.overlay_slider.valueChanged.connect(self._update_overlay_label)
        self.chk_background_enabled.toggled.connect(self._update_background_controls)
        self._load()

    def _settings(self) -> QSettings:
        return QSettings("SekaiTranslatorV", "SekaiTranslatorV")

    def _default_auth_url(self) -> str:
        env = (os.environ.get("SEKAI_AUTH_URL") or "").strip()
        if env:
            return env
        return "https://green-gaur-846876.hostingersite.com/api/auth.php"

    def _default_proxy_url(self) -> str:
        env = (os.environ.get("SEKAI_PROXY_URL") or "").strip()
        if env:
            return env
        return "https://green-gaur-846876.hostingersite.com/api/proxy.php"

    def _load(self) -> None:
        s = self._settings()

        theme = ThemeManager.normalize_theme_name(s.value("ui/theme", ThemeManager.DEFAULT_THEME_NAME))
        self.theme_box.clear()
        self.theme_box.addItems(ThemeManager.display_names())
        idx = self.theme_box.findText(theme)
        if idx >= 0:
            self.theme_box.setCurrentIndex(idx)
        self.theme_editor.reload(theme)

        self.chk_custom_colors.setChecked(bool(s.value("ui/custom_colors", False, type=bool)))
        self.chk_background_enabled.setChecked(bool(s.value("ui/background_enabled", False, type=bool)))
        self.background_path_edit.setText((s.value("ui/background_path", "", type=str) or "").strip())
        self.overlay_slider.setValue(int(s.value("ui/background_overlay", 140) or 140))
        self._update_overlay_label()
        self._update_background_controls()
        self.chk_autosave.setChecked(bool(s.value("behavior/autosave", False, type=bool)))
        self.chk_confirm_exit.setChecked(bool(s.value("behavior/confirm_exit", True, type=bool)))

        auth_url = (s.value("auth/auth_url", "") or "").strip()
        proxy_url = (s.value("auth/proxy_url", "") or "").strip()

        self.auth_url_edit.setText(auth_url or self._default_auth_url())
        self.proxy_url_edit.setText(proxy_url or self._default_proxy_url())

    def _save(self) -> None:
        s = self._settings()

        selected_theme = ThemeManager.normalize_theme_name(self.theme_editor.apply_to_settings())
        self.theme_box.clear()
        self.theme_box.addItems(ThemeManager.display_names())
        idx = self.theme_box.findText(selected_theme)
        if idx >= 0:
            self.theme_box.setCurrentIndex(idx)
        s.setValue("ui/theme", selected_theme)
        s.setValue("ui/custom_colors", self.chk_custom_colors.isChecked())
        s.setValue("ui/background_enabled", self.chk_background_enabled.isChecked())
        s.setValue("ui/background_path", self.background_path_edit.text().strip())
        s.setValue("ui/background_overlay", int(self.overlay_slider.value()))

        s.setValue("behavior/autosave", self.chk_autosave.isChecked())
        s.setValue("behavior/confirm_exit", self.chk_confirm_exit.isChecked())

        s.setValue("auth/auth_url", self.auth_url_edit.text().strip())
        s.setValue("auth/proxy_url", self.proxy_url_edit.text().strip())


    def _browse_background(self) -> None:
        current = self.background_path_edit.text().strip()
        start_dir = current or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Escolher plano de fundo",
            start_dir,
            "Imagens (*.png *.jpg *.jpeg *.bmp *.webp)",
        )
        if path:
            self.background_path_edit.setText(path)
            self.chk_background_enabled.setChecked(True)

    def _update_overlay_label(self) -> None:
        try:
            self.overlay_value_label.setText(str(int(self.overlay_slider.value())))
        except Exception:
            self.overlay_value_label.setText("0")

    def _update_background_controls(self) -> None:
        enabled = self.chk_background_enabled.isChecked()
        self.background_path_edit.setEnabled(enabled)
        self.btn_browse_background.setEnabled(enabled)
        self.btn_clear_background.setEnabled(enabled)
        self.overlay_slider.setEnabled(enabled)
        self.overlay_value_label.setEnabled(enabled)

    def _clear_token(self) -> None:
        s = self._settings()
        s.remove("auth/api_token")
        s.remove("auth/username")
        s.remove("auth/full_name")
        s.remove("auth/role")
        QMessageBox.information(self, "Conta", "Token removido. Faça login novamente para usar IA.")

    def _apply(self) -> None:
        try:
            self._save()
        except Exception as e:
            QMessageBox.critical(self, "Preferências", f"Falha ao salvar preferências:\n\n{e}")
            return

        try:
            parent = self.parent()
            if parent is not None and hasattr(parent, "_apply_saved_theme"):
                parent._apply_saved_theme()
        except Exception:
            pass

        QMessageBox.information(self, "Preferências", "Preferências aplicadas.")

    def _ok(self) -> None:
        self._apply()
        self.accept()
