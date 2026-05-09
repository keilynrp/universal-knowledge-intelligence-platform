use std::collections::HashSet;
use std::sync::LazyLock;
use unicode_segmentation::UnicodeSegmentation;

static STOPWORDS: LazyLock<HashSet<&'static str>> = LazyLock::new(|| {
    include_str!("stopwords_en.txt")
        .lines()
        .map(|l| l.trim())
        .filter(|l| !l.is_empty())
        .collect()
});

/// Tokenize text: unicode word-split, lowercase, remove stopwords and short tokens.
pub fn tokenize(text: &str) -> Vec<String> {
    text.unicode_words()
        .map(|w| w.to_lowercase())
        .filter(|w| w.len() >= 3 && !STOPWORDS.contains(w.as_str()))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tokenize_basic() {
        let tokens = tokenize("Hello, world! This is a test.");
        assert!(tokens.contains(&"hello".to_string()));
        assert!(tokens.contains(&"world".to_string()));
        assert!(tokens.contains(&"test".to_string()));
    }

    #[test]
    fn test_stopwords_removed() {
        let tokens = tokenize("the cat is on the mat");
        assert!(!tokens.contains(&"the".to_string()));
        assert!(!tokens.contains(&"is".to_string()));
        assert!(!tokens.contains(&"on".to_string()));
        assert!(tokens.contains(&"cat".to_string()));
        assert!(tokens.contains(&"mat".to_string()));
    }

    #[test]
    fn test_unicode_handling() {
        let tokens = tokenize("über résumé naïve");
        // Non-ascii words should still be tokenized
        assert!(!tokens.is_empty());
    }

    #[test]
    fn test_empty_input() {
        assert!(tokenize("").is_empty());
        assert!(tokenize("   ").is_empty());
    }
}
