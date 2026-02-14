use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq)]
// #[serde(deny_unknown_fields)] // opcional: mais estrito
pub struct TMEntry {
    pub source_lang: String,
    pub target_lang: String,

    pub original: String,
    pub translation: String,

    // Normalização (C8.3 / canonical)
    pub normalized: String,

    // Hash do normalized (normalmente sha256 em hex)
    pub hash: String,
}
