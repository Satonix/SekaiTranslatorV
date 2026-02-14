use std::fs;
use std::path::Path;

use chardetng::EncodingDetector;
use encoding_rs::Encoding;
use serde::Serialize;

#[derive(Debug, Serialize)]
pub struct EncodingCandidate {
    pub name: String,
    pub confidence: f32,
}

#[derive(Debug, Serialize)]
pub struct EncodingDetectionResult {
    pub best: String,
    pub confidence: f32,
    pub candidates: Vec<EncodingCandidate>,
}

pub fn detect_from_file(path: &Path) -> Result<EncodingDetectionResult, String> {
    let bytes = fs::read(path).map_err(|e| e.to_string())?;

    // BOM UTF-8 (EF BB BF)
    if bytes.starts_with(&[0xEF, 0xBB, 0xBF]) {
        return Ok(EncodingDetectionResult {
            best: "utf-8-sig".into(),
            confidence: 0.99,
            candidates: vec![
                EncodingCandidate {
                    name: "utf-8-sig".into(),
                    confidence: 0.99,
                },
                EncodingCandidate {
                    name: "utf-8".into(),
                    confidence: 0.90,
                },
            ],
        });
    }

    let mut detector = EncodingDetector::new();
    detector.feed(&bytes, true);

    let encoding = detector.guess(None, true);
    let best = encoding.name().to_lowercase();
    let confidence = estimate_confidence(&bytes, encoding);

    let mut candidates = Vec::new();
    candidates.push(EncodingCandidate {
        name: best.clone(),
        confidence,
    });

    // Ambiguidades comuns em VN
    if best == "shift_jis" {
        candidates.push(EncodingCandidate {
            name: "windows-31j".into(),
            confidence: (confidence - 0.03).max(0.0),
        });
        candidates.push(EncodingCandidate {
            name: "cp932".into(),
            confidence: (confidence - 0.05).max(0.0),
        });
    } else if best == "windows-31j" {
        candidates.push(EncodingCandidate {
            name: "cp932".into(),
            confidence: (confidence - 0.02).max(0.0),
        });
        candidates.push(EncodingCandidate {
            name: "shift_jis".into(),
            confidence: (confidence - 0.05).max(0.0),
        });
    }

    if best == "utf-8" {
        candidates.push(EncodingCandidate {
            name: "utf-8-sig".into(),
            confidence: (confidence - 0.20).max(0.0),
        });
    }

    Ok(EncodingDetectionResult {
        best,
        confidence,
        candidates,
    })
}

fn estimate_confidence(bytes: &[u8], encoding: &'static Encoding) -> f32 {
    let (text, _, had_errors) = encoding.decode(bytes);

    if had_errors {
        return 0.35;
    }

    let len = text.len();
    if len < 64 {
        0.55
    } else if len < 512 {
        0.70
    } else if len < 4096 {
        0.82
    } else {
        0.90
    }
}
