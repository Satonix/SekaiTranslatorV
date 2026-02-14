#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Command {
    Ping,
    ParseText,
    RebuildText,
    RunQa,
    DetectEncoding,
    TranslateEntries,
    TranslateWithTm,
    ProjectList,
    ProjectCreate,
    ProjectOpen,
    ProjectSave, // <- NOVO
    Unknown,
}

impl From<&str> for Command {
    fn from(s: &str) -> Self {
        match s {
            "ping" => Command::Ping,
            "parse_text" => Command::ParseText,
            "rebuild_text" => Command::RebuildText,
            "run_qa" => Command::RunQa,
            "detect_encoding" => Command::DetectEncoding,
            "translate_entries" => Command::TranslateEntries,
            "translate_with_tm" => Command::TranslateWithTm,
            "project.list" => Command::ProjectList,
            "project.create" => Command::ProjectCreate,
            "project.open" => Command::ProjectOpen,
            "project.save" => Command::ProjectSave, // <- NOVO
            _ => Command::Unknown,
        }
    }
}
