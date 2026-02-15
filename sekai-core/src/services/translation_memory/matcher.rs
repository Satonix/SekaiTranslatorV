use super::model::TMEntry;
use super::{hash, normalize};

pub fn exact_match<'a>(
    entries: &'a [TMEntry],
    source_lang: &str,
    target_lang: &str,
    original: &str,
) -> Option<&'a TMEntry> {
    let trimmed = original.trim();
    if trimmed.is_empty() {
        return None;
    }

    let norm = normalize::normalize(trimmed);
    let h = hash::hash_norm(&norm);

    entries.iter().find(|e| {
        e.source_lang == source_lang
            && e.target_lang == target_lang
            && e.hash == h
            && e.normalized == norm
    })
}
