
from __future__ import annotations

import json
import os
import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple
from datetime import datetime

from models import project_state_store


def _safe_relpath(root: str, path: str) -> str:
    try:
        rel = os.path.relpath(path, root)
    except Exception:
        rel = os.path.basename(path)
    rel = rel.replace("\\", "/")
    return rel


def compute_project_id(project: dict) -> str:
    """
    Stable-ish ID used to prevent importing progress into the wrong project.
    Uses (name|root_path|engine_label) as seed.
    """
    name = (project.get("name") or "").strip()
    root = (project.get("root_path") or "").strip()
    engine = (project.get("engine") or "").strip()
    seed = f"{name}|{root}|{engine}"
    return hashlib.sha256(seed.encode("utf-8", errors="ignore")).hexdigest()[:24]


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass
class Conflict:
    rel_path: str
    entry_id: str
    field: str
    local_value: str
    incoming_value: str
    local_meta: dict
    incoming_meta: dict


@dataclass
class ImportReport:
    applied: int
    skipped_older: int
    conflicts: List[Conflict]
    base_mismatch: int


def export_sync_snapshot(project: dict) -> dict:
    """
    Exports a single JSON payload with all file states currently persisted.
    This is a full snapshot (professional baseline). Diff export can be added later.
    """
    root = (project.get("root_path") or "").strip()

    state_root = project_state_store.state_root(project)
    files_payload: List[dict] = []

    for dirpath, _, filenames in os.walk(state_root):
        for fn in filenames:
            if not fn.endswith(".json"):
                continue
            abs_state = os.path.join(dirpath, fn)
            try:
                with open(abs_state, "r", encoding="utf-8") as f:
                    st = json.load(f)
            except Exception:
                continue

            file_path = st.get("file_path") or ""
            entries = st.get("entries") if isinstance(st.get("entries"), list) else []
            rel_path = _safe_relpath(root, file_path) if file_path else _safe_relpath(state_root, abs_state)

            # fingerprint based on current state file content (not original game file)
            try:
                raw = json.dumps(entries, ensure_ascii=False, sort_keys=True).encode("utf-8", errors="ignore")
                fp = hashlib.sha256(raw).hexdigest()
            except Exception:
                fp = ""

            file_rec = {
                "rel_path": rel_path,
                "state_fingerprint": fp,
                "entries": [],
            }

            for e in entries:
                if not isinstance(e, dict):
                    continue
                eid = e.get("entry_id")
                if not isinstance(eid, str) or not eid:
                    continue

                file_rec["entries"].append({
                    "entry_id": eid,
                    "translation": e.get("translation") or "",
                    "status": e.get("status") or "untranslated",
                    "speaker": e.get("speaker") or e.get("meta", {}).get("speaker") or "",
                    "rev": int(e.get("_rev") or 0),
                    "updated_at": e.get("_updated_at") or "",
                    "updated_by": e.get("_updated_by") or "",
                })

            files_payload.append(file_rec)

    payload = {
        "format": "sekai-sync",
        "version": 1,
        "project_id": compute_project_id(project),
        "project_name": (project.get("name") or "").strip(),
        "engine": (project.get("engine") or "").strip(),
        "exported_at": _now_iso(),
        "exported_by": os.environ.get("SEKAI_USER_ID") or os.environ.get("USERNAME") or os.environ.get("USER") or "unknown",
        "files": files_payload,
    }
    return payload


def _parse_iso(ts: str) -> float:
    try:
        return datetime.fromisoformat(ts).timestamp()
    except Exception:
        return 0.0


def import_sync_snapshot(project: dict, payload: dict, *, prefer_incoming_on_conflict: bool = False) -> ImportReport:
    """
    Merges incoming snapshot into local persisted states.
    - Uses per-entry rev when present
    - Falls back to updated_at
    - Produces conflicts when both sides have different non-empty translations at same rev
    """
    if not isinstance(payload, dict) or payload.get("format") != "sekai-sync":
        raise ValueError("Arquivo de sincronização inválido (format).")

    if int(payload.get("version") or 0) != 1:
        raise ValueError("Versão do arquivo de sincronização não suportada.")

    incoming_pid = payload.get("project_id") or ""
    local_pid = compute_project_id(project)
    base_mismatch = 0
    if incoming_pid and incoming_pid != local_pid:
        # allow import but count mismatch (professional: warn)
        base_mismatch = 1

    root = (project.get("root_path") or "").strip()

    applied = 0
    skipped_older = 0
    conflicts: List[Conflict] = []

    files = payload.get("files") or []
    if not isinstance(files, list):
        raise ValueError("Arquivo de sincronização inválido (files).")

    # Build a mapping from rel_path -> absolute file_path if we have it via existing states
    # We'll merge into the persisted state files by loading them from project_state_store.
    for f_rec in files:
        if not isinstance(f_rec, dict):
            continue
        rel_path = f_rec.get("rel_path")
        if not isinstance(rel_path, str) or not rel_path:
            continue

        abs_file = os.path.join(root, rel_path.replace("/", os.sep)) if root else rel_path

        st = project_state_store.load_file_state(project, abs_file)
        if not st:
            # If no local state exists yet, create minimal from incoming
            local_entries: List[dict] = []
        else:
            local_entries = st.entries

        by_id: Dict[str, dict] = {}
        for e in local_entries:
            eid = e.get("entry_id")
            if isinstance(eid, str):
                by_id[eid] = e

        incoming_entries = f_rec.get("entries") or []
        if not isinstance(incoming_entries, list):
            continue

        for ie in incoming_entries:
            if not isinstance(ie, dict):
                continue
            eid = ie.get("entry_id")
            if not isinstance(eid, str) or not eid:
                continue

            inc_tr = ie.get("translation") or ""
            inc_st = ie.get("status") or "untranslated"
            inc_rev = int(ie.get("rev") or 0)
            inc_at = ie.get("updated_at") or ""
            inc_by = ie.get("updated_by") or ""

            le = by_id.get(eid)
            if le is None:
                # create a new entry shell only if it has something meaningful
                le = {"entry_id": eid, "translation": "", "status": "untranslated"}
                local_entries.append(le)
                by_id[eid] = le

            loc_tr = le.get("translation") or ""
            loc_st = le.get("status") or "untranslated"
            loc_rev = int(le.get("_rev") or 0)
            loc_at = le.get("_updated_at") or ""
            loc_by = le.get("_updated_by") or ""

            # decide if incoming is newer
            newer = False
            if inc_rev > loc_rev:
                newer = True
            elif inc_rev < loc_rev:
                newer = False
            else:
                # same rev -> use updated_at to decide, but conflicts if both differ and both non-empty
                if (loc_tr and inc_tr and loc_tr != inc_tr):
                    conflicts.append(Conflict(
                        rel_path=rel_path,
                        entry_id=eid,
                        field="translation",
                        local_value=loc_tr,
                        incoming_value=inc_tr,
                        local_meta={"rev": loc_rev, "updated_at": loc_at, "updated_by": loc_by},
                        incoming_meta={"rev": inc_rev, "updated_at": inc_at, "updated_by": inc_by},
                    ))
                    if not prefer_incoming_on_conflict:
                        skipped_older += 1
                        continue
                    newer = True
                else:
                    newer = _parse_iso(inc_at) > _parse_iso(loc_at)

            if not newer:
                skipped_older += 1
                continue

            # apply incoming
            if inc_tr != "":
                le["translation"] = inc_tr
            le["status"] = inc_st
            le["_rev"] = max(loc_rev, inc_rev)
            le["_updated_at"] = inc_at or _now_iso()
            le["_updated_by"] = inc_by or "import"
            applied += 1

        # persist merged state
        project_state_store.save_file_state(project, abs_file, local_entries)

    return ImportReport(applied=applied, skipped_older=skipped_older, conflicts=conflicts, base_mismatch=base_mismatch)
