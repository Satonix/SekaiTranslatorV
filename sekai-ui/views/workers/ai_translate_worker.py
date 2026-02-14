# views/workers/ai_translate_worker.py
from __future__ import annotations

import json
import urllib.request
import urllib.error

from PySide6.QtCore import QObject, Signal, Slot


class AITranslateWorker(QObject):
    """
    Worker para rodar request HTTP em thread (sem travar UI).

    Para progresso real:
    - traduz em chunks (por padrão 1 linha por request)
    - emite progress(done, total)

    Emite:
      - progress(int done, int total)
      - finished(dict) em sucesso  -> {"results": [{"id": "...", "translation": "..."}...]}
      - failed(str) em erro
      - canceled() se cancelado
    """
    progress = Signal(int, int)   # done, total
    finished = Signal(dict)
    failed = Signal(str)
    canceled = Signal()

    def __init__(
        self,
        proxy_url: str,
        api_token: str,
        payload: dict,
        timeout: float = 120.0,
        parent=None,
        *,
        chunk_size: int = 1,
    ):
        super().__init__(parent)
        self.proxy_url = str(proxy_url or "").strip()
        self.api_token = str(api_token or "").strip()
        self.payload = payload if isinstance(payload, dict) else {}
        self.timeout = float(timeout)

        self.chunk_size = max(1, int(chunk_size or 1))
        self._cancel_requested = False

    # -----------------------------
    # Cancel
    # -----------------------------
    @Slot()
    def cancel(self) -> None:
        self._cancel_requested = True

    def _is_canceled(self) -> bool:
        return bool(self._cancel_requested)

    # -----------------------------
    # Run
    # -----------------------------
    @Slot()
    def run(self) -> None:
        try:
            if not self.proxy_url:
                raise RuntimeError("proxy_url vazio.")
            if not self.api_token:
                raise RuntimeError("api_token vazio.")

            items = self.payload.get("items")
            if not isinstance(items, list):
                raise RuntimeError("Payload inválido: 'items' precisa ser uma lista.")

            total = len(items)
            if total <= 0:
                self.finished.emit({"results": []})
                return

            target_language = (self.payload.get("target_language") or "").strip()
            if not target_language:
                raise RuntimeError("Payload inválido: 'target_language' vazio.")

            # Opcional: repassa parâmetros adicionais se existirem
            custom_prompt_text = self.payload.get("custom_prompt_text")
            user_prompt = self.payload.get("user_prompt")

            results: list[dict] = []
            done = 0
            self.progress.emit(done, total)

            # processa em chunks para permitir progresso real
            for start in range(0, total, self.chunk_size):
                if self._is_canceled():
                    self.canceled.emit()
                    return

                chunk = items[start:start + self.chunk_size]

                chunk_payload: dict = {
                    "items": chunk,
                    "target_language": target_language,
                }
                if isinstance(custom_prompt_text, str) and custom_prompt_text.strip():
                    chunk_payload["custom_prompt_text"] = custom_prompt_text
                if isinstance(user_prompt, str) and user_prompt.strip():
                    chunk_payload["user_prompt"] = user_prompt

                resp = self._post_json_bearer(
                    self.proxy_url,
                    self.api_token,
                    chunk_payload,
                    timeout=self.timeout,
                )

                if isinstance(resp, dict) and resp.get("error"):
                    raise RuntimeError(str(resp.get("error")))

                if not (isinstance(resp, dict) and isinstance(resp.get("results"), list)):
                    raise RuntimeError("Resposta inesperada do proxy: esperado dict com 'results' list.")

                # acumula resultados
                for r in resp["results"]:
                    if isinstance(r, dict):
                        results.append(r)

                done = min(total, done + len(chunk))
                self.progress.emit(done, total)

            # Padroniza saída final
            self.finished.emit({"results": results})

        except Exception as e:
            self.failed.emit(str(e))

    # -----------------------------
    # HTTP
    # -----------------------------
    def _post_json_bearer(self, url: str, token: str, payload: dict, *, timeout: float = 120.0) -> dict:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url=url,
            data=data,
            method="POST",
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=float(timeout)) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                try:
                    return json.loads(raw) if raw else {}
                except Exception:
                    return {"error": "Resposta inválida do servidor.", "raw": raw}

        except urllib.error.HTTPError as e:
            raw = ""
            try:
                raw = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass

            msg = f"HTTP {e.code}"
            try:
                j = json.loads(raw) if raw else {}
                if isinstance(j, dict):
                    msg = j.get("message") or j.get("error") or msg
            except Exception:
                pass

            return {"error": msg, "http_status": e.code, "raw": raw}

        except urllib.error.URLError as e:
            return {"error": f"Falha de conexão: {e}"}

        except Exception as e:
            return {"error": f"Erro inesperado: {e}"}
