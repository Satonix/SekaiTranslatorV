use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq)]
pub struct TMEntry {
    pub source_lang: String,
    pub target_lang: String,

    pub original: String,
    pub translation: String,

    pub normalized: String,

    pub hash: String,
}
