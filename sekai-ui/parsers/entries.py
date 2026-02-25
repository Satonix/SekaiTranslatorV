from __future__ import annotations
from typing import TypedDict, NotRequired


class EntryDict(TypedDict, total=False):
    id: NotRequired[str]
    index: NotRequired[int]
    original: str
    translation: str
    status: str
    speaker: NotRequired[str]
    context: NotRequired[str]
    file: NotRequired[str]
    meta: NotRequired[dict]


def new_entry(
    original: str = "",
    translation: str = "",
    status: str = "UNTRANSLATED",
    **extra,
) -> EntryDict:
    entry: EntryDict = {
        "original": original,
        "translation": translation,
        "status": status,
    }

    if extra:
        entry.update(extra)

    return entry
