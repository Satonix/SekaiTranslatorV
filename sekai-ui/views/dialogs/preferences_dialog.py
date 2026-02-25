from __future__ import annotations

import os

from PySide6.QtCore import QSettings
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
)


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
        self.resize(560, 460)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        appearance_box = QGroupBox("Aparência")
        appearance_layout = QVBoxLayout(appearance_box)
        appearance_layout.setSpacing(8)

        appearance_layout.addWidget(QLabel("Tema da interface"))

        self.theme_box = QComboBox()
        self.theme_box.addItems(["Dark (Padrão)", "Light", "Sistema"])
        appearance_layout.addWidget(self.theme_box)

        self.chk_custom_colors = QCheckBox("Usar cores personalizadas")
        appearance_layout.addWidget(self.chk_custom_colors)

        layout.addWidget(appearance_box)

        behavior_box = QGroupBox("Comportamento")
        behavior_layout = QVBoxLayout(behavior_box)
        behavior_layout.setSpacing(6)

        self.chk_autosave = QCheckBox("Salvar automaticamente projetos")
        self.chk_confirm_exit = QCheckBox("Confirmar ao sair com alterações não salvas")

        behavior_layout.addWidget(self.chk_autosave)
        behavior_layout.addWidget(self.chk_confirm_exit)

        layout.addWidget(behavior_box)

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
        hint.setStyleSheet("color: #888;")
        hint.setWordWrap(True)
        server_layout.addWidget(hint)

        layout.addWidget(server_box)

        layout.addStretch()

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

        theme = (s.value("ui/theme", "Dark (Padrão)") or "Dark (Padrão)").strip()
        idx = self.theme_box.findText(theme)
        if idx >= 0:
            self.theme_box.setCurrentIndex(idx)

        self.chk_custom_colors.setChecked(bool(s.value("ui/custom_colors", False)))
        self.chk_autosave.setChecked(bool(s.value("behavior/autosave", False)))
        self.chk_confirm_exit.setChecked(bool(s.value("behavior/confirm_exit", True)))

        auth_url = (s.value("auth/auth_url", "") or "").strip()
        proxy_url = (s.value("auth/proxy_url", "") or "").strip()

        self.auth_url_edit.setText(auth_url or self._default_auth_url())
        self.proxy_url_edit.setText(proxy_url or self._default_proxy_url())

    def _save(self) -> None:
        s = self._settings()

        s.setValue("ui/theme", self.theme_box.currentText())
        s.setValue("ui/custom_colors", self.chk_custom_colors.isChecked())

        s.setValue("behavior/autosave", self.chk_autosave.isChecked())
        s.setValue("behavior/confirm_exit", self.chk_confirm_exit.isChecked())

        s.setValue("auth/auth_url", self.auth_url_edit.text().strip())
        s.setValue("auth/proxy_url", self.proxy_url_edit.text().strip())

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

        QMessageBox.information(self, "Preferências", "Preferências aplicadas.")

    def _ok(self) -> None:
        self._apply()
        self.accept()
