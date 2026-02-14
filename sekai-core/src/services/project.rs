use std::fs;
use std::path::{Path, PathBuf};

use crate::model::project::ProjectInfo;

fn projects_base_dir() -> PathBuf {
    if let Ok(local) = std::env::var("LOCALAPPDATA") {
        return PathBuf::from(local).join("SekaiTranslator").join("Projects");
    }
    std::env::current_dir()
        .unwrap_or_else(|_| PathBuf::from("."))
        .join("Projects")
}

fn ensure_projects_dir() -> PathBuf {
    let dir = projects_base_dir();
    if !dir.exists() {
        fs::create_dir_all(&dir).expect("failed to create projects dir");
    }
    dir
}

/// Converte o "name" (que pode vir zoado como path) em nome seguro de diretório.
/// - Se parecer um caminho, usa apenas o basename (file_name)
/// - Se vier "path já sanitizado" (ex.: C__Users_..._Projects_ATRI), tenta extrair só o sufixo
/// - Remove caracteres inválidos comuns no Windows (incluindo ':')
fn safe_project_dir_name(name: &str) -> String {
    let mut n = name.trim().to_string();

    // Se vier path (ex.: C:\...\ATRI), pega só o final.
    if n.contains('\\') || n.contains('/') {
        if let Some(bn) = Path::new(&n).file_name().and_then(|s| s.to_str()) {
            n = bn.to_string();
        }
    }

    // Se vier path JÁ sanitizado (ex.: C__Users_..._SekaiTranslator_Projects_ATRI),
    // tenta extrair o sufixo após o último "_Projects_" (ou variação em minúsculas).
    if let Some(pos) = n.rfind("_Projects_") {
        n = n[(pos + "_Projects_".len())..].to_string();
    } else if let Some(pos) = n.rfind("_projects_") {
        n = n[(pos + "_projects_".len())..].to_string();
    }

    // Sanitiza agressivamente: mantém letras/números/espacos/_-.
    let mut out = String::with_capacity(n.len());
    for ch in n.chars() {
        let ok = ch.is_ascii_alphanumeric() || ch == ' ' || ch == '_' || ch == '-' || ch == '.';
        out.push(if ok { ch } else { '_' });
    }

    let out = out.trim().trim_matches('.').to_string();
    if out.is_empty() {
        "Project".to_string()
    } else {
        out
    }
}

pub fn list_projects() -> Vec<ProjectInfo> {
    let dir = ensure_projects_dir();
    let mut projects = Vec::new();

    if let Ok(entries) = fs::read_dir(dir) {
        for entry in entries.flatten() {
            let path = entry.path().join("project.json");
            if path.exists() {
                if let Ok(data) = fs::read_to_string(&path) {
                    if let Ok(project) = serde_json::from_str::<ProjectInfo>(&data) {
                        projects.push(project);
                    }
                }
            }
        }
    }

    projects
}

pub fn create_project(
    name: String,
    game_root: String,
    encoding: String,
    engine: String, // legado (pode ficar vazio)
    parser_id: String,
    source_language: String,
    target_language: String,
) -> Result<ProjectInfo, String> {
    let base = ensure_projects_dir();

    let safe_name = safe_project_dir_name(&name);
    let project_dir = base.join(&safe_name);

    if project_dir.exists() {
        return Err("project already exists".into());
    }

    fs::create_dir_all(&project_dir).map_err(|_| "failed to create project directory")?;

    let project = ProjectInfo {
        name, // mantém o "nome de exibição" como veio
        project_path: project_dir.to_string_lossy().to_string(),
        root_path: game_root,
        engine,
        encoding,

        parser_id,

        source_language,
        target_language,

        // defaults IA (para a aba IA funcionar em projetos novos)
        ai_prompt_preset: "default".to_string(),
        ai_custom_prompt_text: String::new(),
    };

    let json = serde_json::to_string_pretty(&project).map_err(|_| "failed to serialize project")?;

    fs::write(project_dir.join("project.json"), json).map_err(|_| "failed to write project.json")?;

    Ok(project)
}

pub fn open_project(project_path: String) -> Result<ProjectInfo, String> {
    let path = Path::new(&project_path).join("project.json");

    if !path.exists() {
        return Err("project.json not found".into());
    }

    let data = fs::read_to_string(path).map_err(|_| "failed to read project.json")?;

    serde_json::from_str::<ProjectInfo>(&data).map_err(|_| "invalid project.json".into())
}

pub fn save_project(mut project: ProjectInfo) -> Result<ProjectInfo, String> {
    let base = ensure_projects_dir();

    let project_dir: PathBuf = {
        let pp = project.project_path.trim().to_string();
        if pp.is_empty() {
            let safe_name = safe_project_dir_name(&project.name);
            base.join(&safe_name)
        } else {
            PathBuf::from(pp)
        }
    };

    fs::create_dir_all(&project_dir).map_err(|e| format!("failed to create project directory: {e}"))?;

    project.project_path = project_dir.to_string_lossy().to_string();

    // se vier vazio, garante um default válido
    if project.ai_prompt_preset.trim().is_empty() {
        project.ai_prompt_preset = "default".to_string();
    }

    // parser_id pode ficar vazio (autodetect no UI) — não força nada aqui

    let json = serde_json::to_string_pretty(&project).map_err(|e| format!("failed to serialize project: {e}"))?;

    fs::write(project_dir.join("project.json"), json)
        .map_err(|e| format!("failed to write project.json: {e}"))?;

    Ok(project)
}
