//! Golden-file test: compare Rust analytics module output against Python reference data.

use serde::Deserialize;

use ukip_engine::pipelines::analytics::clustering::topic_clusters;
use ukip_engine::pipelines::analytics::pmi::cooccurrence_pmi;
use ukip_engine::pipelines::analytics::topics::top_topics;

#[derive(Deserialize)]
struct GoldenData {
    concept_lists: Vec<Vec<String>>,
    topics: Vec<TopicCase>,
    cooccurrences: Vec<CooccurrenceCase>,
    clustering: ClusteringCase,
}

#[derive(Deserialize)]
struct TopicCase {
    concept: String,
    count: usize,
}

#[derive(Deserialize)]
struct CooccurrenceCase {
    a: String,
    b: String,
    co_count: usize,
    pmi_approx: f64,
}

#[derive(Deserialize)]
struct ClusteringCase {
    n_clusters: usize,
    expected_seed_0: String,
    min_total_members: usize,
}

fn load_golden() -> GoldenData {
    let data = include_str!("golden_analytics.json");
    serde_json::from_str(data).expect("failed to parse golden_analytics.json")
}

#[test]
fn golden_top_topics() {
    let golden = load_golden();
    let result = top_topics(&golden.concept_lists, 10);

    // Check counts match Python
    for expected in &golden.topics {
        let found = result
            .iter()
            .find(|(c, _)| c == &expected.concept);
        assert!(
            found.is_some(),
            "missing topic: {}",
            expected.concept
        );
        assert_eq!(
            found.unwrap().1, expected.count,
            "count mismatch for {}",
            expected.concept
        );
    }

    // Top concept should be Machine Learning with count=3
    assert_eq!(result[0].0, "Machine Learning");
    assert_eq!(result[0].1, 3);
}

#[test]
fn golden_cooccurrence_pmi() {
    let golden = load_golden();
    let result = cooccurrence_pmi(&golden.concept_lists, 20);

    for expected in &golden.cooccurrences {
        let found = result.iter().find(|e| {
            (e.concept_a == expected.a && e.concept_b == expected.b)
                || (e.concept_a == expected.b && e.concept_b == expected.a)
        });
        assert!(
            found.is_some(),
            "missing pair: {} - {}",
            expected.a, expected.b
        );
        let entry = found.unwrap();
        assert_eq!(
            entry.co_count, expected.co_count,
            "co_count mismatch for {}-{}",
            expected.a, expected.b
        );
        // PMI tolerance: ±0.1
        assert!(
            (entry.pmi - expected.pmi_approx).abs() < 0.1,
            "PMI mismatch for {}-{}: got {}, expected ~{}",
            expected.a,
            expected.b,
            entry.pmi,
            expected.pmi_approx
        );
    }
}

#[test]
fn golden_topic_clusters() {
    let golden = load_golden();
    let clusters = topic_clusters(
        &golden.concept_lists,
        golden.clustering.n_clusters,
    );

    assert_eq!(clusters.len(), golden.clustering.n_clusters);
    assert_eq!(clusters[0].seed, golden.clustering.expected_seed_0);

    let total_members: usize = clusters.iter().map(|c| c.members.len()).sum();
    assert!(
        total_members >= golden.clustering.min_total_members,
        "expected at least {} members, got {}",
        golden.clustering.min_total_members,
        total_members
    );
}
