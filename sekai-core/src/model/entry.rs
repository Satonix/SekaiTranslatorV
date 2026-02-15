use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CoreEntry {
    pub entry_id: String,

    #[serde(default)]
    pub original: String,

    #[serde(default)]
    pub translation: String,

    #[serde(default)]
    pub status: EntryStatus,

    #[serde(default)]
    pub is_translatable: bool,

    #[serde(default)]
    pub line_number: usize,

    #[serde(default)]
    pub raw_line: Option<String>,

    #[serde(default)]
    pub prefix: Option<String>,

    #[serde(default)]
    pub suffix: Option<String>,

    #[serde(default)]
    pub speaker: Option<String>,
}

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
