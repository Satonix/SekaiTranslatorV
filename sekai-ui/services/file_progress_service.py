from __future__ import annotations

from typing import Any

from models import project_state_store


_PROGRESS_CACHE: dict[tuple[str, str], tuple[tuple[int, int] | tuple[str], dict[str, Any]]] = {}


def entry_translation_text(entry: dict[str, Any]) -> str:
    tr = entry.get('translation')
    if isinstance(tr, str) and tr.strip():
        return tr.strip()

    tr2 = entry.get('_last_committed_translation')
    if isinstance(tr2, str) and tr2.strip():
        return tr2.strip()

    return ''


def normalize_status(value: object) -> str:
    s = str(value or '').strip().lower().replace(' ', '_')
    if s in ('untranslated', 'not_translated', 'untranslated.'):
        return 'untranslated'
    if s in ('inprogress', 'in_progress'):
        return 'in_progress'
    if s in ('translated', 'done'):
        return 'translated'
    if s in ('reviewed', 'approved'):
        return 'reviewed'
    return s or 'untranslated'


def compute_entries_progress(entries: list[dict[str, Any]] | None) -> tuple[int, int, int]:
    total = 0
    done = 0

    for entry in entries or []:
        original = entry.get('original')
        if not isinstance(original, str) or not original.strip():
            continue

        total += 1
        tr = entry_translation_text(entry)
        if tr:
            done += 1

    if total == 0:
        return 0, 0, 100

    percent = int(round((done / total) * 100))
    return done, total, percent



def invalidate_progress_cache(project: dict | None = None, file_path: str | None = None) -> None:
    if project and file_path:
        try:
            key = (project_state_store._project_key(project), file_path)
            _PROGRESS_CACHE.pop(key, None)
            return
        except Exception:
            pass
    _PROGRESS_CACHE.clear()


def get_file_progress(project: dict, file_path: str) -> dict[str, Any]:
    try:
        cache_key = (project_state_store._project_key(project), file_path)
    except Exception:
        cache_key = ("", file_path)

    try:
        state_path = project_state_store.state_path_for_file(project, file_path)
        sig = project_state_store._file_sig(state_path) or ("missing",)
    except Exception:
        sig = ("missing",)

    cached = _PROGRESS_CACHE.get(cache_key)
    if cached and cached[0] == sig:
        return cached[1]

    state = project_state_store.load_file_state(project, file_path)
    if state is None:
        result = {
            'has_state': False,
            'done': 0,
            'total': 0,
            'percent': 0,
            'is_full': False,
        }
        _PROGRESS_CACHE[cache_key] = (sig, result)
        return result

    done, total, percent = compute_entries_progress(state.entries)
    result = {
        'has_state': True,
        'done': done,
        'total': total,
        'percent': percent,
        'is_full': percent >= 100,
    }
    _PROGRESS_CACHE[cache_key] = (sig, result)
    return result

    done, total, percent = compute_entries_progress(state.entries)
    return {
        'has_state': True,
        'done': done,
        'total': total,
        'percent': percent,
        'is_full': percent >= 100,
    }
