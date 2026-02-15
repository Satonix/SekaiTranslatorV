import json
import subprocess
import threading
from dataclasses import dataclass
from queue import Queue, Empty
from typing import Any


@dataclass
class _Pending:
    q: "Queue[dict]"


class SekaiCoreClient:
    """
    Cliente IPC (stdin/stdout) para o sekai-core (Rust).

    Garantias:
    - id incremental por request
    - pareamento resposta ↔ request via id
    - tratamento de core morto / pipe quebrado
    - captura de stderr (útil para debugging)
    - timeout configurável

    Contrato esperado do core:
    Request:  {"id": <int|str>, "cmd": str, "payload": object}
    Response: {"id": <id>, "status": "ok"|"error", "payload": object? , "message": str?}
    """

    def __init__(self, core_path: str, *, default_timeout: float = 60.0):
        self.core_path = core_path
        self.default_timeout = float(default_timeout)

        self.proc: subprocess.Popen[str] | None = None

        self._lock = threading.Lock()
        self._next_id = 1

        self._pending: dict[Any, _Pending] = {}

        self._stdout_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None

        self._stderr_lines: "Queue[str]" = Queue()
        self._running = False

    def start(self) -> None:
        if self.proc and self.proc.poll() is None:
            return

        self.proc = subprocess.Popen(
            [self.core_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )

        self._running = True

        self._stdout_thread = threading.Thread(target=self._read_stdout, daemon=True)
        self._stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)

        self._stdout_thread.start()
        self._stderr_thread.start()

    def stop(self) -> None:
        self._running = False

        if not self.proc:
            return

        try:
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=1.5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait(timeout=1.5)
        finally:
            self._fail_all_pending("core process stopped")
            self.proc = None

    def send(self, cmd: str, payload: dict | None = None, *, timeout: float | None = None) -> dict:
        """
        Envia um comando e aguarda a resposta correspondente (mesmo id).
        """
        if not self.proc or self.proc.poll() is not None:
            raise RuntimeError("sekai-core is not running (call start())")

        req_id = self._alloc_id()

        q: "Queue[dict]" = Queue(maxsize=1)
        with self._lock:
            self._pending[req_id] = _Pending(q=q)

        msg = {
            "id": req_id,
            "cmd": cmd,
            "payload": payload or {},
        }

        try:
            self._write_line(json.dumps(msg, ensure_ascii=False))
        except Exception as e:
            with self._lock:
                self._pending.pop(req_id, None)
            raise RuntimeError(f"failed to send to sekai-core: {e}") from e

        wait_timeout = self.default_timeout if timeout is None else float(timeout)

        try:
            resp = q.get(timeout=wait_timeout)
        except Empty:
            stderr_tail = self._drain_stderr_tail(max_lines=8)
            with self._lock:
                self._pending.pop(req_id, None)

            extra = ""
            if stderr_tail:
                extra = "\n\n[sekai-core stderr tail]\n" + "\n".join(stderr_tail)

            raise TimeoutError(
                f"sekai-core timeout waiting for response (cmd={cmd}, id={req_id}){extra}"
            )

        return resp

    def get_stderr_tail(self, max_lines: int = 50) -> list[str]:
        """
        Útil para mostrar em dialog de erro, logs, etc.
        """
        max_lines = max(1, int(max_lines))
        return self._drain_stderr_tail(max_lines=max_lines)

    def _write_line(self, line: str) -> None:
        if not self.proc or not self.proc.stdin:
            raise RuntimeError("stdin not available")

        if self.proc.poll() is not None:
            raise RuntimeError("sekai-core process exited")

        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()

    def _read_stdout(self) -> None:
        assert self.proc is not None
        assert self.proc.stdout is not None

        for raw in self.proc.stdout:
            if not self._running:
                break

            line = raw.strip()
            if not line:
                continue

            try:
                msg = json.loads(line)
            except Exception:
                continue

            msg_id = msg.get("id", None)
            if msg_id is None:
                continue

            key: Any = msg_id
            if isinstance(msg_id, str) and msg_id.isdigit():
                key = int(msg_id)

            with self._lock:
                pending = self._pending.pop(key, None)

            if pending:
                try:
                    pending.q.put_nowait(msg)
                except Exception:
                    pass
            else:
                pass

        self._fail_all_pending("core stdout closed")

    def _read_stderr(self) -> None:
        assert self.proc is not None
        assert self.proc.stderr is not None

        for raw in self.proc.stderr:
            if not self._running:
                break
            line = raw.rstrip("\n")
            if line:
                self._stderr_lines.put(line)

    def _alloc_id(self) -> int:
        with self._lock:
            rid = self._next_id
            self._next_id += 1
        return rid

    def _fail_all_pending(self, message: str) -> None:
        """
        Envia uma resposta de erro sintética para todas as requests pendentes,
        para evitar deadlock da UI.
        """
        with self._lock:
            pendings = list(self._pending.values())
            self._pending.clear()

        err = {"id": None, "status": "error", "message": message}
        for p in pendings:
            try:
                p.q.put_nowait(err)
            except Exception:
                pass

    def _drain_stderr_tail(self, max_lines: int) -> list[str]:
        """
        Pega as últimas N linhas de stderr já capturadas (não bloqueia).
        """
        max_lines = max(1, int(max_lines))
        lines: list[str] = []

        while True:
            try:
                lines.append(self._stderr_lines.get_nowait())
            except Empty:
                break

        if len(lines) <= max_lines:
            return lines
        return lines[-max_lines:]
