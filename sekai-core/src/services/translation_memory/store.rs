use super::model::TMEntry;
use super::{hash, normalize};
use std::{
    collections::HashMap,
    fs,
    path::{Path, PathBuf},
};

const TM_FILE: &str = "translation_memory.json";

pub fn load() -> Vec<TMEntry> {
    if !Path::new(TM_FILE).exists() {
        return Vec::new();
    }

    let data = match fs::read_to_string(TM_FILE) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("[TM] failed to read {TM_FILE}: {e}");
            return Vec::new();
        }
    };

    let mut entries: Vec<TMEntry> = match serde_json::from_str(&data) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("[TM] failed to parse {TM_FILE}: {e}");
            return Vec::new();
        }
    };

    let mut migrated = false;

    for e in entries.iter_mut() {
        migrated |= ensure_norm_hash(e);
    }

    let (deduped, removed) = dedup(entries);
    if removed > 0 {
        migrated = true;
    }

    let mut final_entries = deduped;
    sort_entries(&mut final_entries);

    if migrated {
        if let Err(e) = save(&final_entries) {
            eprintln!("[TM] failed to persist migration: {e}");
        }
    }

    final_entries
}

pub fn save(entries: &[TMEntry]) -> Result<(), String> {
    let mut v: Vec<TMEntry> = entries.to_vec();

    for e in v.iter_mut() {
        ensure_norm_hash(e);
    }

    let (mut v, _removed) = dedup(v);
    sort_entries(&mut v);

    let json = serde_json::to_string_pretty(&v).map_err(|e| e.to_string())?;

    write_atomic(Path::new(TM_FILE), json.as_bytes())?;

    Ok(())
}


fn ensure_norm_hash(e: &mut TMEntry) -> bool {
    let mut changed = false;

    if e.normalized.is_empty() {
        e.normalized = normalize::normalize(&e.original);
        changed = true;
    }

    if e.hash.is_empty() {
        e.hash = hash::hash_norm(&e.normalized);
        changed = true;
    }

    changed
}

fn dedup(entries: Vec<TMEntry>) -> (Vec<TMEntry>, usize) {
    let mut map: HashMap<(String, String, String), TMEntry> = HashMap::new();
    let mut removed = 0usize;

    for mut e in entries {
        ensure_norm_hash(&mut e);

        let key = (e.source_lang.clone(), e.target_lang.clone(), e.hash.clone());

        match map.get_mut(&key) {
            None => {
                map.insert(key, e);
            }
            Some(existing) => {
                let keep_new = pick_better(existing, &e);
                if keep_new {
                    *existing = e;
                }
                removed += 1;
            }
        }
    }

    let out: Vec<TMEntry> = map.into_values().collect();
    (out, removed)
}

fn pick_better(current: &TMEntry, candidate: &TMEntry) -> bool {
    let cur_empty = current.translation.trim().is_empty();
    let cand_empty = candidate.translation.trim().is_empty();

    if cur_empty && !cand_empty {
        return true;
    }
    if !cur_empty && cand_empty {
        return false;
    }

    candidate.translation.len() > current.translation.len()
}

fn sort_entries(entries: &mut Vec<TMEntry>) {
    entries.sort_by(|a, b| {
        (
            a.source_lang.as_str(),
            a.target_lang.as_str(),
            a.hash.as_str(),
            a.normalized.as_str(),
            a.original.as_str(),
            a.translation.as_str(),
        )
            .cmp(&(
                b.source_lang.as_str(),
                b.target_lang.as_str(),
                b.hash.as_str(),
                b.normalized.as_str(),
                b.original.as_str(),
                b.translation.as_str(),
            ))
    });
}

fn write_atomic(path: &Path, bytes: &[u8]) -> Result<(), String> {
    let tmp = tmp_path(path);

    if let Some(parent) = tmp.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }

    fs::write(&tmp, bytes).map_err(|e| e.to_string())?;

    if path.exists() {
        fs::remove_file(path).map_err(|e| e.to_string())?;
    }

    fs::rename(&tmp, path).map_err(|e| e.to_string())?;

    Ok(())
}

fn tmp_path(path: &Path) -> PathBuf {
    let mut p = path.to_path_buf();
    let file_name = match path.file_name().and_then(|s| s.to_str()) {
        Some(n) => n.to_string(),
        None => "tm".to_string(),
    };
    p.set_file_name(format!("{file_name}.tmp"));
    p
}
