use std::collections::HashMap;

use super::fuzzy::{token_sort_ratio, token_set_ratio};
use super::normalize::{normalize_name, reformat_surname_first};

// Signal weights
const W_ID: f64 = 0.35;
const W_NAME: f64 = 0.25;
const W_AFFIL: f64 = 0.20;
const W_COAUTH: f64 = 0.10; // reserved
const W_TOPIC: f64 = 0.10; // reserved

// Source quality priors
fn source_quality(source: &str) -> f64 {
    match source {
        "orcid" => 0.90,
        "openalex" => 0.70,
        "viaf" => 0.65,
        "wikidata" => 0.55,
        "dbpedia" => 0.40,
        _ => 0.30,
    }
}

// Resolution thresholds
const T_EXACT: f64 = 0.85;
const T_PROBABLE: f64 = 0.65;
const T_AMBIGUOUS: f64 = 0.45;

pub struct ScoreResult {
    pub total: f64,
    pub breakdown: HashMap<String, f64>,
    pub evidence: Vec<String>,
    pub resolution_status: String,
}

fn score_identifiers(
    source: &str,
    authority_id: &str,
    orcid_hint: Option<&str>,
    evidence: &mut Vec<String>,
) -> f64 {
    let base = source_quality(source);
    evidence.push(format!("source_quality:{}={:.2}", source, base));

    if let Some(hint) = orcid_hint {
        if source == "orcid" {
            let hint = hint
                .trim()
                .strip_prefix("https://orcid.org/")
                .unwrap_or(hint.trim());
            if !hint.is_empty() && authority_id.contains(hint) {
                evidence.push("orcid_hint_matched".to_string());
                return 1.0;
            }
        }
    }

    base
}

fn score_name(query: &str, canonical_label: &str, evidence: &mut Vec<String>) -> f64 {
    let qn = normalize_name(query);
    let variants = [
        normalize_name(canonical_label),
        normalize_name(&reformat_surname_first(canonical_label)),
    ];

    let mut best = variants
        .iter()
        .map(|v| token_sort_ratio(&qn, v))
        .fold(0.0_f64, f64::max);

    // Bonus for complete token overlap
    if token_set_ratio(&qn, &variants[0]) > 0.99 {
        best = (best + 0.05).min(1.0);
        evidence.push("token_set_exact".to_string());
    }

    evidence.push(format!("name_score:{:.3}", best));
    (best * 1000.0).round() / 1000.0
}

fn score_affiliation(
    description: Option<&str>,
    affiliation: Option<&str>,
    evidence: &mut Vec<String>,
) -> f64 {
    let (desc, affil) = match (description, affiliation) {
        (Some(d), Some(a)) if !d.is_empty() && !a.is_empty() => (d, a),
        _ => return 0.0,
    };

    let nd = normalize_name(desc);
    let na = normalize_name(affil);

    // Partial ratio: check if the shorter string appears within the longer
    let score = if nd.contains(&na) || na.contains(&nd) {
        1.0
    } else {
        token_sort_ratio(&na, &nd)
    };

    if score > 0.6 {
        evidence.push(format!("affiliation_match:{:.2}", score));
    }
    (score * 1000.0).round() / 1000.0
}

/// Compute the weighted authority score for a single candidate.
pub fn compute_score(
    value: &str,
    authority_source: &str,
    authority_id: &str,
    canonical_label: &str,
    description: Option<&str>,
    orcid_hint: Option<&str>,
    affiliation: Option<&str>,
) -> ScoreResult {
    let mut evidence: Vec<String> = Vec::new();

    let s_id = score_identifiers(authority_source, authority_id, orcid_hint, &mut evidence);
    let s_name = score_name(value, canonical_label, &mut evidence);
    let s_affil = score_affiliation(description, affiliation, &mut evidence);
    let s_coauth = 0.0;
    let s_topic = 0.0;

    // Dynamic weight normalization
    let w_affil = if affiliation.is_some() { W_AFFIL } else { 0.0 };
    let total_w = W_ID + W_NAME + w_affil; // coauth and topic are 0
    let eff_id = W_ID / total_w;
    let eff_name = W_NAME / total_w;
    let eff_affil = w_affil / total_w;

    let total = (eff_id * s_id + eff_name * s_name + eff_affil * s_affil) * 1000.0;
    let total = total.round() / 1000.0;

    let mut breakdown = HashMap::new();
    breakdown.insert("identifiers".to_string(), (s_id * 1000.0).round() / 1000.0);
    breakdown.insert("name".to_string(), (s_name * 1000.0).round() / 1000.0);
    breakdown.insert("affiliation".to_string(), (s_affil * 1000.0).round() / 1000.0);
    breakdown.insert("coauthorship".to_string(), s_coauth);
    breakdown.insert("topic".to_string(), s_topic);

    let resolution_status = if total >= T_EXACT {
        "exact_match"
    } else if total >= T_PROBABLE {
        "probable_match"
    } else if total >= T_AMBIGUOUS {
        "ambiguous"
    } else {
        "unresolved"
    };

    ScoreResult {
        total,
        breakdown,
        evidence,
        resolution_status: resolution_status.to_string(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_high_quality_source_high_name_match() {
        let result = compute_score(
            "John Smith",
            "orcid",
            "0000-0001-2345-6789",
            "John Smith",
            None,
            None,
            None,
        );
        assert!(
            result.total >= T_EXACT,
            "expected exact_match, got {} ({})",
            result.total,
            result.resolution_status
        );
        assert_eq!(result.resolution_status, "exact_match");
    }

    #[test]
    fn test_orcid_hint_match_boosts_to_max() {
        let result = compute_score(
            "John Smith",
            "orcid",
            "0000-0001-2345-6789",
            "John Smith",
            None,
            Some("0000-0001-2345-6789"),
            None,
        );
        assert!(result.total >= 0.95, "score={}", result.total);
        assert_eq!(result.resolution_status, "exact_match");
    }

    #[test]
    fn test_low_quality_source_different_name() {
        let result = compute_score(
            "John Smith",
            "dbpedia",
            "John_Smith_(engineer)",
            "Alice Jones",
            None,
            None,
            None,
        );
        assert!(result.total < T_AMBIGUOUS, "score={}", result.total);
        assert_eq!(result.resolution_status, "unresolved");
    }

    #[test]
    fn test_affiliation_context_changes_score() {
        let without = compute_score(
            "John Smith",
            "openalex",
            "A12345",
            "John Smith",
            Some("MIT, Cambridge"),
            None,
            None,
        );
        let with = compute_score(
            "John Smith",
            "openalex",
            "A12345",
            "John Smith",
            Some("MIT, Cambridge"),
            None,
            Some("MIT"),
        );
        // With affiliation context, score should be at least as high
        assert!(
            with.total >= without.total,
            "with={} without={}",
            with.total,
            without.total
        );
    }

    #[test]
    fn test_resolution_thresholds() {
        assert_eq!(
            if 0.90 >= T_EXACT { "exact_match" } else { "other" },
            "exact_match"
        );
        assert_eq!(
            if 0.70 >= T_PROBABLE && 0.70 < T_EXACT { "probable_match" } else { "other" },
            "probable_match"
        );
        assert_eq!(
            if 0.50 >= T_AMBIGUOUS && 0.50 < T_PROBABLE { "ambiguous" } else { "other" },
            "ambiguous"
        );
        assert_eq!(
            if 0.30 < T_AMBIGUOUS { "unresolved" } else { "other" },
            "unresolved"
        );
    }

    #[test]
    fn test_weight_renormalization_without_affiliation() {
        // Without affiliation: weights should renormalize so W_ID + W_NAME = 1.0
        let result = compute_score(
            "John Smith",
            "openalex",
            "A123",
            "John Smith",
            None,
            None,
            None, // no affiliation
        );
        // Score should still reach max ~0.95 with good source + perfect name
        assert!(result.total > 0.7, "total={}", result.total);
        assert!(result.breakdown["affiliation"] == 0.0);
    }

    #[test]
    fn test_weight_renormalization_with_affiliation() {
        let result = compute_score(
            "John Smith",
            "orcid",
            "0000-0001",
            "John Smith",
            Some("Massachusetts Institute of Technology"),
            None,
            Some("MIT"),
        );
        // With affiliation context, all three signals contribute
        assert!(result.breakdown["affiliation"] > 0.0);
    }

    #[test]
    fn test_unknown_source_gets_low_quality() {
        let result = compute_score(
            "John Smith",
            "unknown_source",
            "X999",
            "John Smith",
            None,
            None,
            None,
        );
        // Unknown source quality = 0.30 vs orcid = 0.90
        let result_orcid = compute_score(
            "John Smith",
            "orcid",
            "0000-0001",
            "John Smith",
            None,
            None,
            None,
        );
        assert!(result.total < result_orcid.total);
        assert!(result.breakdown["identifiers"] < result_orcid.breakdown["identifiers"]);
    }

    #[test]
    fn test_score_name_with_surname_first_format() {
        // "Smith, John" should match "John Smith" highly
        let result = compute_score(
            "John Smith",
            "viaf",
            "V123",
            "Smith, John",
            None,
            None,
            None,
        );
        assert!(result.breakdown["name"] > 0.9, "name score was {}", result.breakdown["name"]);
    }

    #[test]
    fn test_orcid_hint_url_format() {
        // ORCID hint as full URL should still match
        let result = compute_score(
            "John Smith",
            "orcid",
            "0000-0001-2345-6789",
            "John Smith",
            None,
            Some("https://orcid.org/0000-0001-2345-6789"),
            None,
        );
        assert_eq!(result.breakdown["identifiers"], 1.0);
    }

    #[test]
    fn test_orcid_hint_mismatch() {
        let result = compute_score(
            "John Smith",
            "orcid",
            "0000-0001-2345-6789",
            "John Smith",
            None,
            Some("0000-9999-9999-9999"), // wrong ORCID
            None,
        );
        // Should fall back to source_quality, not 1.0
        assert_eq!(result.breakdown["identifiers"], 0.9); // orcid base quality
    }

    #[test]
    fn test_affiliation_exact_substring_match() {
        let result = compute_score(
            "John Smith",
            "openalex",
            "A1",
            "John Smith",
            Some("Department of Physics, MIT, Cambridge, MA"),
            None,
            Some("mit"),
        );
        assert!(result.breakdown["affiliation"] > 0.9, "affil={}", result.breakdown["affiliation"]);
    }

    #[test]
    fn test_evidence_tracking() {
        let result = compute_score(
            "John Smith",
            "orcid",
            "0000-0001",
            "John Smith",
            None,
            Some("0000-0001"),
            None,
        );
        assert!(result.evidence.iter().any(|e| e.contains("orcid_hint_matched")));
    }

    #[test]
    fn test_score_bounded_zero_one() {
        // All scores should be in [0, 1]
        let cases = [
            ("X", "unknown", "?", "Y", None, None, None),
            ("John Smith", "orcid", "0000-0001", "John Smith", None, Some("0000-0001"), Some("MIT")),
        ];
        for (value, src, id, label, desc, orcid, affil) in &cases {
            let r = compute_score(value, src, id, label, *desc, *orcid, *affil);
            assert!(r.total >= 0.0 && r.total <= 1.0, "out of bounds: {}", r.total);
        }
    }
}
