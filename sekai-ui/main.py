import sys
import os
import traceback

# garante que imports como `views.*` funcionem em builds empacotados
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Fonte única de verdade (CI escreve version.py a partir da tag)
try:
    from version import APP_NAME, APP_VERSION
except Exception:
    APP_NAME = "SekaiTranslatorV"
    APP_VERSION = "0.0.0"

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt

from core_client import SekaiCoreClient
from views.main_window import MainWindow


def apply_dark_theme(app: QApplication):
    """
    Tema escuro suave, baseado no SekaiTranslator original.
    Usa QPalette + Fusion.
    """
    app.setStyle("Fusion")

    palette = QPalette()

    palette.setColor(QPalette.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.WindowText, Qt.white)

    palette.setColor(QPalette.Base, QColor(24, 24, 24))
    palette.setColor(QPalette.AlternateBase, QColor(36, 36, 36))

    palette.setColor(QPalette.Text, Qt.white)

    palette.setColor(QPalette.Button, QColor(45, 45, 45))
    palette.setColor(QPalette.ButtonText, Qt.white)

    palette.setColor(QPalette.Highlight, QColor(60, 120, 200))
    palette.setColor(QPalette.HighlightedText, Qt.white)

    app.setPalette(palette)


def _show_fatal(title: str, message: str):
    # QMessageBox precisa de QApplication já criado
    QMessageBox.critical(None, title, message)


def _app_dir() -> str:
    """
    Retorna a pasta base do app.
    - PyInstaller: pasta do executável
    - Dev: pasta deste arquivo (main.py)
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def find_core_exe() -> str:
    """
    Resolve o caminho do sekai-core.exe de forma portátil.

    Ordem:
    1) env SEKAI_CORE_PATH (override)
    2) ao lado do exe (produção)
    3) fallback dev (repo)
    """
    # 1) Override por env (dev / power users)
    envp = (os.environ.get("SEKAI_CORE_PATH") or "").strip()
    if envp and os.path.exists(envp):
        return envp

    base = _app_dir()

    # 2) Produção: core ao lado do exe (Inno Setup instala assim)
    candidates = [
        os.path.join(base, "sekai-core.exe"),
        os.path.join(base, "core", "sekai-core.exe"),  # opcional (se você preferir subpasta)
    ]

    # 3) Dev fallback (repo)
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    candidates += [
        os.path.join(repo_root, "sekai-core", "target", "release", "sekai-core.exe"),
        os.path.join(repo_root, "sekai-core", "target", "debug", "sekai-core.exe"),
    ]

    for p in candidates:
        if os.path.exists(p):
            return p

    # Retorna o caminho "esperado" (para aparecer na mensagem de erro)
    return os.path.join(base, "sekai-core.exe")


def main():
    app = QApplication(sys.argv)
    apply_dark_theme(app)

    core_path = find_core_exe()

    if not os.path.exists(core_path):
        _show_fatal(
            "Core não encontrado",
            "Não foi possível localizar o executável do sekai-core.\n\n"
            f"Caminho esperado:\n{core_path}\n\n"
            "Verifique se o arquivo 'sekai-core.exe' está na mesma pasta do SekaiTranslatorV "
            "(ou reinstale).",
        )
        return 1

    core = SekaiCoreClient(core_path=core_path)

    try:
        core.start()

        # sanity check: ping (detecta core que abriu e morreu na hora)
        try:
            resp = core.send("ping", {}, timeout=5)
            if resp.get("status") != "ok":
                raise RuntimeError(resp.get("message") or "ping failed")
        except Exception as e:
            tail = "\n".join(core.get_stderr_tail(30)) if hasattr(core, "get_stderr_tail") else ""
            extra = f"\n\nstderr:\n{tail}" if tail else ""
            _show_fatal(
                "Falha ao iniciar o core",
                f"O sekai-core iniciou, mas não respondeu ao ping.\n\nErro: {e}{extra}",
            )
            return 1

        window = MainWindow(core, app_version=APP_VERSION, app_name=APP_NAME)
        window.show()

        exit_code = app.exec()
        return int(exit_code)

    except Exception:
        # Erro inesperado: mostra e garante stop do core
        err_text = traceback.format_exc()
        _show_fatal("Erro fatal", err_text)
        return 1

    finally:
        try:
            core.stop()
        except Exception:
            # não deixe erro no stop mascarar a saída do app
            pass


if __name__ == "__main__":
    sys.exit(main())
```0
