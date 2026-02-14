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

    // 1) Migração leve + 2) dedup + 3) sort (determinístico)
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

    // Persistir migrações/normalizações/dedup
    if migrated {
        if let Err(e) = save(&final_entries) {
            eprintln!("[TM] failed to persist migration: {e}");
        }
    }

    final_entries
}

pub fn save(entries: &[TMEntry]) -> Result<(), String> {
    // Copia para poder garantir invariantes sem mutar chamador
    let mut v: Vec<TMEntry> = entries.to_vec();

    // Garantir invariantes (normalized/hash) antes de persistir
    for e in v.iter_mut() {
        ensure_norm_hash(e);
    }

    // Dedup + sort antes de salvar (arquivo estável)
    let (mut v, _removed) = dedup(v);
    sort_entries(&mut v);

    let json = serde_json::to_string_pretty(&v).map_err(|e| e.to_string())?;

    write_atomic(Path::new(TM_FILE), json.as_bytes())?;

    Ok(())
}

// Internals

fn ensure_norm_hash(e: &mut TMEntry) -> bool {
    // Retorna true se alterou (migração)
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
    // Regra: chave determinística por língua + hash.
    // Preferência: manter a "melhor" entry caso haja colisão.
    // Critério simples (determinístico):
    // - preferir tradução não vazia
    // - se ambas não vazias, preferir a mais longa (tende a ser mais completa)
    // - fallback: manter a primeira após sort (mas aqui ainda não sortamos; então aplicamos regra local)
    let mut map: HashMap<(String, String, String), TMEntry> = HashMap::new();
    let mut removed = 0usize;

    for mut e in entries {
        // Garantir invariantes para chave correta
        ensure_norm_hash(&mut e);

        let key = (e.source_lang.clone(), e.target_lang.clone(), e.hash.clone());

        match map.get_mut(&key) {
            None => {
                map.insert(key, e);
            }
            Some(existing) => {
                // Decide qual manter
                let keep_new = pick_better(existing, &e);
                if keep_new {
                    *existing = e;
                }
                removed += 1;
            }
        }
    }

    let out: Vec<TMEntry> = map.into_values().collect();
    // Não esquecer: ordenação é feita fora (load/save)
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

    // ambos vazios ou ambos não vazios -> preferir a mais longa
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
    // Estratégia: escrever em arquivo temporário no mesmo diretório e renomear.
    // Em Windows, rename sobre existente pode falhar; então removemos antes.
    let tmp = tmp_path(path);

    if let Some(parent) = tmp.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }

    fs::write(&tmp, bytes).map_err(|e| e.to_string())?;

    // Remover destino antes (melhor compatibilidade no Windows)
    if path.exists() {
        fs::remove_file(path).map_err(|e| e.to_string())?;
    }

    fs::rename(&tmp, path).map_err(|e| e.to_string())?;

    Ok(())
}

fn tmp_path(path: &Path) -> PathBuf {
    // translation_memory.json.tmp
    let mut p = path.to_path_buf();
    let file_name = match path.file_name().and_then(|s| s.to_str()) {
        Some(n) => n.to_string(),
        None => "tm".to_string(),
    };
    p.set_file_name(format!("{file_name}.tmp"));
    p
}
