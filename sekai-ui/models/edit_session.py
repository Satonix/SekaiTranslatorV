from typing import List


class EditSession:
    """
    Sessão de edição para um conjunto de entries selecionadas.

    Responsabilidades:
    - Manter buffer lógico (linhas)
    - Atualizar status durante digitação (IN_PROGRESS)
    - Commit explícito (Enter)
    - Preservar last committed (para Undo correto)
    """

    def __init__(self):
        self.entries: List[dict] = []
        self.rows: List[int] = []

        self._current_lines: List[str] = []
        self._changed_indices: set[int] = set()
        self._active = False

    def start(self, entries: List[dict], rows: List[int]):
        self.entries = entries or []
        self.rows = rows or []

        for e in self.entries:
            if "_last_committed_translation" not in e:
                e["_last_committed_translation"] = (e.get("translation") or "").strip()
            if "_last_committed_status" not in e:
                e["_last_committed_status"] = e.get("status", "untranslated")

        self._current_lines = [e.get("translation", "") for e in self.entries]

        self._changed_indices.clear()
        self._active = True

    def clear(self):
        self.entries = []
        self.rows = []
        self._current_lines = []
        self._changed_indices.clear()
        self._active = False

    def is_active(self) -> bool:
        return self._active

    def on_text_edited(self, lines: List[str]):
        """
        Chamado a cada alteração no editor.
        Atualiza buffer e status IN_PROGRESS.
        """
        if not self._active:
            return

        self._current_lines = list(lines)

        for i, text in enumerate(lines):
            if i >= len(self.entries):
                continue

            entry = self.entries[i]
            self._changed_indices.add(i)

            entry["translation"] = text

            if text.strip():
                entry["status"] = "in_progress"
            else:
                entry["status"] = "untranslated"

    def commit(self) -> list[int]:
        """
        Confirma traduções.
        Retorna rows globais alteradas.
        Usa last_committed_* para permitir Undo correto.
        """
        if not self._active:
            return []

        changed_rows: list[int] = []

        for i, entry in enumerate(self.entries):
            if i >= len(self._current_lines):
                continue

            new_text = (self._current_lines[i] or "").strip()

            should_commit = (
                i in self._changed_indices
                or entry.get("status") == "in_progress"
            )
            if not should_commit:
                continue

            entry["translation"] = new_text
            entry["status"] = "translated" if new_text else "untranslated"

            entry["_last_committed_translation"] = new_text
            entry["_last_committed_status"] = entry["status"]

            changed_rows.append(self.rows[i])

        self._changed_indices.clear()
        return changed_rows
