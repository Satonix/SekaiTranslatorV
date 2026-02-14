use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct AiItemResult {
    pub entry_id: String,
    pub ok: bool,
    pub error: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct AiRunReport {
    pub succeeded: usize,
    pub failed: usize,
    pub items: Vec<AiItemResult>,
}
