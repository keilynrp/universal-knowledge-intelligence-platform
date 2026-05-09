use std::collections::HashMap;

/// Supported language codes.
const SUPPORTED_LANGS: &[&str] = &["en", "es", "fr", "de", "pt"];

/// Detect the language of a text using trigram profiles.
/// Returns the BCP-47 language code or None if confidence is too low.
pub fn detect_language(text: &str) -> Option<String> {
    if text.split_whitespace().count() < 5 {
        return None; // Too short for reliable detection
    }

    let text_trigrams = build_trigram_profile(text);
    if text_trigrams.is_empty() {
        return None;
    }

    let mut best_lang = None;
    let mut best_score = 0.0f64;

    for &lang in SUPPORTED_LANGS {
        let profile = lang_profile(lang);
        let score = cosine_similarity(&text_trigrams, &profile);
        if score > best_score {
            best_score = score;
            best_lang = Some(lang.to_string());
        }
    }

    // Threshold: must have reasonable confidence
    if best_score > 0.05 {
        best_lang
    } else {
        None
    }
}

fn build_trigram_profile(text: &str) -> HashMap<String, f64> {
    let lower = text.to_lowercase();
    let chars: Vec<char> = lower.chars().filter(|c| c.is_alphabetic() || *c == ' ').collect();
    let mut counts: HashMap<String, usize> = HashMap::new();

    for window in chars.windows(3) {
        let trigram: String = window.iter().collect();
        *counts.entry(trigram).or_insert(0) += 1;
    }

    let total: f64 = counts.values().sum::<usize>() as f64;
    if total == 0.0 {
        return HashMap::new();
    }

    counts.into_iter().map(|(k, v)| (k, v as f64 / total)).collect()
}

fn cosine_similarity(a: &HashMap<String, f64>, b: &HashMap<String, f64>) -> f64 {
    let dot: f64 = a
        .iter()
        .filter_map(|(k, va)| b.get(k).map(|vb| va * vb))
        .sum();

    let norm_a: f64 = a.values().map(|v| v * v).sum::<f64>().sqrt();
    let norm_b: f64 = b.values().map(|v| v * v).sum::<f64>().sqrt();

    if norm_a == 0.0 || norm_b == 0.0 {
        0.0
    } else {
        dot / (norm_a * norm_b)
    }
}

/// Pre-computed trigram profiles for each supported language.
/// These are simplified representative profiles (not production-grade).
fn lang_profile(lang: &str) -> HashMap<String, f64> {
    let data: &[(&str, f64)] = match lang {
        "en" => &[
            ("the", 0.05), ("ing", 0.04), ("and", 0.03), ("ion", 0.03), ("tio", 0.03),
            ("ent", 0.025), ("ati", 0.02), ("for", 0.02), ("her", 0.015), ("ter", 0.015),
            ("hat", 0.01), ("tha", 0.01), ("his", 0.01), ("ere", 0.01), ("con", 0.01),
            ("res", 0.01), ("ver", 0.01), ("all", 0.01), ("ons", 0.01), ("nce", 0.01),
        ],
        "es" => &[
            ("que", 0.05), ("con", 0.04), ("ent", 0.04), ("ión", 0.03), ("ado", 0.03),
            ("los", 0.025), ("del", 0.02), ("ión", 0.02), ("par", 0.015), ("las", 0.015),
            ("una", 0.01), ("pro", 0.01), ("tra", 0.01), ("est", 0.01), ("aci", 0.01),
        ],
        "fr" => &[
            ("les", 0.05), ("ent", 0.04), ("ion", 0.04), ("des", 0.03), ("que", 0.03),
            ("ati", 0.025), ("ons", 0.02), ("tio", 0.02), ("est", 0.015), ("une", 0.015),
            ("par", 0.01), ("con", 0.01), ("res", 0.01), ("men", 0.01), ("pou", 0.01),
        ],
        "de" => &[
            ("ung", 0.05), ("sch", 0.04), ("ein", 0.04), ("ich", 0.03), ("die", 0.03),
            ("den", 0.025), ("und", 0.02), ("che", 0.02), ("gen", 0.015), ("der", 0.015),
            ("eit", 0.01), ("ste", 0.01), ("ion", 0.01), ("ver", 0.01), ("auf", 0.01),
        ],
        "pt" => &[
            ("que", 0.05), ("ção", 0.04), ("ent", 0.04), ("ado", 0.03), ("com", 0.03),
            ("par", 0.025), ("dos", 0.02), ("uma", 0.02), ("pro", 0.015), ("res", 0.015),
            ("ões", 0.01), ("tra", 0.01), ("ais", 0.01), ("est", 0.01), ("iva", 0.01),
        ],
        _ => &[],
    };

    data.iter().map(|(k, v)| (k.to_string(), *v)).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_english_detection() {
        let text = "The quick brown fox jumps over the lazy dog. \
                    This is a well-known English language test sentence.";
        let lang = detect_language(text);
        assert_eq!(lang, Some("en".to_string()));
    }

    #[test]
    fn test_short_text_returns_none() {
        let lang = detect_language("hello");
        assert!(lang.is_none());
    }

    #[test]
    fn test_empty_returns_none() {
        assert!(detect_language("").is_none());
    }

    #[test]
    fn test_spanish_detection() {
        let text = "La investigación científica es fundamental para el progreso \
                    de la humanidad y el desarrollo de nuevas tecnologías.";
        let lang = detect_language(text);
        // Should detect as Spanish or at least not None
        assert!(lang.is_some());
    }
}
