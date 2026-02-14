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

    // Compat: se algum dia você salvar como "game_root" no JSON, ainda abre.
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

    // NOVO — Configurações de IA por projeto

    /// Preset de prompt:
    /// "default" | "literal" | "natural" | "custom"
    #[serde(default = "default_ai_prompt_preset")]
    pub ai_prompt_preset: String,

    /// Texto livre do prompt (usado apenas se preset == "custom")
    #[serde(default)]
    pub ai_custom_prompt_text: String,
}
