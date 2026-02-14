use crate::model::entry::{CoreEntry, EntryStatus};
use crate::services::ai_types::{AiItemResult, AiRunReport};

use rand::{thread_rng, Rng};
use reqwest::blocking::Client;
use reqwest::StatusCode;
use serde_json::json;

use std::{thread, time::Duration};

pub struct AiConfig<'a> {
    pub provider: &'a str,
    pub api_key: &'a str,
    pub model: &'a str,
    pub source_lang: &'a str,
    pub target_lang: &'a str,
}

const MAX_RETRIES: usize = 3;
const BASE_DELAY_MS: u64 = 800;
const TIMEOUT_SECS: u64 = 60;
const BATCH_SIZE: usize = 5;

fn backoff(attempt: usize) -> Duration {
    let jitter: u64 = thread_rng().gen_range(0..200);
    let ms = BASE_DELAY_MS * (2_u64.pow(attempt as u32)) + jitter;
    Duration::from_millis(ms)
}

fn endpoint_for(provider: &str) -> Result<&'static str, String> {
    match provider {
        // Nota: /v1/chat/completions ainda é válido; você pode migrar depois.
        "openai" => Ok("https://api.openai.com/v1/chat/completions"),
        "deepseek" => Ok("https://api.deepseek.com/v1/chat/completions"),
        _ => Err("Unsupported provider".into()),
    }
}

pub fn translate_entries(entries: &mut [CoreEntry], cfg: AiConfig) -> Result<AiRunReport, String> {
    let client = Client::builder()
        .timeout(Duration::from_secs(TIMEOUT_SECS))
        .build()
        .map_err(|e| e.to_string())?;

    let endpoint = endpoint_for(cfg.provider)?;

    let mut report = AiRunReport {
        succeeded: 0,
        failed: 0,
        items: Vec::new(),
    };

    // Coletar índices traduzíveis
    let translatable_indices: Vec<usize> = entries
        .iter()
        .enumerate()
        .filter_map(|(i, e)| if e.is_translatable { Some(i) } else { None })
        .collect();

    // Processar em batches
    let mut batch: Vec<usize> = Vec::with_capacity(BATCH_SIZE);

    for idx in translatable_indices {
        batch.push(idx);

        if batch.len() == BATCH_SIZE {
            process_batch(&client, endpoint, entries, &batch, &cfg, &mut report);
            batch.clear();
        }
    }

    if !batch.is_empty() {
        process_batch(&client, endpoint, entries, &batch, &cfg, &mut report);
    }

    Ok(report)
}

fn process_batch(
    client: &Client,
    endpoint: &str,
    entries: &mut [CoreEntry],
    batch_idx: &[usize],
    cfg: &AiConfig,
    report: &mut AiRunReport,
) {
    for &i in batch_idx {
        let e = &mut entries[i];

        // Dá para pular itens já traduzidos:
        // if !e.translation.trim().is_empty() { continue; }

        let prompt = build_prompt(e, cfg);

        let body = json!({
            "model": cfg.model,
            "messages": [
                { "role": "system", "content": "You are a professional visual novel translator." },
                { "role": "user", "content": prompt }
            ],
            "temperature": 0.3
        });

        let mut ok = false;
        let mut last_err: Option<String> = None;

        for attempt in 0..MAX_RETRIES {
            let res = client
                .post(endpoint)
                .bearer_auth(cfg.api_key)
                .json(&body)
                .send();

            match res {
                Ok(resp) => {
                    let status = resp.status();

                    // Lê como texto primeiro: isso evita perder mensagem de erro quando JSON falha
                    let text = match resp.text() {
                        Ok(t) => t,
                        Err(err) => {
                            last_err = Some(err.to_string());
                            thread::sleep(backoff(attempt));
                            continue;
                        }
                    };

                    if !status.is_success() {
                        // Erro HTTP: tenta extrair mensagem do JSON, senão guarda o corpo bruto
                        last_err = Some(extract_error_message(status, &text));
                        if should_retry_http(status) && attempt + 1 < MAX_RETRIES {
                            thread::sleep(backoff(attempt));
                            continue;
                        } else {
                            break;
                        }
                    }

                    let v: Result<serde_json::Value, _> = serde_json::from_str(&text);
                    match v {
                        Ok(json) => {
                            if let Some(t) = json
                                .get("choices")
                                .and_then(|c| c.get(0))
                                .and_then(|c| c.get("message"))
                                .and_then(|m| m.get("content"))
                                .and_then(|c| c.as_str())
                            {
                                e.translation = t.trim().to_string();
                                e.status = EntryStatus::Translated;

                                report.succeeded += 1;
                                report.items.push(AiItemResult {
                                    entry_id: e.entry_id.clone(),
                                    ok: true,
                                    error: None,
                                });

                                ok = true;
                                break;
                            } else {
                                last_err = Some(
                                    "Invalid AI response: missing choices[0].message.content"
                                        .into(),
                                );
                                if attempt + 1 < MAX_RETRIES {
                                    thread::sleep(backoff(attempt));
                                    continue;
                                }
                            }
                        }
                        Err(_) => {
                            last_err = Some("Invalid JSON from AI".into());
                            if attempt + 1 < MAX_RETRIES {
                                thread::sleep(backoff(attempt));
                                continue;
                            }
                        }
                    }
                }
                Err(err) => {
                    last_err = Some(err.to_string());
                    if attempt + 1 < MAX_RETRIES {
                        thread::sleep(backoff(attempt));
                        continue;
                    }
                }
            }
        }

        if !ok {
            report.failed += 1;
            report.items.push(AiItemResult {
                entry_id: e.entry_id.clone(),
                ok: false,
                error: last_err,
            });
        }
    }
}

fn should_retry_http(status: StatusCode) -> bool {
    // 408/429/5xx tipicamente são temporários
    status == StatusCode::REQUEST_TIMEOUT
        || status == StatusCode::TOO_MANY_REQUESTS
        || status.is_server_error()
}

fn extract_error_message(status: StatusCode, body_text: &str) -> String {
    // Tenta padrão comum: { "error": { "message": "..." } } ou { "message": "..." }
    if let Ok(v) = serde_json::from_str::<serde_json::Value>(body_text) {
        if let Some(msg) = v
            .get("error")
            .and_then(|e| e.get("message"))
            .and_then(|m| m.as_str())
        {
            return format!("HTTP {}: {}", status.as_u16(), msg);
        }
        if let Some(msg) = v.get("message").and_then(|m| m.as_str()) {
            return format!("HTTP {}: {}", status.as_u16(), msg);
        }
    }

    // Fallback: corpo bruto (limitado)
    let trimmed = body_text.trim();
    let snippet = if trimmed.len() > 400 {
        format!("{}...", &trimmed[..400])
    } else {
        trimmed.to_string()
    };

    format!("HTTP {}: {}", status.as_u16(), snippet)
}

fn build_prompt(entry: &CoreEntry, cfg: &AiConfig) -> String {
    let mut p = String::new();

    p.push_str(&format!(
        "Translate from {} to {}.\n",
        cfg.source_lang, cfg.target_lang
    ));

    if let Some(speaker) = &entry.speaker {
        if !speaker.trim().is_empty() {
            p.push_str(&format!("Speaker: {}\n", speaker.trim()));
        }
    }

    p.push_str("Text:\n");
    p.push_str(entry.original.trim());

    p
}
