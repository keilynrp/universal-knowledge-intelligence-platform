//! Greedy topic clustering: seed by highest-frequency concept, assign by co-occurrence.

use std::collections::HashMap;

/// A topic cluster with a seed concept and its members.
#[derive(Debug, Clone)]
pub struct Cluster {
    pub seed: String,
    pub members: Vec<(String, usize)>, // (concept, count)
}

/// Greedy topic clustering.
///
/// Algorithm:
/// 1. Count concept frequencies across all concept lists.
/// 2. Pick the top n_clusters concepts by frequency as seeds.
/// 3. Assign remaining concepts to the seed they co-occur with most.
///
/// Returns clusters sorted by seed frequency descending.
pub fn topic_clusters(
    concept_lists: &[Vec<String>],
    n_clusters: usize,
) -> Vec<Cluster> {
    let mut concept_counter: HashMap<String, usize> = HashMap::new();
    let mut pair_counter: HashMap<(String, String), usize> = HashMap::new();

    for concepts in concept_lists {
        let mut unique: Vec<&String> = concepts.iter().collect();
        unique.sort();
        unique.dedup();

        for concept in &unique {
            *concept_counter.entry((*concept).clone()).or_insert(0) += 1;
        }

        for i in 0..unique.len() {
            for j in (i + 1)..unique.len() {
                let a = unique[i].clone();
                let b = unique[j].clone();
                let key = if a <= b { (a, b) } else { (b, a) };
                *pair_counter.entry(key).or_insert(0) += 1;
            }
        }
    }

    if concept_counter.is_empty() {
        return vec![];
    }

    // Sort by frequency descending
    let mut sorted_concepts: Vec<(String, usize)> = concept_counter.iter()
        .map(|(k, v)| (k.clone(), *v))
        .collect();
    sorted_concepts.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));

    let seeds: Vec<String> = sorted_concepts.iter()
        .take(n_clusters)
        .map(|(c, _)| c.clone())
        .collect();

    // Assign each concept to the seed with highest co-occurrence
    let mut cluster_map: HashMap<String, String> = HashMap::new();
    for seed in &seeds {
        cluster_map.insert(seed.clone(), seed.clone());
    }

    for (concept, _) in &sorted_concepts[seeds.len()..] {
        let mut best_seed: Option<&String> = None;
        let mut best_score: usize = 0;

        for seed in &seeds {
            let key = if concept <= seed {
                (concept.clone(), seed.clone())
            } else {
                (seed.clone(), concept.clone())
            };
            let score = pair_counter.get(&key).copied().unwrap_or(0);
            if score > best_score {
                best_score = score;
                best_seed = Some(seed);
            }
        }

        if let Some(seed) = best_seed {
            cluster_map.insert(concept.clone(), seed.clone());
        }
    }

    // Build output
    let mut clusters: Vec<Cluster> = seeds
        .iter()
        .map(|seed| {
            let mut members: Vec<(String, usize)> = cluster_map
                .iter()
                .filter(|(_, s)| *s == seed)
                .map(|(concept, _)| {
                    let count = *concept_counter.get(concept).unwrap_or(&0);
                    (concept.clone(), count)
                })
                .collect();
            members.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));

            Cluster {
                seed: seed.clone(),
                members,
            }
        })
        .collect();

    clusters.sort_by(|a, b| {
        let a_count = concept_counter.get(&a.seed).unwrap_or(&0);
        let b_count = concept_counter.get(&b.seed).unwrap_or(&0);
        b_count.cmp(a_count)
    });

    clusters
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_clustering_basic() {
        let lists = vec![
            vec!["AI".to_string(), "ML".to_string(), "DL".to_string()],
            vec!["AI".to_string(), "ML".to_string()],
            vec!["NLP".to_string(), "Text Mining".to_string()],
            vec!["AI".to_string(), "NLP".to_string()],
        ];
        let clusters = topic_clusters(&lists, 2);
        assert_eq!(clusters.len(), 2);
        // AI should be the top seed (count=3)
        assert_eq!(clusters[0].seed, "AI");
    }

    #[test]
    fn test_clustering_empty() {
        let clusters = topic_clusters(&[], 3);
        assert!(clusters.is_empty());
    }

    #[test]
    fn test_clustering_fewer_than_n() {
        let lists = vec![
            vec!["A".to_string()],
        ];
        let clusters = topic_clusters(&lists, 5);
        assert_eq!(clusters.len(), 1);
    }

    #[test]
    fn test_clustering_all_assigned() {
        let lists = vec![
            vec!["A".to_string(), "B".to_string(), "C".to_string()],
            vec!["A".to_string(), "D".to_string()],
            vec!["B".to_string(), "E".to_string()],
        ];
        let clusters = topic_clusters(&lists, 2);
        let total_members: usize = clusters.iter().map(|c| c.members.len()).sum();
        assert_eq!(total_members, 5, "all 5 concepts should be assigned");
    }
}
