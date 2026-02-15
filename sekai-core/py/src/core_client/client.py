from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Optional


class SekaiCoreClient:
    """
    Cliente simples para o sekai-core.exe.
    Protocolo: stdin/stdout JSON por linha (NDJSON).
    Ajuste o formato se seu core usar outro protocolo.
    """

    def __init__(self, core_exe_path: str | Path):
        self.core_exe_path = str(core_exe_path)

        if not Path(self.core_exe_path).exists():
            raise FileNotFoundError(f"sekai-core.exe não encontrado: {self.core_exe_path}")

    def run(self, command: str, payload: Optional[dict[str, Any]] = None, timeout: Optional[float] = None) -> dict[str, Any]:
        req = {"cmd": command, "payload": payload or {}}

        p = subprocess.run(
            [self.core_exe_path],
            input=(json.dumps(req, ensure_ascii=False) + "\n").encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )

        if p.returncode != 0:
            err = p.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"sekai-core retornou {p.returncode}:\n{err}")

        out = p.stdout.decode("utf-8", errors="replace").strip()
        if not out:
            return {"ok": True, "result": None}

        try:
            return json.loads(out)
        except Exception:
            return {"ok": True, "result": out}
