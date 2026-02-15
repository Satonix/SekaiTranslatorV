use crate::model::entry::CoreEntry;

pub fn rebuild(entries: &[CoreEntry]) -> String {
    let mut out: Vec<String> = Vec::with_capacity(entries.len());

    for e in entries {
        if !e.is_translatable {
            out.push(e.raw_line.clone().unwrap_or_default());
            continue;
        }

        let translation_trimmed_empty = e.translation.trim().is_empty();
        let text = if !translation_trimmed_empty {
            e.translation.as_str()
        } else {
            e.original.as_str()
        };

        let line = format!(
            "{}{}{}",
            e.prefix.as_deref().unwrap_or(""),
            text,
            e.suffix.as_deref().unwrap_or("")
        );

        out.push(line);
    }

    out.join("\n")
}
