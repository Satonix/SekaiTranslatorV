#![windows_subsystem = "windows"]
use std::io::{self, BufRead, Write};

mod model;
mod parsers;
mod protocol;
mod services;

fn main() {
    let stdin = io::stdin();
    let mut stdout = io::stdout();

    for line in stdin.lock().lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => continue,
        };

        if line.trim().is_empty() {
            continue;
        }

        let result = std::panic::catch_unwind(|| protocol::handle(&line));

        let response = match result {
            Ok(resp) => resp,
            Err(_) => serde_json::json!({
                "status": "error",
                "message": "internal core error"
            })
            .to_string(),
        };

        if writeln!(stdout, "{response}").is_err() {
            break;
        }

        let _ = stdout.flush();
    }
}
