pub fn normalize(text: &str) -> String {
    let mut s = text.trim().to_lowercase();

    s = s.split_whitespace().collect::<Vec<_>>().join(" ");

    for ch in ['“', '”', '’', '‘', '…', '"', '\'', '(', ')'] {
        s = s.replace(ch, "");
    }

    s
}
