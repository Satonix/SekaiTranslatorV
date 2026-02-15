use serde::{Deserialize, Serialize};

fn default_ai_prompt_preset() -> String {
    "default".to_string()
}

#[derive(Debug, Serialize, Deserialize, Clone, Default)]
pub struct ProjectInfo {
    #[serde(default)]
    pub name: String,

    #[serde(default)]
    pub project_path: String,

    #[serde(default, alias = "game_root")]
    pub root_path: String,

    #[serde(default)]
    pub engine: String,

    #[serde(default)]
    pub encoding: String,

    #[serde(default)]
    pub parser_id: String,

    #[serde(default, alias = "source_lang")]
    pub source_language: String,

    #[serde(default, alias = "target_lang")]
    pub target_language: String,


    #[serde(default = "default_ai_prompt_preset")]
    pub ai_prompt_preset: String,

    #[serde(default)]
    pub ai_custom_prompt_text: String,
}
