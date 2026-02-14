from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional


@dataclass(frozen=True)
class UndoItem:
    row: int
    field: str
    old_value: Any
    new_value: Any


@dataclass(frozen=True)
class UndoAction:
    items: List[UndoItem]


class UndoStack:
    """
    Pilha simples de undo/redo para ações compostas.
    """

    def __init__(self):
        self._undo: List[UndoAction] = []
        self._redo: List[UndoAction] = []

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()

    def push(self, action: UndoAction) -> None:
        if not action.items:
            return
        self._undo.append(action)
        self._redo.clear()

    def pop_undo(self) -> Optional[UndoAction]:
        if not self._undo:
            return None
        act = self._undo.pop()
        self._redo.append(act)
        return act

    def pop_redo(self) -> Optional[UndoAction]:
        if not self._redo:
            return None
        act = self._redo.pop()
        self._undo.append(act)
        return act
