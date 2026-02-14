use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CoreEntry {
    // ID estável da entry no arquivo/projeto.
    pub entry_id: String,

    // Texto
    #[serde(default)]
    pub original: String,

    #[serde(default)]
    pub translation: String,

    // Estado
    #[serde(default)]
    pub status: EntryStatus,

    // Contexto estrutural
    #[serde(default)]
    pub is_translatable: bool,

    #[serde(default)]
    pub line_number: usize,

    // Reconstrução
    #[serde(default)]
    pub raw_line: Option<String>,

    #[serde(default)]
    pub prefix: Option<String>,

    #[serde(default)]
    pub suffix: Option<String>,

    // VN
    #[serde(default)]
    pub speaker: Option<String>,
}

/// Status de tradução.
///
/// Importante: o front-end Python (sekai-ui) usa valores em *snake_case*
/// (ex.: "untranslated", "in_progress"). Para manter compatibilidade,
/// serializamos/deserializamos o enum com `rename_all = "snake_case"`.
#[derive(Debug, Serialize, Deserialize, Clone, Copy, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum EntryStatus {
    Untranslated,
    InProgress,
    Translated,
    Reviewed,
}

impl Default for EntryStatus {
    fn default() -> Self {
        EntryStatus::Untranslated
    }
}
