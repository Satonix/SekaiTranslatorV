use crate::model::entry::{CoreEntry, EntryStatus};
use crate::services::{
    ai,
    ai_types::AiRunReport,
    translation_memory::{hash, matcher, model::TMEntry, normalize, store},
};

use std::collections::HashMap;

pub struct PipelineConfig<'a> {
    pub provider: &'a str,
    pub api_key: &'a str,
    pub model: &'a str,
    pub source_lang: &'a str,
    pub target_lang: &'a str,
}

#[derive(Debug, serde::Serialize)]
pub struct PipelineReport {
    pub used_tm: usize,
    pub used_ai: usize,
    pub ai_report: Option<AiRunReport>,
}

pub fn run(entries: &mut [CoreEntry], cfg: PipelineConfig) -> Result<PipelineReport, String> {
    let mut tm_entries = store::load();

    let mut used_tm = 0usize;

    let mut ai_needed: Vec<usize> = Vec::new();

    for (i, e) in entries.iter_mut().enumerate() {
        if !e.is_translatable {
            continue;
        }

        if let Some(tm) =
            matcher::exact_match(&tm_entries, cfg.source_lang, cfg.target_lang, &e.original)
        {
            e.translation = tm.translation.clone();
            e.status = EntryStatus::Translated;
            used_tm += 1;
        } else {
            ai_needed.push(i);
        }
    }

    let mut ai_report: Option<AiRunReport> = None;
    let mut used_ai = 0usize;

    if !ai_needed.is_empty() {
        let mut slice: Vec<CoreEntry> = ai_needed.iter().map(|&i| entries[i].clone()).collect();

        let cfg_ai = ai::AiConfig {
            provider: cfg.provider,
            api_key: cfg.api_key,
            model: cfg.model,
            source_lang: cfg.source_lang,
            target_lang: cfg.target_lang,
        };

        let report = ai::translate_entries(&mut slice, cfg_ai)?;

        let mut ok_by_id: HashMap<String, bool> = HashMap::new();
        for item in &report.items {
            ok_by_id.insert(item.entry_id.clone(), item.ok);
        }

        for (&idx, translated) in ai_needed.iter().zip(slice.into_iter()) {
            let target = &mut entries[idx];

            let ok = ok_by_id.get(&translated.entry_id).copied().unwrap_or(false);

            if ok && !translated.translation.trim().is_empty() {
                target.translation = translated.translation.clone();
                target.status = EntryStatus::Translated;
                used_ai += 1;

                let norm = normalize::normalize(&target.original);
                let h = hash::hash_norm(&norm);

                tm_entries.push(TMEntry {
                    source_lang: cfg.source_lang.to_string(),
                    target_lang: cfg.target_lang.to_string(),
                    original: target.original.clone(),
                    translation: target.translation.clone(),
                    normalized: norm,
                    hash: h,
                });
            } else {
                if target.translation.trim().is_empty() {
                    target.status = EntryStatus::Untranslated;
                } else {
                    target.status = EntryStatus::InProgress;
                }
            }
        }

        ai_report = Some(report);
    }

    store::save(&tm_entries)?;

    Ok(PipelineReport {
        used_tm,
        used_ai,
        ai_report,
    })
}
