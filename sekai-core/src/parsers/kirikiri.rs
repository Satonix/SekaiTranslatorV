use crate::model::entry::{CoreEntry, EntryStatus};
use regex::Regex;

pub fn parse(text: &str) -> Vec<CoreEntry> {
    let mut entries = Vec::new();

    let dialog_re = Regex::new(
        r#"^(?P<prefix>\s*<(?P<speaker>[^>]+)>[\"\(])(?P<text>.*?)(?P<suffix>[\"\)]\s*)$"#,
    )
    .unwrap();

    for (i, line) in text.lines().enumerate() {
        let ln = i + 1;

        let line_clean = line.trim_end_matches('\r');

        let logical = line_clean.trim();

        if logical.is_empty() {
            entries.push(raw_entry(ln, line_clean));
            continue;
        }

        if logical.starts_with('[') && logical.ends_with(']') {
            entries.push(raw_entry(ln, line_clean));
            continue;
        }

        if let Some(caps) = dialog_re.captures(line_clean) {
            let speaker = caps
                .name("speaker")
                .map(|m| m.as_str().to_string())
                .unwrap_or_default();

            let text_m = caps.name("text").unwrap();
            let text = text_m.as_str().to_string();

            let start = text_m.start();
            let end = text_m.end();

            entries.push(CoreEntry {
                entry_id: format!("{}-text", ln),
                original: text,
                translation: String::new(),
                status: EntryStatus::Untranslated,
                is_translatable: true,
                line_number: ln,
                raw_line: None,
                prefix: Some(line_clean[..start].to_string()),
                suffix: Some(line_clean[end..].to_string()),
                speaker: Some(speaker),
            });

            continue;
        }

        let original = logical.to_string();

        let start = match line_clean.find(&original) {
            Some(pos) => pos,
            None => {
                entries.push(raw_entry(ln, line_clean));
                continue;
            }
        };
        let end = start + original.len();

        entries.push(CoreEntry {
            entry_id: format!("{}-text", ln),
            original,
            translation: String::new(),
            status: EntryStatus::Untranslated,
            is_translatable: true,
            line_number: ln,
            raw_line: None,
            prefix: Some(line_clean[..start].to_string()),
            suffix: Some(line_clean[end..].to_string()),
            speaker: None,
        });
    }

    entries
}

fn raw_entry(line_number: usize, line: &str) -> CoreEntry {
    CoreEntry {
        entry_id: format!("{}-raw", line_number),
        original: String::new(),
        translation: String::new(),
        status: EntryStatus::Untranslated,
        is_translatable: false,
        line_number,
        raw_line: Some(line.to_string()),
        prefix: None,
        suffix: None,
        speaker: None,
    }
}
