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
    status: str = "untranslated",
    **extra,
) -> EntryDict:
    entry: EntryDict = {
        "original": original,
        "translation": translation,
        "status": status,
    }

    # Normalize status to the UI convention (lowercase snake_case).
    try:
        s = entry.get('status') or 'untranslated'
        if not isinstance(s, str):
            s = 'untranslated'
        s2 = s.strip().lower().replace(' ', '_')
        # Accept legacy/uppercase variants
        if s2 in ('untranslated', 'not_translated'):
            entry['status'] = 'untranslated'
        elif s2 in ('in_progress', 'inprogress'):
            entry['status'] = 'in_progress'
        elif s2 in ('translated', 'done'):
            entry['status'] = 'translated'
        elif s2 in ('reviewed', 'approved'):
            entry['status'] = 'reviewed'
        else:
            entry['status'] = s2 or 'untranslated'
    except Exception:
        entry['status'] = 'untranslated'

    if extra:
        entry.update(extra)

    return entry