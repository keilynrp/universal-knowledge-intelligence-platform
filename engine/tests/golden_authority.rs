//! Golden-file test: compare Rust authority module output against Python reference data.
//!
//! The golden file `tests/golden_authority.json` was generated from the Python
//! `backend.authority` module to ensure parity between the Rust and Python
//! implementations.

use serde::Deserialize;
use std::collections::HashMap;

use ukip_engine::pipelines::authority::fuzzy::token_sort_ratio;
use ukip_engine::pipelines::authority::normalize::{
    name_variants, normalize_name, reformat_surname_first,
};
use ukip_engine::pipelines::authority::scoring::compute_score;

#[derive(Deserialize)]
struct GoldenData {
    normalize: Vec<NormalizeCase>,
    reformat: Vec<ReformatCase>,
    variants: Vec<VariantsCase>,
    scoring: Vec<ScoringCase>,
}

#[derive(Deserialize)]
struct NormalizeCase {
    input: String,
    expected: String,
}

#[derive(Deserialize)]
struct ReformatCase {
    input: String,
    expected: String,
}

#[derive(Deserialize)]
struct VariantsCase {
    input: String,
    expected: Vec<String>,
}

#[derive(Deserialize)]
struct ScoringCase {
    value: String,
    source: String,
    id: String,
    label: String,
    orcid_hint: Option<String>,
    affiliation: Option<String>,
    description: Option<String>,
    expected_status: String,
    #[serde(default)]
    expected_total_min: Option<f64>,
    #[serde(default)]
    expected_total_max: Option<f64>,
    expected_breakdown: HashMap<String, f64>,
}

fn load_golden() -> GoldenData {
    let data = include_str!("golden_authority.json");
    serde_json::from_str(data).expect("failed to parse golden_authority.json")
}

#[test]
fn golden_normalize_name() {
    let golden = load_golden();
    for case in &golden.normalize {
        let result = normalize_name(&case.input);
        assert_eq!(
            result, case.expected,
            "normalize_name({:?}): got {:?}, expected {:?}",
            case.input, result, case.expected
        );
    }
}

#[test]
fn golden_reformat_surname_first() {
    let golden = load_golden();
    for case in &golden.reformat {
        let result = reformat_surname_first(&case.input);
        assert_eq!(
            result, case.expected,
            "reformat_surname_first({:?}): got {:?}, expected {:?}",
            case.input, result, case.expected
        );
    }
}

#[test]
fn golden_name_variants() {
    let golden = load_golden();
    for case in &golden.variants {
        let mut result = name_variants(&case.input);
        result.sort();
        assert_eq!(
            result, case.expected,
            "name_variants({:?}): got {:?}, expected {:?}",
            case.input, result, case.expected
        );
    }
}

#[test]
fn golden_scoring() {
    let golden = load_golden();
    for (i, case) in golden.scoring.iter().enumerate() {
        let result = compute_score(
            &case.value,
            &case.source,
            &case.id,
            &case.label,
            case.description.as_deref(),
            case.orcid_hint.as_deref(),
            case.affiliation.as_deref(),
        );

        // Check resolution status
        assert_eq!(
            result.resolution_status, case.expected_status,
            "scoring case {}: status got {:?}, expected {:?} (total={})",
            i, result.resolution_status, case.expected_status, result.total
        );

        // Check total bounds
        if let Some(min) = case.expected_total_min {
            assert!(
                result.total >= min,
                "scoring case {}: total {} < min {}",
                i, result.total, min
            );
        }
        if let Some(max) = case.expected_total_max {
            assert!(
                result.total <= max,
                "scoring case {}: total {} > max {}",
                i, result.total, max
            );
        }

        // Check breakdown values match within tolerance
        for (key, expected_val) in &case.expected_breakdown {
            let actual = result
                .breakdown
                .get(key)
                .copied()
                .unwrap_or(0.0);
            assert!(
                (actual - expected_val).abs() < 0.05,
                "scoring case {}: breakdown[{:?}] = {}, expected {} (tolerance 0.05)",
                i, key, actual, expected_val
            );
        }
    }
}

#[test]
fn golden_token_sort_ratio_reorder_parity() {
    // Python fuzzywuzzy token_sort_ratio("john smith", "smith john") == 100
    // Rust should return ~1.0
    let score = token_sort_ratio("john smith", "smith john");
    assert!(
        (score - 1.0).abs() < 0.001,
        "token_sort_ratio reorder: got {}",
        score
    );
}

#[test]
fn golden_token_sort_ratio_different() {
    // Python: token_sort_ratio("john smith", "alice jones") is low
    let score = token_sort_ratio("john smith", "alice jones");
    assert!(score < 0.5, "token_sort_ratio different: got {}", score);
}
