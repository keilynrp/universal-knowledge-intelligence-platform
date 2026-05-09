use crate::db::schema::PendingRelationship;
use crate::proto::Publication;
use super::canonical;

/// Compute all relationships for a single publication.
/// Relationship types:
/// - authored-by:     publication → author
/// - belongs-to:      author → affiliation
/// - published-in:    publication → journal
/// - has-concept:     publication → concept
/// - identified-by:   publication → identifier
/// - coauthor-with:   author ↔ author (pairs, ordered by canonical_id)
pub fn compute_relationships(
    _entity_id: i64,
    pub_canonical_id: &str,
    publication: &Publication,
    org_id: Option<i64>,
) -> Vec<PendingRelationship> {
    let mut rels = Vec::new();

    let author_canonical_ids: Vec<String> = publication
        .authors
        .iter()
        .map(|a| canonical::author_canonical_id(a))
        .collect();

    // authored-by: publication → author
    for author_cid in &author_canonical_ids {
        rels.push(PendingRelationship {
            org_id,
            source_canonical_id: pub_canonical_id.to_string(),
            target_canonical_id: author_cid.clone(),
            relation_type: "authored-by".to_string(),
            weight: 1.0,
        });
    }

    // belongs-to: author → affiliation
    for author in &publication.authors {
        let author_cid = canonical::author_canonical_id(author);
        for aff in &publication.affiliations {
            let aff_cid = canonical::affiliation_canonical_id(aff);
            rels.push(PendingRelationship {
                org_id,
                source_canonical_id: author_cid.clone(),
                target_canonical_id: aff_cid,
                relation_type: "belongs-to".to_string(),
                weight: 1.0,
            });
        }
    }

    // published-in: publication → journal
    if let Some(source_title) = &publication.source_title {
        if !source_title.is_empty() {
            let journal_cid = canonical::journal_canonical_id(source_title);
            rels.push(PendingRelationship {
                org_id,
                source_canonical_id: pub_canonical_id.to_string(),
                target_canonical_id: journal_cid,
                relation_type: "published-in".to_string(),
                weight: 1.0,
            });
        }
    }

    // has-concept: publication → concept
    for concept in &publication.concepts {
        if !concept.is_empty() {
            let concept_cid = canonical::concept_canonical_id(concept);
            rels.push(PendingRelationship {
                org_id,
                source_canonical_id: pub_canonical_id.to_string(),
                target_canonical_id: concept_cid,
                relation_type: "has-concept".to_string(),
                weight: 1.0,
            });
        }
    }

    // identified-by: publication → identifier
    for id in &publication.identifiers {
        if !id.value.is_empty() {
            let id_cid = canonical::identifier_canonical_id(&id.scheme, &id.value);
            rels.push(PendingRelationship {
                org_id,
                source_canonical_id: pub_canonical_id.to_string(),
                target_canonical_id: id_cid,
                relation_type: "identified-by".to_string(),
                weight: 1.0,
            });
        }
    }

    // coauthor-with: author ↔ author (N*(N-1)/2 pairs, ordered by canonical_id)
    let n = author_canonical_ids.len();
    for i in 0..n {
        for j in (i + 1)..n {
            let mut pair = [author_canonical_ids[i].clone(), author_canonical_ids[j].clone()];
            pair.sort(); // ensure canonical ordering
            rels.push(PendingRelationship {
                org_id,
                source_canonical_id: pair[0].clone(),
                target_canonical_id: pair[1].clone(),
                relation_type: "coauthor-with".to_string(),
                weight: 1.0,
            });
        }
    }

    rels
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::proto::{Author, Affiliation, Identifier};

    fn two_author_pub() -> Publication {
        Publication {
            entity_id: 42,
            title: "Test Paper".to_string(),
            source_title: Some("Nature".to_string()),
            authors: vec![
                Author {
                    name: "Alice Smith".to_string(),
                    orcid: Some("0000-0001-0000-0001".to_string()),
                    ..Default::default()
                },
                Author {
                    name: "Bob Jones".to_string(),
                    external_id: Some("openalex:B1".to_string()),
                    ..Default::default()
                },
            ],
            affiliations: vec![
                Affiliation {
                    name: "MIT".to_string(),
                    ..Default::default()
                },
            ],
            concepts: vec!["AI".to_string()],
            identifiers: vec![
                Identifier {
                    scheme: "doi".to_string(),
                    value: "10.1234/test".to_string(),
                },
            ],
            ..Default::default()
        }
    }

    #[test]
    fn test_authored_by_relationships() {
        let pub_ = two_author_pub();
        let rels = compute_relationships(42, "pub:42", &pub_, None);
        let authored: Vec<_> = rels.iter().filter(|r| r.relation_type == "authored-by").collect();
        assert_eq!(authored.len(), 2);
    }

    #[test]
    fn test_published_in_relationship() {
        let pub_ = two_author_pub();
        let rels = compute_relationships(42, "pub:42", &pub_, None);
        let pub_in: Vec<_> = rels.iter().filter(|r| r.relation_type == "published-in").collect();
        assert_eq!(pub_in.len(), 1);
        assert!(pub_in[0].target_canonical_id.starts_with("journal:"));
    }

    #[test]
    fn test_has_concept_relationship() {
        let pub_ = two_author_pub();
        let rels = compute_relationships(42, "pub:42", &pub_, None);
        let concepts: Vec<_> = rels.iter().filter(|r| r.relation_type == "has-concept").collect();
        assert_eq!(concepts.len(), 1);
    }

    #[test]
    fn test_identified_by_relationship() {
        let pub_ = two_author_pub();
        let rels = compute_relationships(42, "pub:42", &pub_, None);
        let ids: Vec<_> = rels.iter().filter(|r| r.relation_type == "identified-by").collect();
        assert_eq!(ids.len(), 1);
    }

    #[test]
    fn test_coauthor_pairs_ordered() {
        let pub_ = two_author_pub();
        let rels = compute_relationships(42, "pub:42", &pub_, None);
        let coauthors: Vec<_> = rels.iter().filter(|r| r.relation_type == "coauthor-with").collect();
        // 2 authors → 1 pair
        assert_eq!(coauthors.len(), 1);
        // Pair should be ordered (source_canonical_id < target_canonical_id)
        assert!(coauthors[0].source_canonical_id <= coauthors[0].target_canonical_id);
    }

    #[test]
    fn test_three_authors_coauthor_count() {
        let mut pub_ = two_author_pub();
        pub_.authors.push(Author {
            name: "Carol White".to_string(),
            ..Default::default()
        });
        let rels = compute_relationships(42, "pub:42", &pub_, None);
        let coauthors: Vec<_> = rels.iter().filter(|r| r.relation_type == "coauthor-with").collect();
        // 3 authors → 3 pairs (3*2/2)
        assert_eq!(coauthors.len(), 3);
    }
}
