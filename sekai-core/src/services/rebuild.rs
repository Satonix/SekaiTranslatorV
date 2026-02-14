use crate::model::entry::CoreEntry;

pub fn rebuild(entries: &[CoreEntry]) -> String {
    let mut out: Vec<String> = Vec::with_capacity(entries.len());

    for e in entries {
        // Entradas estruturais: deve preservar 1:1 o conteúdo original da linha
        if !e.is_translatable {
            // Se raw_line existir, preserva exatamente.
            // Se não existir (edge-case), ainda assim emite uma linha vazia
            // para não desalinhar o arquivo reconstruído.
            out.push(e.raw_line.clone().unwrap_or_default());
            continue;
        }

        // Texto translatável:
        // - Usa translation se tiver conteúdo "real"
        // - Caso contrário, volta pro original
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

    // Mantém LF como normalização interna.
    // Se você quiser preservar CRLF, isso deve ser decidido no lado do UI ao salvar em disco.
    out.join("\n")
}
