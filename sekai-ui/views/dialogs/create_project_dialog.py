from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton,
    QFileDialog, QMessageBox, QComboBox
)

from parsers.manager import get_parser_manager, reload_parsers


LANGUAGES = {
    "en": "Inglês",
    "ja": "Japonês",
    "zh": "Chinês",
    "pt-BR": "Português (Brasil)",
    "es": "Espanhol",
}


class CreateProjectDialog(QDialog):
    """
    Cria um projeto no core, e o seletor principal é PARSER (plugin_id).

    - Mostra parsers instalados (repo/external)
    - Salva parser_id diretamente no project.create (core já persiste no project.json)
    - engine é legado e vai vazio
    """

    def __init__(self, core_client, parent=None):
        super().__init__(parent)

        self.core = core_client
        self.project_path = None

        self.setWindowTitle("Criar Projeto")
        self.resize(460, 420)

        layout = QVBoxLayout(self)

        # Nome
        layout.addWidget(QLabel("Nome do projeto"))
        self.name_edit = QLineEdit()
        layout.addWidget(self.name_edit)

        # Pasta do jogo
        layout.addWidget(QLabel("Pasta do jogo"))
        root_layout = QHBoxLayout()
        self.root_edit = QLineEdit()
        browse = QPushButton("Selecionar...")
        browse.clicked.connect(self._browse)
        root_layout.addWidget(self.root_edit)
        root_layout.addWidget(browse)
        layout.addLayout(root_layout)

        # Encoding
        layout.addWidget(QLabel("Encoding do texto"))
        self.encoding = QComboBox()
        self.encoding.addItem("Detectar automaticamente", "auto")
        self.encoding.addItems([
            "utf-8",
            "utf-8-sig",
            "cp932",
            "shift_jis",
        ])
        layout.addWidget(self.encoding)

        # Idiomas
        layout.addWidget(QLabel("Idioma original"))
        self.source_lang = QComboBox()
        for c, n in LANGUAGES.items():
            if c != "pt-BR":
                self.source_lang.addItem(n, c)
        layout.addWidget(self.source_lang)

        layout.addWidget(QLabel("Idioma da tradução"))
        self.target_lang = QComboBox()
        for c, n in LANGUAGES.items():
            self.target_lang.addItem(n, c)
        layout.addWidget(self.target_lang)

        # Parser
        layout.addWidget(QLabel("Parser do jogo"))
        self.parser = QComboBox()
        layout.addWidget(self.parser)

        btn_refresh = QPushButton("Recarregar parsers")
        btn_refresh.clicked.connect(self._reload_parsers)
        layout.addWidget(btn_refresh)

        self._reload_parsers()

        # Criar
        btn = QPushButton("Criar Projeto")
        btn.clicked.connect(self._create)
        layout.addWidget(btn)

    # ---------------------------
    # UI helpers
    # ---------------------------
    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Selecione a pasta do jogo")
        if path:
            self.root_edit.setText(path)

    def _reload_parsers(self):
        """
        Carrega parsers do registry (repo/external).
        Inclui Auto-detect (parser_id vazio).
        """
        self.parser.clear()

        try:
            mgr = reload_parsers()
        except Exception:
            mgr = get_parser_manager()

        # Auto
        self.parser.addItem("Auto-detect (recomendado)", "")

        plugins = mgr.all_plugins() if mgr else []
        items: list[tuple[str, str]] = []

        for p in plugins:
            pid = (getattr(p, "plugin_id", "") or "").strip()
            name = (getattr(p, "name", "") or "").strip()
            exts = getattr(p, "extensions", None) or set()

            if not pid:
                continue

            label = name or pid
            if exts:
                label = f"{label}  ({', '.join(sorted({str(e).lower() for e in exts}))})"

            items.append((label, pid))

        items.sort(key=lambda t: t[0].lower())

        for label, pid in items:
            self.parser.addItem(label, pid)

        if self.parser.count() == 1:
            # só ficou o Auto
            self.parser.addItem("Nenhum parser instalado (instale via Plugins → Parsers)", "__none__")
            self.parser.setCurrentIndex(1)

    # ---------------------------
    # Core helpers
    # ---------------------------
    def _detect_encoding(self, root_path: str) -> str:
        """
        Pede ao sekai-core para detectar encoding.
        Fallback seguro: utf-8
        """
        resp = self.core.send("detect_encoding", {"path": root_path})

        if resp.get("status") != "ok":
            QMessageBox.warning(
                self,
                "Encoding",
                "Não foi possível detectar o encoding automaticamente.\n"
                "utf-8 será utilizado como fallback.",
            )
            return "utf-8"

        payload = resp.get("payload") or {}
        if isinstance(payload, dict):
            return (payload.get("encoding") or "utf-8").strip() or "utf-8"

        return "utf-8"

    # ---------------------------
    # Create flow
    # ---------------------------
    def _create(self):
        name = self.name_edit.text().strip()
        root = self.root_edit.text().strip()
        parser_id = (self.parser.currentData() or "").strip()

        if not name or not root:
            QMessageBox.warning(self, "Erro", "Nome do projeto e pasta do jogo são obrigatórios.")
            return

        # Nenhum parser instalado
        if parser_id == "__none__":
            QMessageBox.warning(
                self,
                "Parser",
                "Nenhum parser instalado.\n\n"
                "Instale parsers em Plugins → Parsers e tente novamente.",
            )
            return

        # Encoding
        enc_data = self.encoding.currentData()
        if enc_data == "auto":
            encoding = self._detect_encoding(root)
        else:
            encoding = self.encoding.currentText()

        # ✅ cria o projeto no core (parser_id já persiste no project.json)
        resp = self.core.send("project.create", {
            "name": name,
            "game_root": root,
            "encoding": encoding,
            "engine": "",           # legado
            "parser_id": parser_id, # "" = auto-detect
            "source_language": self.source_lang.currentData(),
            "target_language": self.target_lang.currentData(),
        })

        if resp.get("status") != "ok":
            QMessageBox.critical(
                self,
                "Erro ao criar projeto",
                resp.get("message", "Erro desconhecido"),
            )
            return

        self.project_path = resp["payload"]["project_path"]
        self.accept()
