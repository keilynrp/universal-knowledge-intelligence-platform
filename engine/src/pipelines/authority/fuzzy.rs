use strsim::{jaro_winkler, normalized_levenshtein};

/// Jaro-Winkler similarity (0.0 to 1.0).
pub fn jaro_winkler_similarity(a: &str, b: &str) -> f64 {
    jaro_winkler(a, b)
}

/// Token-sort ratio: sort tokens alphabetically, then compute normalized
/// Levenshtein similarity. Equivalent to fuzzywuzzy's token_sort_ratio.
pub fn token_sort_ratio(a: &str, b: &str) -> f64 {
    let sort_tokens = |s: &str| -> String {
        let mut tokens: Vec<&str> = s.split_whitespace().collect();
        tokens.sort_unstable();
        tokens.join(" ")
    };

    let sa = sort_tokens(a);
    let sb = sort_tokens(b);

    if sa.is_empty() && sb.is_empty() {
        return 1.0;
    }

    normalized_levenshtein(&sa, &sb)
}

/// Token-set ratio: compare the intersection and remainder of token sets.
/// Returns 1.0 if all tokens from one string appear in the other.
pub fn token_set_ratio(a: &str, b: &str) -> f64 {
    let set_a: std::collections::HashSet<&str> = a.split_whitespace().collect();
    let set_b: std::collections::HashSet<&str> = b.split_whitespace().collect();

    if set_a.is_empty() && set_b.is_empty() {
        return 1.0;
    }

    let intersection: Vec<&&str> = set_a.intersection(&set_b).collect();
    let mut sorted_inter: Vec<&str> = intersection.iter().map(|s| **s).collect();
    sorted_inter.sort_unstable();
    let inter_str = sorted_inter.join(" ");

    let mut diff_a: Vec<&str> = set_a.difference(&set_b).copied().collect();
    diff_a.sort_unstable();
    let mut diff_b: Vec<&str> = set_b.difference(&set_a).copied().collect();
    diff_b.sort_unstable();

    let combined_a = if diff_a.is_empty() {
        inter_str.clone()
    } else {
        format!("{} {}", inter_str, diff_a.join(" "))
    };
    let combined_b = if diff_b.is_empty() {
        inter_str.clone()
    } else {
        format!("{} {}", inter_str, diff_b.join(" "))
    };

    let r1 = normalized_levenshtein(&inter_str, &combined_a);
    let r2 = normalized_levenshtein(&inter_str, &combined_b);
    let r3 = normalized_levenshtein(&combined_a, &combined_b);

    f64::max(r1, f64::max(r2, r3))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_jaro_winkler_identical() {
        assert!((jaro_winkler_similarity("john", "john") - 1.0).abs() < 0.001);
    }

    #[test]
    fn test_jaro_winkler_similar() {
        let score = jaro_winkler_similarity("john", "johm");
        assert!(score > 0.8, "score was {}", score);
    }

    #[test]
    fn test_token_sort_ratio_reorder() {
        let score = token_sort_ratio("john smith", "smith john");
        assert!((score - 1.0).abs() < 0.001, "score was {}", score);
    }

    #[test]
    fn test_token_sort_ratio_different() {
        let score = token_sort_ratio("john smith", "alice jones");
        assert!(score < 0.5);
    }

    #[test]
    fn test_token_sort_ratio_empty() {
        assert!((token_sort_ratio("", "") - 1.0).abs() < 0.001);
    }

    #[test]
    fn test_token_set_ratio_subset() {
        let score = token_set_ratio("john smith", "john michael smith");
        assert!(score > 0.8, "score was {}", score);
    }

    #[test]
    fn test_token_set_ratio_identical() {
        let score = token_set_ratio("john smith", "john smith");
        assert!((score - 1.0).abs() < 0.001);
    }

    #[test]
    fn test_jaro_winkler_completely_different() {
        let score = jaro_winkler_similarity("abcdef", "zyxwvu");
        assert!(score < 0.5, "score was {}", score);
    }

    #[test]
    fn test_jaro_winkler_empty_strings() {
        let score = jaro_winkler_similarity("", "");
        assert!((score - 1.0).abs() < 0.001);
    }

    #[test]
    fn test_jaro_winkler_one_empty() {
        let score = jaro_winkler_similarity("hello", "");
        assert!(score < 0.01, "score was {}", score);
    }

    #[test]
    fn test_token_sort_ratio_with_diacritics() {
        // After normalization, these would be compared as-is by fuzzy
        let score = token_sort_ratio("jose garcia", "garcia jose");
        assert!((score - 1.0).abs() < 0.001);
    }

    #[test]
    fn test_token_sort_ratio_single_token() {
        let score = token_sort_ratio("smith", "smith");
        assert!((score - 1.0).abs() < 0.001);
    }

    #[test]
    fn test_token_set_ratio_disjoint() {
        let score = token_set_ratio("alice jones", "bob smith");
        assert!(score < 0.5, "score was {}", score);
    }

    #[test]
    fn test_token_set_ratio_both_empty() {
        let score = token_set_ratio("", "");
        assert!((score - 1.0).abs() < 0.001);
    }

    #[test]
    fn test_token_sort_ratio_extra_whitespace() {
        let score = token_sort_ratio("  john   smith  ", "smith john");
        assert!((score - 1.0).abs() < 0.001, "score was {}", score);
    }
}
