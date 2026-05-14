//! Topic extraction: concept frequency counting from comma-separated concept strings.

use std::collections::HashMap;

/// Parse a comma/semicolon/pipe-separated concept string into individual concepts.
pub fn parse_concepts(raw: &str) -> Vec<String> {
    raw.split(|c: char| c == ',' || c == ';' || c == '|')
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect()
}

/// Count concept frequencies across a collection of concept lists.
/// Returns (concept, count) pairs sorted by count descending.
pub fn top_topics(concept_lists: &[Vec<String>], top_n: usize) -> Vec<(String, usize)> {
    let mut counter: HashMap<String, usize> = HashMap::new();
    for concepts in concept_lists {
        for concept in concepts {
            *counter.entry(concept.clone()).or_insert(0) += 1;
        }
    }

    let mut sorted: Vec<(String, usize)> = counter.into_iter().collect();
    sorted.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
    sorted.truncate(top_n);
    sorted
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_concepts_comma() {
        let result = parse_concepts("Machine Learning, Neural Network, Deep Learning");
        assert_eq!(result, vec!["Machine Learning", "Neural Network", "Deep Learning"]);
    }

    #[test]
    fn test_parse_concepts_semicolon() {
        let result = parse_concepts("AI; ML; NLP");
        assert_eq!(result, vec!["AI", "ML", "NLP"]);
    }

    #[test]
    fn test_parse_concepts_mixed() {
        let result = parse_concepts("AI, ML; NLP | CV");
        assert_eq!(result, vec!["AI", "ML", "NLP", "CV"]);
    }

    #[test]
    fn test_parse_concepts_empty() {
        let result = parse_concepts("");
        assert!(result.is_empty());
    }

    #[test]
    fn test_parse_concepts_whitespace_only() {
        let result = parse_concepts("  ,  , ");
        assert!(result.is_empty());
    }

    #[test]
    fn test_top_topics_basic() {
        let lists = vec![
            vec!["AI".to_string(), "ML".to_string()],
            vec!["AI".to_string(), "NLP".to_string()],
            vec!["AI".to_string(), "ML".to_string(), "CV".to_string()],
        ];
        let result = top_topics(&lists, 3);
        assert_eq!(result[0], ("AI".to_string(), 3));
        assert_eq!(result[1], ("ML".to_string(), 2));
        // NLP and CV both have count 1, sorted alphabetically
        assert_eq!(result[2].1, 1);
    }

    #[test]
    fn test_top_topics_truncation() {
        let lists = vec![
            vec!["A".to_string(), "B".to_string(), "C".to_string(), "D".to_string()],
        ];
        let result = top_topics(&lists, 2);
        assert_eq!(result.len(), 2);
    }

    #[test]
    fn test_top_topics_empty() {
        let lists: Vec<Vec<String>> = vec![];
        let result = top_topics(&lists, 10);
        assert!(result.is_empty());
    }
}
