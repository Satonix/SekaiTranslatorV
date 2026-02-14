# views/dialogs/login_dialog.py

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QMessageBox,
)


class LoginDialog(QDialog):
    """
    Dialog de login (real) via auth.php.

    Saídas após sucesso:
    - self.username (str)
    - self.api_token (str)
    - self.user_data (dict)  # id, username, full_name, role
    Também persiste em QSettings.

    NÃO altera o PHP. Apenas consome o endpoint.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Login")
        self.setModal(True)
        self.resize(320, 180)

        self.username: str | None = None
        self.api_token: str | None = None
        self.user_data: dict | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("Conta Sekai")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        # Usuário
        self.user_edit = QLineEdit()
        self.user_edit.setPlaceholderText("Usuário ou email")
        layout.addWidget(self.user_edit)

        # Senha
        self.pass_edit = QLineEdit()
        self.pass_edit.setPlaceholderText("Senha")
        self.pass_edit.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.pass_edit)

        # Botões
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_login = QPushButton("Entrar")

        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_login)

        layout.addStretch()
        layout.addLayout(btn_layout)

        # Conexões
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_login.clicked.connect(self._on_login)

        # Enter para logar
        self.user_edit.returnPressed.connect(self._on_login)
        self.pass_edit.returnPressed.connect(self._on_login)

        # tenta preencher último user salvo
        try:
            s = self._settings()
            last_user = (s.value("auth/last_username", "") or "").strip()
            if last_user:
                self.user_edit.setText(last_user)
                self.pass_edit.setFocus()
        except Exception:
            pass

    # -------------------------------------------------
    # Settings / URLs
    # -------------------------------------------------
    def _settings(self) -> QSettings:
        return QSettings("SekaiTranslator", "SekaiTranslator")

    def _auth_url(self) -> str:
        """
        Default assume:
        https://green-gaur-846876.hostingersite.com/api/auth.php

        Você pode sobrescrever por:
        - env SEKAI_AUTH_URL
        - QSettings: auth/auth_url
        """
        s = self._settings()
        v = (s.value("auth/auth_url", "") or "").strip()
        if v:
            return v

        env = (os.environ.get("SEKAI_AUTH_URL") or "").strip()
        if env:
            return env

        return "https://green-gaur-846876.hostingersite.com/api/auth.php"

    # -------------------------------------------------
    # HTTP
    # -------------------------------------------------
    def _post_json(self, url: str, payload: dict, *, timeout: float = 25.0) -> dict:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url=url,
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=float(timeout)) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                try:
                    return json.loads(raw) if raw else {}
                except Exception:
                    return {"status": "error", "message": "Resposta inválida do servidor.", "raw": raw}
        except urllib.error.HTTPError as e:
            raw = ""
            try:
                raw = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass

            # tenta extrair message do JSON
            msg = f"HTTP {e.code}"
            try:
                j = json.loads(raw) if raw else {}
                if isinstance(j, dict):
                    msg = j.get("message") or j.get("error") or msg
            except Exception:
                pass

            return {"status": "error", "message": msg, "http_status": e.code, "raw": raw}
        except urllib.error.URLError as e:
            return {"status": "error", "message": f"Falha de conexão: {e}"}
        except Exception as e:
            return {"status": "error", "message": f"Erro inesperado: {e}"}

    # -------------------------------------------------
    # Actions
    # -------------------------------------------------
    def _on_login(self):
        user = self.user_edit.text().strip()
        pwd = self.pass_edit.text().strip()

        if not user or not pwd:
            QMessageBox.warning(self, "Login", "Informe usuário e senha.")
            return

        self.btn_login.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        try:
            resp = self._post_json(
                self._auth_url(),
                {"username": user, "password": pwd},
                timeout=25.0,
            )

            # seu PHP usa: status=success + api_token
            if resp.get("status") != "success":
                msg = resp.get("message") or "Falha no login."
                QMessageBox.critical(self, "Login", msg)
                return

            token = (resp.get("api_token") or "").strip()
            if not token:
                QMessageBox.critical(self, "Login", "Servidor não retornou api_token.")
                return

            data = resp.get("data") if isinstance(resp.get("data"), dict) else {}

            self.username = (data.get("username") or user).strip()
            self.api_token = token
            self.user_data = data

            # Persistência
            try:
                s = self._settings()
                s.setValue("auth/api_token", token)
                s.setValue("auth/username", self.username)
                s.setValue("auth/full_name", (data.get("full_name") or "").strip())
                s.setValue("auth/role", (data.get("role") or "").strip())
                s.setValue("auth/last_username", user)
            except Exception:
                pass

            self.accept()

        finally:
            self.btn_login.setEnabled(True)
            self.btn_cancel.setEnabled(True)
