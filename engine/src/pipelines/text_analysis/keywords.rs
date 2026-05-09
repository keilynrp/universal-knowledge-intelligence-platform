use std::collections::HashMap;

pub struct TfIdfExtractor {
    max_keywords: usize,
    min_df: f64,
    max_df: f64,
}

impl TfIdfExtractor {
    pub fn new(max_keywords: usize, min_df: f64, max_df: f64) -> Self {
        Self {
            max_keywords,
            min_df,
            max_df,
        }
    }

    /// Extract top-N keywords per document using TF-IDF.
    /// `corpus` is a list of tokenized documents.
    pub fn extract(&self, corpus: &[Vec<String>]) -> Vec<Vec<(String, f64)>> {
        let n_docs = corpus.len();
        if n_docs == 0 {
            return vec![];
        }

        // 1. Build document frequency map
        let mut df: HashMap<String, usize> = HashMap::new();
        for doc in corpus {
            let unique: std::collections::HashSet<&String> = doc.iter().collect();
            for word in unique {
                *df.entry(word.clone()).or_insert(0) += 1;
            }
        }

        // 2. Filter by min_df and max_df (as fractions of total docs)
        let min_count = (self.min_df * n_docs as f64).ceil() as usize;
        let max_count = (self.max_df * n_docs as f64).floor().max(1.0) as usize;

        let filtered_df: HashMap<&String, usize> = df
            .iter()
            .filter(|(_, &count)| count >= min_count && count <= max_count)
            .map(|(k, &v)| (k, v))
            .collect();

        // 3. Compute TF-IDF per document
        corpus
            .iter()
            .map(|doc| {
                if doc.is_empty() {
                    return vec![];
                }

                // Term frequency
                let mut tf: HashMap<String, f64> = HashMap::new();
                for word in doc {
                    *tf.entry(word.clone()).or_insert(0.0) += 1.0;
                }
                let doc_len = doc.len() as f64;
                for v in tf.values_mut() {
                    *v /= doc_len;
                }

                // TF-IDF score
                let mut scores: Vec<(String, f64)> = tf
                    .into_iter()
                    .filter_map(|(word, tf_val)| {
                        let df_count = *filtered_df.get(&word)?;
                        let idf = ((n_docs as f64 + 1.0) / (df_count as f64 + 1.0)).ln() + 1.0;
                        Some((word, tf_val * idf))
                    })
                    .collect();

                // Sort descending by score
                scores.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
                scores.truncate(self.max_keywords);
                scores
            })
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_keywords_basic() {
        let corpus = vec![
            vec!["machine".to_string(), "learning".to_string(), "neural".to_string(), "network".to_string()],
            vec!["deep".to_string(), "learning".to_string(), "convolutional".to_string(), "network".to_string()],
            vec!["natural".to_string(), "language".to_string(), "processing".to_string(), "transformer".to_string()],
        ];
        let extractor = TfIdfExtractor::new(5, 0.0, 1.0);
        let results = extractor.extract(&corpus);
        assert_eq!(results.len(), 3);
        // All docs should have keywords
        assert!(!results[0].is_empty());
    }

    #[test]
    fn test_empty_corpus() {
        let extractor = TfIdfExtractor::new(5, 0.0, 1.0);
        let results = extractor.extract(&[]);
        assert!(results.is_empty());
    }

    #[test]
    fn test_single_doc() {
        let corpus = vec![
            vec!["rust".to_string(), "programming".to_string(), "systems".to_string()],
        ];
        let extractor = TfIdfExtractor::new(5, 0.0, 1.0);
        let results = extractor.extract(&corpus);
        assert_eq!(results.len(), 1);
        assert!(!results[0].is_empty());
    }

    #[test]
    fn test_max_keywords_limit() {
        let corpus = vec![
            vec!["a".to_string(), "b".to_string(), "c".to_string(), "d".to_string(),
                 "e".to_string(), "f".to_string(), "g".to_string(), "h".to_string()],
        ];
        let extractor = TfIdfExtractor::new(3, 0.0, 1.0);
        let results = extractor.extract(&corpus);
        assert!(results[0].len() <= 3);
    }

    #[test]
    fn test_max_df_filters_common_words() {
        let corpus = vec![
            vec!["common".to_string(), "rare_a".to_string()],
            vec!["common".to_string(), "rare_b".to_string()],
            vec!["common".to_string(), "rare_c".to_string()],
        ];
        // max_df = 0.5 should filter "common" (appears in all 3 docs = 100%)
        let extractor = TfIdfExtractor::new(5, 0.0, 0.5);
        let results = extractor.extract(&corpus);
        for doc_kws in &results {
            assert!(!doc_kws.iter().any(|(w, _)| w == "common"));
        }
    }
}
