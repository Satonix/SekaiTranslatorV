use crate::model::entry::{CoreEntry, EntryStatus};
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct QaIssue {
    pub entry_id: String,
    pub code: String,
    pub message: String,
}

pub fn run(entries: &[CoreEntry]) -> Vec<QaIssue> {
    let mut issues: Vec<QaIssue> = Vec::new();

    for e in entries {
        // QA só faz sentido para linhas traduzíveis
        if !e.is_translatable {
            continue;
        }

        let original_trim = e.original.trim();
        let translation_trim = e.translation.trim();

        // Tradução idêntica ao original (normalizando trim)
        if !translation_trim.is_empty() && translation_trim == original_trim {
            issues.push(QaIssue {
                entry_id: e.entry_id.clone(),
                code: "SAME_AS_ORIGINAL".to_string(),
                message: "Tradução é idêntica ao texto original".to_string(),
            });
        }

        // Contexto ausente (edge-case real: entrada traduzível
        // sem prefix/suffix - pode quebrar rebuild para engines
        // que dependem do wrapper)
        if e.prefix.is_none() && e.suffix.is_none() {
            issues.push(QaIssue {
                entry_id: e.entry_id.clone(),
                code: "MISSING_CONTEXT".to_string(),
                message: "Linha traduzível sem prefix/suffix".to_string(),
            });
        }

        // Speaker definido mas texto vazio (ou whitespace)
        if e.speaker.is_some() && original_trim.is_empty() {
            issues.push(QaIssue {
                entry_id: e.entry_id.clone(),
                code: "SPEAKER_WITHOUT_TEXT".to_string(),
                message: "Speaker definido mas texto original vazio".to_string(),
            });
        }

        // Inconsistências de status
        match e.status {
            EntryStatus::Translated | EntryStatus::Reviewed => {
                if translation_trim.is_empty() {
                    issues.push(QaIssue {
                        entry_id: e.entry_id.clone(),
                        code: "STATUS_TRANSLATED_BUT_EMPTY".to_string(),
                        message: "Status indica traduzido, mas tradução está vazia".to_string(),
                    });
                }
            }
            EntryStatus::InProgress => {
                if translation_trim.is_empty() {
                    issues.push(QaIssue {
                        entry_id: e.entry_id.clone(),
                        code: "STATUS_IN_PROGRESS_BUT_EMPTY".to_string(),
                        message: "Status IN_PROGRESS, mas tradução está vazia".to_string(),
                    });
                }
            }
            EntryStatus::Untranslated => {
                // opcional: se quiser marcar "untranslated mas tem texto", útil para debugging
                // if !translation_trim.is_empty() {
                //     issues.push(QaIssue {
                //         entry_id: e.entry_id.clone(),
                //         code: "STATUS_UNTRANSLATED_BUT_HAS_TEXT".to_string(),
                //         message: "Status UNTRANSLATED, mas há texto na tradução".to_string(),
                //     });
                // }
            }
        }
    }

    issues
}
