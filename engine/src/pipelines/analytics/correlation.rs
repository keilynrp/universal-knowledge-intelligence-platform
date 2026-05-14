//! Cramér's V correlation between categorical fields.

use std::collections::HashMap;

/// Maximum cardinality for a field to be analyzed.
const MAX_CARDINALITY: usize = 50;

/// Fields to skip (free text, high cardinality, identifiers).
const SKIP_FIELDS: &[&str] = &[
    "entity_name", "title", "sku", "gtin", "doi", "nct_id",
    "enrichment_concepts", "normalized_json", "enrichment_doi",
    "id", "enrichment_citation_count", "enrichment_status", "enrichment_source",
    "validation_status", "creation_date", "barcode", "branches",
];

/// Result of a correlation analysis between two fields.
#[derive(Debug, Clone)]
pub struct CorrelationEntry {
    pub field_a: String,
    pub field_b: String,
    pub cramers_v: f64,
    pub strength: String,
}

/// Compute Cramér's V between two categorical arrays.
///
/// Returns a value in [0, 1]; 0 = no association, 1 = perfect.
pub fn cramers_v(x: &[String], y: &[String]) -> f64 {
    assert_eq!(x.len(), y.len(), "arrays must have equal length");

    let n = x.len();
    if n == 0 {
        return 0.0;
    }

    // Build category indices
    let mut x_cats: Vec<String> = x.to_vec();
    x_cats.sort();
    x_cats.dedup();
    let mut y_cats: Vec<String> = y.to_vec();
    y_cats.sort();
    y_cats.dedup();

    let x_idx: HashMap<&str, usize> = x_cats.iter().enumerate().map(|(i, c)| (c.as_str(), i)).collect();
    let y_idx: HashMap<&str, usize> = y_cats.iter().enumerate().map(|(i, c)| (c.as_str(), i)).collect();

    let r = x_cats.len();
    let c = y_cats.len();

    if r <= 1 || c <= 1 {
        return 0.0;
    }

    // Build contingency table
    let mut ct = vec![0u64; r * c];
    for (xi, yi) in x.iter().zip(y.iter()) {
        let ri = x_idx[xi.as_str()];
        let ci = y_idx[yi.as_str()];
        ct[ri * c + ci] += 1;
    }

    // Row and column sums
    let n_f = n as f64;
    let row_sums: Vec<f64> = (0..r)
        .map(|i| ct[i * c..(i + 1) * c].iter().sum::<u64>() as f64)
        .collect();
    let col_sums: Vec<f64> = (0..c)
        .map(|j| (0..r).map(|i| ct[i * c + j]).sum::<u64>() as f64)
        .collect();

    // Chi-squared
    let mut chi2 = 0.0;
    for i in 0..r {
        for j in 0..c {
            let expected = row_sums[i] * col_sums[j] / n_f;
            if expected > 0.0 {
                let observed = ct[i * c + j] as f64;
                chi2 += (observed - expected).powi(2) / expected;
            }
        }
    }

    let k = r.min(c);
    if k <= 1 || n <= 1 {
        return 0.0;
    }

    let v = (chi2 / (n_f * (k as f64 - 1.0))).sqrt();
    (v.min(1.0) * 10000.0).round() / 10000.0
}

/// Classify correlation strength.
pub fn strength_label(v: f64) -> &'static str {
    if v >= 0.5 {
        "strong"
    } else if v >= 0.2 {
        "moderate"
    } else {
        "weak"
    }
}

/// Check whether a field should be skipped.
pub fn should_skip_field(field: &str) -> bool {
    SKIP_FIELDS.contains(&field)
}

/// Check whether a field has acceptable cardinality.
pub fn within_cardinality(distinct_count: usize) -> bool {
    distinct_count <= MAX_CARDINALITY
}

/// Compute pairwise Cramér's V for all valid field pairs.
///
/// `field_data` maps field names to their value arrays (all same length).
/// Returns entries sorted by Cramér's V descending, capped at `top_n`.
pub fn top_correlations(
    field_data: &HashMap<String, Vec<String>>,
    top_n: usize,
) -> Vec<CorrelationEntry> {
    // Filter to usable fields
    let usable: Vec<&String> = field_data
        .keys()
        .filter(|f| !should_skip_field(f))
        .filter(|f| {
            let vals = &field_data[*f];
            let mut unique = vals.clone();
            unique.sort();
            unique.dedup();
            within_cardinality(unique.len()) && unique.len() > 1
        })
        .collect();

    let mut entries = Vec::new();

    for i in 0..usable.len() {
        for j in (i + 1)..usable.len() {
            let a = usable[i];
            let b = usable[j];
            let x = &field_data[a];
            let y = &field_data[b];

            if x.len() < 5 {
                continue;
            }

            let v = cramers_v(x, y);
            if v < 0.05 {
                continue;
            }

            entries.push(CorrelationEntry {
                field_a: a.clone(),
                field_b: b.clone(),
                cramers_v: v,
                strength: strength_label(v).to_string(),
            });
        }
    }

    entries.sort_by(|a, b| b.cramers_v.partial_cmp(&a.cramers_v).unwrap_or(std::cmp::Ordering::Equal));
    entries.truncate(top_n);
    entries
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cramers_v_perfect_association() {
        // Perfect 1:1 mapping
        let x = vec!["A".to_string(), "A".to_string(), "B".to_string(), "B".to_string(), "C".to_string()];
        let y = vec!["X".to_string(), "X".to_string(), "Y".to_string(), "Y".to_string(), "Z".to_string()];
        let v = cramers_v(&x, &y);
        assert!(v > 0.9, "expected near 1.0, got {}", v);
    }

    #[test]
    fn test_cramers_v_no_association() {
        // Uniformly distributed — near zero
        let x: Vec<String> = (0..100).map(|i| if i % 2 == 0 { "A".to_string() } else { "B".to_string() }).collect();
        let y: Vec<String> = (0..100).map(|i| if i % 3 == 0 { "X".to_string() } else if i % 3 == 1 { "Y".to_string() } else { "Z".to_string() }).collect();
        let v = cramers_v(&x, &y);
        assert!(v < 0.3, "expected low V, got {}", v);
    }

    #[test]
    fn test_cramers_v_empty() {
        let v = cramers_v(&[], &[]);
        assert!((v - 0.0).abs() < 0.001);
    }

    #[test]
    fn test_cramers_v_single_category() {
        let x = vec!["A".to_string(); 10];
        let y = vec!["X".to_string(), "Y".to_string(), "X".to_string(), "Y".to_string(), "X".to_string(),
                     "Y".to_string(), "X".to_string(), "Y".to_string(), "X".to_string(), "Y".to_string()];
        let v = cramers_v(&x, &y);
        assert!((v - 0.0).abs() < 0.001, "single x category → V=0, got {}", v);
    }

    #[test]
    fn test_strength_label() {
        assert_eq!(strength_label(0.6), "strong");
        assert_eq!(strength_label(0.5), "strong");
        assert_eq!(strength_label(0.3), "moderate");
        assert_eq!(strength_label(0.2), "moderate");
        assert_eq!(strength_label(0.1), "weak");
        assert_eq!(strength_label(0.0), "weak");
    }

    #[test]
    fn test_skip_fields() {
        assert!(should_skip_field("entity_name"));
        assert!(should_skip_field("doi"));
        assert!(!should_skip_field("brand"));
    }

    #[test]
    fn test_within_cardinality() {
        assert!(within_cardinality(10));
        assert!(within_cardinality(50));
        assert!(!within_cardinality(51));
    }

    #[test]
    fn test_top_correlations() {
        let mut field_data: HashMap<String, Vec<String>> = HashMap::new();
        // Perfectly correlated fields
        field_data.insert("color".to_string(), vec!["red", "red", "blue", "blue", "green"].iter().map(|s| s.to_string()).collect());
        field_data.insert("shape".to_string(), vec!["circle", "circle", "square", "square", "triangle"].iter().map(|s| s.to_string()).collect());
        // Unrelated field
        field_data.insert("size".to_string(), vec!["S", "L", "M", "S", "L"].iter().map(|s| s.to_string()).collect());

        let result = top_correlations(&field_data, 10);
        assert!(!result.is_empty());
        // color-shape should have high V
        let cs = result.iter().find(|e| {
            (e.field_a == "color" && e.field_b == "shape") ||
            (e.field_a == "shape" && e.field_b == "color")
        });
        assert!(cs.is_some(), "should find color-shape pair");
        assert!(cs.unwrap().cramers_v > 0.5, "should be strong correlation");
    }
}
