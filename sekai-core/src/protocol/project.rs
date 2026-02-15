use serde_json::{json, Value};

use crate::model::project::ProjectInfo;
use crate::services::project as service;

pub fn handle(cmd: &str, payload: &Value) -> Option<Value> {
    match cmd {
        "project.list" => {
            let projects = service::list_projects();
            Some(json!({
                "projects": projects
            }))
        }

        "project.create" => {
            let name = payload["name"].as_str().unwrap_or("").to_string();
            let game_root = payload["game_root"].as_str().unwrap_or("").to_string();
            let encoding = payload["encoding"].as_str().unwrap_or("utf-8").to_string();
            let engine = payload["engine"].as_str().unwrap_or("").to_string();
            let source_language = payload["source_language"].as_str().unwrap_or("").to_string();
            let target_language = payload["target_language"].as_str().unwrap_or("").to_string();

            match service::create_project(
                name,
                game_root,
                encoding,
                engine,
                source_language,
                target_language,
            ) {
                Ok(project) => Some(json!({
                    "project_path": project.project_path
                })),
                Err(e) => Some(json!({
                    "__error": e
                })),
            }
        }

        "project.open" => {
            let path = payload["project_path"].as_str().unwrap_or("").to_string();

            match service::open_project(path) {
                Ok(project) => Some(json!({
                    "project": project
                })),
                Err(e) => Some(json!({
                    "__error": e
                })),
            }
        }

        "project.save" => {
            let project_val = payload.get("project").cloned().unwrap_or(Value::Null);
            if project_val.is_null() {
                return Some(json!({ "__error": "payload.project is required" }));
            }

            let project: ProjectInfo = match serde_json::from_value(project_val) {
                Ok(p) => p,
                Err(e) => {
                    return Some(json!({
                        "__error": format!("invalid payload.project: {e}")
                    }))
                }
            };

            match service::save_project(project) {
                Ok(saved) => Some(json!({
                    "project": saved
                })),
                Err(e) => Some(json!({
                    "__error": e
                })),
            }
        }

        _ => None,
    }
}
