from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton,
    QFileDialog, QMessageBox, QComboBox, QTabWidget, QWidget
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

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # ---------------------
        # Aba Projeto
        # ---------------------
        tab_project = QWidget()
        p_layout = QVBoxLayout(tab_project)

        p_layout.addWidget(QLabel("Nome do projeto"))
        self.name_edit = QLineEdit()
        p_layout.addWidget(self.name_edit)

        p_layout.addWidget(QLabel("Pasta do jogo"))
        root_layout = QHBoxLayout()
        self.root_edit = QLineEdit()
        browse = QPushButton("Selecionar...")
        browse.clicked.connect(self._browse)
        root_layout.addWidget(self.root_edit)
        root_layout.addWidget(browse)
        p_layout.addLayout(root_layout)

        p_layout.addWidget(QLabel("Idioma original"))
        self.source_lang = QComboBox()
        for c, n in LANGUAGES.items():
            if c != "pt-BR":
                self.source_lang.addItem(n, c)
        p_layout.addWidget(self.source_lang)

        p_layout.addWidget(QLabel("Idioma da tradução"))
        self.target_lang = QComboBox()
        for c, n in LANGUAGES.items():
            self.target_lang.addItem(n, c)
        p_layout.addWidget(self.target_lang)

        p_layout.addStretch()
        self.tabs.addTab(tab_project, "Projeto")

        # ---------------------
        # Aba Engine
        # ---------------------
        tab_engine = QWidget()
        e_layout = QVBoxLayout(tab_engine)

        e_layout.addWidget(QLabel("Engine"))
        self.engine = QComboBox()
        e_layout.addWidget(self.engine)

        e_layout.addWidget(QLabel("Perfis"))
        self.profile = QComboBox()
        self.profile.setEnabled(False)
        e_layout.addWidget(self.profile)

        btn_refresh = QPushButton("Recarregar parsers")
        btn_refresh.clicked.connect(self._reload_parsers)
        e_layout.addWidget(btn_refresh)

        e_layout.addStretch()
        self.tabs.addTab(tab_engine, "Engine")

        # Footer
        btn = QPushButton("Criar Projeto")
        btn.clicked.connect(self._create)
        layout.addWidget(btn)

        self.engine.currentIndexChanged.connect(self._refresh_profiles)

        self._reload_parsers()

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Selecione a pasta do jogo")
        if path:
            self.root_edit.setText(path)

    def _reload_parsers(self):
        """
        Carrega parsers do registry (repo/external).
        Inclui Auto-detect (parser_id vazio).
        """
        self.engine.clear()
        self.profile.clear()

        try:
            mgr = reload_parsers()
        except Exception:
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

        if not ids:
            self.engine.addItem("Nenhum parser instalado (instale via Plugins → Parsers)", "__none__")
            self.profile.setEnabled(False)
            return

        base_to_profiles: dict[str, list[str]] = {}
        for eid in sorted(ids):
            if "." in eid:
                candidate = eid.rsplit(".", 1)[0]
                if candidate in ids:
                    prof = eid[len(candidate) + 1 :]
                    base_to_profiles.setdefault(candidate, []).append(prof)
                    continue
            base_to_profiles.setdefault(eid, [])

        items: list[tuple[str, str]] = []
        for base_id in base_to_profiles.keys():
            name, exts = meta_by_id.get(base_id, (base_id, set()))
            label = name
            if exts:
                label = f"{label}  ({', '.join(sorted(exts))})"
            items.append((label, base_id))

        items.sort(key=lambda t: t[0].lower())
        for label, base_id in items:
            self.engine.addItem(label, base_id)

        self._base_to_profiles = {k: sorted(set(v)) for k, v in base_to_profiles.items()}
        self._refresh_profiles()

    def _refresh_profiles(self):
        base_id = str(self.engine.currentData() or "").strip()
        self.profile.blockSignals(True)
        try:
            self.profile.clear()
            if not base_id or base_id == "__none__":
                self.profile.setEnabled(False)
                return

            profiles = list((getattr(self, "_base_to_profiles", {}) or {}).get(base_id, []) or [])
            if not profiles:
                self.profile.addItem("(Sem perfis)", "")
                self.profile.setEnabled(False)
                return

            self.profile.addItem("Padrão", "")
            for p in profiles:
                self.profile.addItem(str(p), str(p))
            self.profile.setEnabled(True)
        finally:
            self.profile.blockSignals(False)

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

    def _create(self):
        name = self.name_edit.text().strip()
        root = self.root_edit.text().strip()
        engine_id = (self.engine.currentData() or "").strip()
        profile = (self.profile.currentData() or "").strip()

        parser_id = ""
        if engine_id and engine_id != "__none__":
            parser_id = f"{engine_id}.{profile}" if profile else engine_id

        if not name or not root:
            QMessageBox.warning(self, "Erro", "Nome do projeto e pasta do jogo são obrigatórios.")
            return

        if engine_id == "__none__":
            QMessageBox.warning(
                self,
                "Parser",
                "Nenhum parser instalado.\n\n"
                "Instale parsers em Plugins → Parsers e tente novamente.",
            )
            return

        # Encoding de entrada é sempre o do arquivo original (detectado por arquivo)
        payload = {
            "name": name,
            "game_root": root,
            "encoding": "auto",
            "export_encoding": "utf-8",
            "engine": "",
            "parser_id": parser_id,
            "source_language": self.source_lang.currentData(),
            "target_language": self.target_lang.currentData(),
        }

        # Prefer UI-side persistence (sekai-core project persistence ainda é instável)
        from services.local_project_service import LocalProjectService
        try:
            project = LocalProjectService().create_project(payload)
            resp = {"status": "ok", "payload": {"project_path": project["project_path"], "project": project}}
        except Exception as e:
            resp = {"status": "error", "message": str(e)}

        if resp.get("status") != "ok":
            QMessageBox.critical(
                self,
                "Erro ao criar projeto",
                resp.get("message", "Erro desconhecido"),
            )
            return

        self.project_path = resp["payload"]["project_path"]
        self.accept()
