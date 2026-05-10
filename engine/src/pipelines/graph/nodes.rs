use super::canonical;
use crate::db::schema::PendingNode;
use crate::proto::Publication;

pub fn extract_nodes(
    pub_: &Publication,
    org_id: Option<i64>,
    import_batch_id: i64,
    domain: &str,
) -> Vec<PendingNode> {
    let mut nodes = Vec::new();
    let source = "graph_materializer".to_string();

    nodes.push(PendingNode {
        org_id,
        import_batch_id: Some(import_batch_id),
        domain: domain.to_string(),
        entity_type: "publication".to_string(),
        primary_label: pub_.title.clone(),
        secondary_label: pub_.year.map(|year| year.to_string()),
        canonical_id: canonical::publication_canonical_id(pub_),
        attributes_json: serde_json::json!({
            "doi": pub_.doi,
            "year": pub_.year,
            "publication_type": pub_.publication_type,
            "citation_count": pub_.citation_count,
            "reference_count": pub_.reference_count,
            "enrichment_doi": pub_.enrichment_doi,
        })
        .to_string(),
        source: source.clone(),
        enrichment_source: pub_.enrichment_source.clone(),
        enrichment_concepts: None,
    });

    // Authors
    for author in &pub_.authors {
        let canonical_id = canonical::author_canonical_id(author);
        nodes.push(PendingNode {
            org_id,
            import_batch_id: Some(import_batch_id),
            domain: domain.to_string(),
            entity_type: "author".to_string(),
            primary_label: author.name.clone(),
            secondary_label: None,
            canonical_id,
            attributes_json: serde_json::json!({
                "orcid": author.orcid,
                "external_id": author.external_id,
                "order": author.order,
            })
            .to_string(),
            source: source.clone(),
            enrichment_source: None,
            enrichment_concepts: None,
        });
    }

    // Affiliations (from both pub_.affiliations and author.affiliations strings)
    for aff in &pub_.affiliations {
        let canonical_id = canonical::affiliation_canonical_id(aff);
        nodes.push(PendingNode {
            org_id,
            import_batch_id: Some(import_batch_id),
            domain: domain.to_string(),
            entity_type: "affiliation".to_string(),
            primary_label: aff.name.clone(),
            secondary_label: aff.country.clone(),
            canonical_id,
            attributes_json: serde_json::json!({
                "country": aff.country,
                "external_id": aff.external_id,
            })
            .to_string(),
            source: source.clone(),
            enrichment_source: None,
            enrichment_concepts: None,
        });
    }
    for author in &pub_.authors {
        for aff_name in &author.affiliations {
            if !aff_name.trim().is_empty() {
                let canonical_id = canonical::affiliation_name_canonical_id(aff_name);
                nodes.push(PendingNode {
                    org_id,
                    import_batch_id: Some(import_batch_id),
                    domain: domain.to_string(),
                    entity_type: "affiliation".to_string(),
                    primary_label: aff_name.clone(),
                    secondary_label: None,
                    canonical_id,
                    attributes_json: "{}".to_string(),
                    source: source.clone(),
                    enrichment_source: None,
                    enrichment_concepts: None,
                });
            }
        }
    }

    // Journal / source
    if let Some(source_title) = &pub_.source_title {
        if !source_title.is_empty() {
            let canonical_id = canonical::journal_canonical_id(source_title);
            nodes.push(PendingNode {
                org_id,
                import_batch_id: Some(import_batch_id),
                domain: domain.to_string(),
                entity_type: "journal".to_string(),
                primary_label: source_title.clone(),
                secondary_label: pub_.publisher.clone(),
                canonical_id,
                attributes_json: serde_json::json!({
                    "publisher": pub_.publisher,
                })
                .to_string(),
                source: source.clone(),
                enrichment_source: None,
                enrichment_concepts: None,
            });
        }
    }

    // Concepts
    for concept in &pub_.concepts {
        if !concept.is_empty() {
            let canonical_id = canonical::concept_canonical_id(concept);
            nodes.push(PendingNode {
                org_id,
                import_batch_id: Some(import_batch_id),
                domain: domain.to_string(),
                entity_type: "concept".to_string(),
                primary_label: concept.clone(),
                secondary_label: None,
                canonical_id,
                attributes_json: "{}".to_string(),
                source: source.clone(),
                enrichment_source: None,
                enrichment_concepts: None,
            });
        }
    }

    // Identifiers
    for id in &pub_.identifiers {
        if !id.value.is_empty() {
            let canonical_id = canonical::identifier_canonical_id(&id.scheme, &id.value);
            nodes.push(PendingNode {
                org_id,
                import_batch_id: Some(import_batch_id),
                domain: domain.to_string(),
                entity_type: "identifier".to_string(),
                primary_label: id.value.clone(),
                secondary_label: Some(id.scheme.clone()),
                canonical_id,
                attributes_json: serde_json::json!({
                    "scheme": id.scheme,
                    "value": id.value,
                })
                .to_string(),
                source: source.clone(),
                enrichment_source: None,
                enrichment_concepts: None,
            });
        }
    }

    nodes
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::proto::{Affiliation, Author};

    fn make_pub() -> Publication {
        Publication {
            entity_id: 1,
            title: "Test Paper".to_string(),
            authors: vec![
                Author {
                    name: "Alice Smith".to_string(),
                    order: Some(1),
                    orcid: Some("0000-0001-0000-0001".to_string()),
                    ..Default::default()
                },
                Author {
                    name: "Bob Jones".to_string(),
                    order: Some(2),
                    ..Default::default()
                },
            ],
            affiliations: vec![Affiliation {
                name: "MIT".to_string(),
                country: Some("US".to_string()),
                ..Default::default()
            }],
            source_title: Some("Nature Reviews".to_string()),
            concepts: vec!["Machine Learning".to_string(), "AI".to_string()],
            ..Default::default()
        }
    }

    #[test]
    fn test_extract_nodes_returns_authors() {
        let pub_ = make_pub();
        let nodes = extract_nodes(&pub_, None, 1, "science");
        let author_nodes: Vec<_> = nodes.iter().filter(|n| n.entity_type == "author").collect();
        assert_eq!(author_nodes.len(), 2);
    }

    #[test]
    fn test_extract_nodes_returns_publication() {
        let pub_ = make_pub();
        let nodes = extract_nodes(&pub_, None, 1, "science");
        let publication_nodes: Vec<_> = nodes
            .iter()
            .filter(|n| n.entity_type == "publication")
            .collect();
        assert_eq!(publication_nodes.len(), 1);
        assert_eq!(publication_nodes[0].canonical_id, "pub:1");
    }

    #[test]
    fn test_extract_nodes_returns_journal() {
        let pub_ = make_pub();
        let nodes = extract_nodes(&pub_, None, 1, "science");
        let journal_nodes: Vec<_> = nodes
            .iter()
            .filter(|n| n.entity_type == "journal")
            .collect();
        assert_eq!(journal_nodes.len(), 1);
        assert_eq!(journal_nodes[0].primary_label, "Nature Reviews");
    }

    #[test]
    fn test_extract_nodes_returns_concepts() {
        let pub_ = make_pub();
        let nodes = extract_nodes(&pub_, None, 1, "science");
        let concept_nodes: Vec<_> = nodes
            .iter()
            .filter(|n| n.entity_type == "concept")
            .collect();
        assert_eq!(concept_nodes.len(), 2);
    }

    #[test]
    fn test_extract_nodes_affiliation_dedup() {
        let mut pub_ = make_pub();
        // Same affiliation for two different entries
        pub_.affiliations.push(crate::proto::Affiliation {
            name: "MIT".to_string(),
            country: Some("US".to_string()),
            ..Default::default()
        });
        let nodes = extract_nodes(&pub_, None, 1, "science");
        let aff_nodes: Vec<_> = nodes
            .iter()
            .filter(|n| n.entity_type == "affiliation")
            .collect();
        // Raw extraction returns 2 (dedup happens at the pipeline level via HashMap)
        assert_eq!(aff_nodes.len(), 2);
    }

    #[test]
    fn test_extract_nodes_includes_author_affiliation_strings() {
        let mut pub_ = make_pub();
        pub_.authors[0]
            .affiliations
            .push("Stanford University".to_string());
        let nodes = extract_nodes(&pub_, None, 1, "science");
        assert!(nodes.iter().any(|n| {
            n.entity_type == "affiliation" && n.canonical_id == "affiliation:stanford-university"
        }));
    }
}
