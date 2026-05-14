use unicode_normalization::UnicodeNormalization;

/// NFD decompose then drop all combining (diacritic) characters.
/// García → Garcia
pub fn strip_diacritics(text: &str) -> String {
    text.nfd()
        .filter(|c| !unicode_normalization::char::is_combining_mark(*c))
        .collect()
}

/// Canonical form for fuzzy comparison:
/// - strip diacritics
/// - lowercase
/// - collapse non-alphanumeric to single spaces
pub fn normalize_name(name: &str) -> String {
    let s = strip_diacritics(name);
    let s: String = s
        .chars()
        .map(|c| if c.is_alphanumeric() || c.is_whitespace() { c } else { ' ' })
        .collect();
    // Collapse whitespace
    s.split_whitespace().collect::<Vec<_>>().join(" ").to_lowercase()
}

/// Convert cataloguing-inverted format 'Surname, Firstname [Middle]'
/// to natural order 'Firstname [Middle] Surname'.
pub fn reformat_surname_first(name: &str) -> String {
    if let Some(comma_pos) = name.find(',') {
        let surname = name[..comma_pos].trim();
        let given = name[comma_pos + 1..].trim();
        format!("{} {}", given, surname)
    } else {
        name.to_string()
    }
}

/// Generate all normalised name variants for maximum recall.
pub fn name_variants(name: &str) -> Vec<String> {
    let mut variants = vec![normalize_name(name)];
    let reformatted = reformat_surname_first(name);
    if reformatted != name {
        let v = normalize_name(&reformatted);
        if !variants.contains(&v) {
            variants.push(v);
        }
    }

    // Initials-only variant: "John Smith" → "j smith"
    let norm = normalize_name(name);
    let tokens: Vec<&str> = norm.split_whitespace().collect();
    if tokens.len() >= 2 {
        let initials_first: String = tokens
            .iter()
            .enumerate()
            .map(|(i, t)| {
                if i < tokens.len() - 1 {
                    t.chars().next().map(|c| c.to_string()).unwrap_or_default()
                } else {
                    t.to_string()
                }
            })
            .collect::<Vec<_>>()
            .join(" ");
        if !variants.contains(&initials_first) {
            variants.push(initials_first);
        }
    }

    variants
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_strip_diacritics() {
        assert_eq!(strip_diacritics("García"), "Garcia");
        assert_eq!(strip_diacritics("Müller"), "Muller");
        assert_eq!(strip_diacritics("Šťěpán"), "Stepan");
    }

    #[test]
    fn test_normalize_name() {
        assert_eq!(normalize_name("García, José"), "garcia jose");
        assert_eq!(normalize_name("  John   Doe  "), "john doe");
        assert_eq!(normalize_name("O'Brien"), "o brien");
    }

    #[test]
    fn test_reformat_surname_first() {
        assert_eq!(reformat_surname_first("Smith, John"), "John Smith");
        assert_eq!(reformat_surname_first("John Smith"), "John Smith");
        assert_eq!(
            reformat_surname_first("García, José María"),
            "José María García"
        );
    }

    #[test]
    fn test_name_variants() {
        let variants = name_variants("Smith, John");
        assert!(variants.contains(&"smith john".to_string()));
        assert!(variants.contains(&"john smith".to_string()));
    }

    #[test]
    fn test_name_variants_initials() {
        let variants = name_variants("John Smith");
        assert!(variants.contains(&"john smith".to_string()));
        assert!(variants.contains(&"j smith".to_string()));
    }

    #[test]
    fn test_strip_diacritics_no_change() {
        assert_eq!(strip_diacritics("John Smith"), "John Smith");
    }

    #[test]
    fn test_strip_diacritics_mixed() {
        assert_eq!(strip_diacritics("José García-López"), "Jose Garcia-Lopez");
    }

    #[test]
    fn test_normalize_name_punctuation() {
        assert_eq!(normalize_name("Dr. John-Paul Smith Jr."), "dr john paul smith jr");
    }

    #[test]
    fn test_normalize_name_empty() {
        assert_eq!(normalize_name(""), "");
    }

    #[test]
    fn test_reformat_surname_first_no_comma() {
        assert_eq!(reformat_surname_first("Alice Jones"), "Alice Jones");
    }

    #[test]
    fn test_reformat_surname_first_multiple_commas() {
        // Only splits on first comma
        assert_eq!(reformat_surname_first("Smith, John, Jr"), "John, Jr Smith");
    }

    #[test]
    fn test_name_variants_single_name() {
        let variants = name_variants("Madonna");
        assert!(variants.contains(&"madonna".to_string()));
        // No initials variant for single token
        assert_eq!(variants.len(), 1);
    }

    #[test]
    fn test_name_variants_three_parts() {
        let variants = name_variants("John Michael Smith");
        assert!(variants.contains(&"john michael smith".to_string()));
        assert!(variants.contains(&"j m smith".to_string()));
    }

    #[test]
    fn test_name_variants_with_diacritics() {
        let variants = name_variants("García, José María");
        assert!(variants.contains(&"garcia jose maria".to_string()));
        assert!(variants.contains(&"jose maria garcia".to_string()));
    }
}
