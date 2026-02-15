use serde_json::{json, Value};

use crate::model::entry::CoreEntry;
use crate::model::project::ProjectInfo;
use crate::parsers;
use crate::services::{ai, encoding, pipeline, project, qa, rebuild};

mod command;
use command::Command;

fn get_cmd(req: &Value) -> &str {
    req.get("cmd").and_then(|v| v.as_str()).unwrap_or("")
}

fn get_id(req: &Value) -> Value {
    req.get("id").cloned().unwrap_or(Value::Null)
}

fn get_payload<'a>(req: &'a Value) -> &'a Value {
    static EMPTY: Value = Value::Null;
    req.get("payload").unwrap_or(&EMPTY)
}

fn ok(id: Value, payload: Value) -> String {
    json!({
        "id": id,
        "status": "ok",
        "payload": payload
    })
    .to_string()
}

fn err(id: Value, message: impl Into<String>) -> String {
    json!({
        "id": id,
        "status": "error",
        "message": message.into()
    })
    .to_string()
}

fn parse_entries_from_payload(payload: &Value) -> Result<Vec<CoreEntry>, String> {
    let arr = payload
        .get("entries")
        .and_then(|v| v.as_array())
        .ok_or_else(|| "payload.entries must be an array".to_string())?;

    let mut entries: Vec<CoreEntry> = Vec::with_capacity(arr.len());

    for (i, v) in arr.iter().cloned().enumerate() {
        match serde_json::from_value::<CoreEntry>(v) {
            Ok(e) => entries.push(e),
            Err(e) => return Err(format!("invalid entry at index {}: {}", i, e)),
        }
    }

    Ok(entries)
}

pub fn handle(input: &str) -> String {
    let req: Value = match serde_json::from_str(input) {
        Ok(v) => v,
        Err(_) => {
            return json!({
                "status": "error",
                "message": "invalid json"
            })
            .to_string();
        }
    };

    let id = get_id(&req);
    let cmd_str = get_cmd(&req);
    let payload = get_payload(&req);

    let _cmd = Command::from(cmd_str);

    match cmd_str {
        "ping" => ok(id, json!({ "message": "sekai-core alive" })),

        "parse_text" => {
            let text = payload.get("text").and_then(|v| v.as_str()).unwrap_or("");
            let entries = parsers::kirikiri::parse(text);
            ok(id, json!({ "entries": entries }))
        }

        "rebuild_text" => {
            let entries = match parse_entries_from_payload(payload) {
                Ok(v) => v,
                Err(e) => return err(id, e),
            };
            let output = rebuild::rebuild(&entries);
            ok(id, json!({ "text": output }))
        }

        "run_qa" => {
            let entries = match parse_entries_from_payload(payload) {
                Ok(v) => v,
                Err(e) => return err(id, e),
            };
            let issues = qa::run(&entries);
            ok(id, json!({ "issues": issues }))
        }

        "encoding.detect" | "detect_encoding" => {
            let path_str = payload.get("path").and_then(|v| v.as_str()).unwrap_or("");
            if path_str.is_empty() {
                return err(id, "payload.path is required");
            }
            let path = std::path::PathBuf::from(path_str);
            match encoding::detect_from_file(&path) {
                Ok(result) => ok(id, serde_json::to_value(result).unwrap_or(json!({}))),
                Err(e) => err(id, e),
            }
        }

        "translate_entries" => {
            let provider = payload.get("provider").and_then(|v| v.as_str()).unwrap_or("");
            let api_key = payload.get("api_key").and_then(|v| v.as_str()).unwrap_or("");
            let model = payload.get("model").and_then(|v| v.as_str()).unwrap_or("");
            let source_lang = payload.get("source_lang").and_then(|v| v.as_str()).unwrap_or("ja");
            let target_lang = payload.get("target_lang").and_then(|v| v.as_str()).unwrap_or("pt-BR");

            if provider.is_empty() { return err(id, "payload.provider is required"); }
            if api_key.is_empty() { return err(id, "payload.api_key is required"); }
            if model.is_empty() { return err(id, "payload.model is required"); }

            let mut entries = match parse_entries_from_payload(payload) {
                Ok(v) => v,
                Err(e) => return err(id, e),
            };

            let cfg = ai::AiConfig { provider, api_key, model, source_lang, target_lang };
            match ai::translate_entries(&mut entries, cfg) {
                Ok(report) => ok(id, json!({ "entries": entries, "report": report })),
                Err(e) => err(id, e),
            }
        }

        "translate_with_tm" => {
            let provider = payload.get("provider").and_then(|v| v.as_str()).unwrap_or("");
            let api_key = payload.get("api_key").and_then(|v| v.as_str()).unwrap_or("");
            let model = payload.get("model").and_then(|v| v.as_str()).unwrap_or("");
            let source_lang = payload.get("source_lang").and_then(|v| v.as_str()).unwrap_or("ja");
            let target_lang = payload.get("target_lang").and_then(|v| v.as_str()).unwrap_or("pt-BR");

            if provider.is_empty() { return err(id, "payload.provider is required"); }
            if api_key.is_empty() { return err(id, "payload.api_key is required"); }
            if model.is_empty() { return err(id, "payload.model is required"); }

            let mut entries = match parse_entries_from_payload(payload) {
                Ok(v) => v,
                Err(e) => return err(id, e),
            };

            let cfg = pipeline::PipelineConfig { provider, api_key, model, source_lang, target_lang };
            match pipeline::run(&mut entries, cfg) {
                Ok(report) => ok(id, json!({ "entries": entries, "report": report })),
                Err(e) => err(id, e),
            }
        }

        "project.list" => ok(id, json!({ "projects": project::list_projects() })),

        "project.create" => {
            let name = payload.get("name").and_then(|v| v.as_str()).unwrap_or("").to_string();
            let game_root = payload.get("game_root").and_then(|v| v.as_str()).unwrap_or("").to_string();
            let encoding = payload.get("encoding").and_then(|v| v.as_str()).unwrap_or("utf-8").to_string();

            let engine = payload.get("engine").and_then(|v| v.as_str()).unwrap_or("").to_string();
            let parser_id = payload.get("parser_id").and_then(|v| v.as_str()).unwrap_or("").to_string();

            let source_language = payload.get("source_language").and_then(|v| v.as_str()).unwrap_or("").to_string();
            let target_language = payload.get("target_language").and_then(|v| v.as_str()).unwrap_or("").to_string();

            if name.is_empty() { return err(id, "payload.name is required"); }
            if game_root.is_empty() { return err(id, "payload.game_root is required"); }

            match project::create_project(
                name,
                game_root,
                encoding,
                engine,
                parser_id,
                source_language,
                target_language,
            ) {
                Ok(p) => ok(id, json!({ "project_path": p.project_path })),
                Err(e) => err(id, e),
            }
        }

        "project.open" => {
            let project_path = payload.get("project_path").and_then(|v| v.as_str()).unwrap_or("").to_string();
            if project_path.is_empty() { return err(id, "payload.project_path is required"); }

            match project::open_project(project_path) {
                Ok(p) => ok(id, json!({ "project": p })),
                Err(e) => err(id, e),
            }
        }

        "project.save" => {
            let project_val = payload.get("project").cloned().unwrap_or(Value::Null);
            if project_val.is_null() {
                return err(id, "payload.project is required");
            }

            let p: ProjectInfo = match serde_json::from_value(project_val) {
                Ok(v) => v,
                Err(e) => return err(id, format!("invalid payload.project: {e}")),
            };

            match project::save_project(p) {
                Ok(saved) => ok(id, json!({ "project": saved })),
                Err(e) => err(id, e),
            }
        }

        _ => err(id, "unknown command"),
    }
}
