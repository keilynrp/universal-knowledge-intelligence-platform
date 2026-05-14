//! Pointwise Mutual Information (PMI) co-occurrence computation.

use std::collections::HashMap;

/// Compute PMI co-occurrence pairs from concept lists.
///
/// PMI = log2(P(a,b) / (P(a) * P(b)))
/// where P(a) = count(a) / total_docs, P(a,b) = co_count(a,b) / total_docs.
///
/// Returns top_n pairs sorted by co-occurrence count descending.
pub fn cooccurrence_pmi(
    concept_lists: &[Vec<String>],
    top_n: usize,
) -> Vec<CooccurrenceEntry> {
    let total = concept_lists.len();
    if total == 0 {
        return vec![];
    }

    let mut concept_counter: HashMap<String, usize> = HashMap::new();
    let mut pair_counter: HashMap<(String, String), usize> = HashMap::new();

    for concepts in concept_lists {
        // Deduplicate within each document
        let mut unique: Vec<&String> = concepts.iter().collect();
        unique.sort();
        unique.dedup();

        for concept in &unique {
            *concept_counter.entry((*concept).clone()).or_insert(0) += 1;
        }

        // Count pairs (canonicalized: a < b)
        for i in 0..unique.len() {
            for j in (i + 1)..unique.len() {
                let a = unique[i].clone();
                let b = unique[j].clone();
                *pair_counter.entry((a, b)).or_insert(0) += 1;
            }
        }
    }

    let total_f = total as f64;
    let mut entries: Vec<CooccurrenceEntry> = pair_counter
        .into_iter()
        .map(|((a, b), co_count)| {
            let p_a = *concept_counter.get(&a).unwrap_or(&0) as f64 / total_f;
            let p_b = *concept_counter.get(&b).unwrap_or(&0) as f64 / total_f;
            let p_ab = co_count as f64 / total_f;

            let pmi = if p_a > 0.0 && p_b > 0.0 && p_ab > 0.0 {
                (p_ab / (p_a * p_b)).log2()
            } else {
                0.0
            };

            CooccurrenceEntry {
                concept_a: a,
                concept_b: b,
                co_count,
                pmi: (pmi * 1000.0).round() / 1000.0,
            }
        })
        .collect();

    entries.sort_by(|a, b| b.co_count.cmp(&a.co_count).then_with(|| a.concept_a.cmp(&b.concept_a)));
    entries.truncate(top_n);
    entries
}

#[derive(Debug, Clone)]
pub struct CooccurrenceEntry {
    pub concept_a: String,
    pub concept_b: String,
    pub co_count: usize,
    pub pmi: f64,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cooccurrence_basic() {
        let lists = vec![
            vec!["AI".to_string(), "ML".to_string()],
            vec!["AI".to_string(), "ML".to_string(), "NLP".to_string()],
            vec!["AI".to_string(), "NLP".to_string()],
        ];
        let result = cooccurrence_pmi(&lists, 10);
        assert!(!result.is_empty());

        // AI-ML appears in 2 docs, AI-NLP in 2, ML-NLP in 1
        let ai_ml = result.iter().find(|e| e.concept_a == "AI" && e.concept_b == "ML").unwrap();
        assert_eq!(ai_ml.co_count, 2);

        let ai_nlp = result.iter().find(|e| e.concept_a == "AI" && e.concept_b == "NLP").unwrap();
        assert_eq!(ai_nlp.co_count, 2);
    }

    #[test]
    fn test_cooccurrence_pmi_perfect() {
        // If two concepts always appear together and nowhere else: PMI > 0
        let lists = vec![
            vec!["X".to_string(), "Y".to_string()],
            vec!["X".to_string(), "Y".to_string()],
        ];
        let result = cooccurrence_pmi(&lists, 10);
        assert_eq!(result.len(), 1);
        assert_eq!(result[0].co_count, 2);
        // PMI = log2(1.0 / (1.0 * 1.0)) = 0.0 (perfect co-occurrence, both appear in all docs)
        assert!((result[0].pmi - 0.0).abs() < 0.01);
    }

    #[test]
    fn test_cooccurrence_empty() {
        let result = cooccurrence_pmi(&[], 10);
        assert!(result.is_empty());
    }

    #[test]
    fn test_cooccurrence_truncation() {
        let lists = vec![
            vec!["A".to_string(), "B".to_string(), "C".to_string(), "D".to_string()],
        ];
        let result = cooccurrence_pmi(&lists, 2);
        assert_eq!(result.len(), 2);
    }

    #[test]
    fn test_cooccurrence_deduplicates_within_doc() {
        let lists = vec![
            vec!["AI".to_string(), "AI".to_string(), "ML".to_string()],
        ];
        let result = cooccurrence_pmi(&lists, 10);
        assert_eq!(result.len(), 1);
        assert_eq!(result[0].co_count, 1);
    }
}
