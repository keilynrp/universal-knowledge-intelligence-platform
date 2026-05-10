use regex::Regex;
use std::sync::LazyLock;

static SLUG_RE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[^a-z0-9]+").unwrap());

pub fn slug(value: &str) -> String {
    use unicode_normalization::UnicodeNormalization;
    // NFD decompose then strip combining marks (diacritics) before lowercasing
    let normalized: String = value
        .nfd()
        .filter(|c| !unicode_normalization::char::is_combining_mark(*c))
        .collect();
    let lower = normalized.to_lowercase();
    let slugged = SLUG_RE.replace_all(&lower, "-");
    slugged.trim_matches('-').to_string()
}

pub fn author_canonical_id(author: &crate::proto::Author) -> String {
    if let Some(orcid) = &author.orcid {
        if !orcid.is_empty() {
            return format!("orcid:{orcid}");
        }
    }
    if let Some(ext) = &author.external_id {
        if !ext.is_empty() {
            return format!("author:{ext}");
        }
    }
    format!("author:{}", slug(&author.name))
}

pub fn affiliation_canonical_id(aff: &crate::proto::Affiliation) -> String {
    if let Some(ext) = &aff.external_id {
        if !ext.is_empty() {
            return format!("affiliation:{ext}");
        }
    }
    affiliation_name_canonical_id(&aff.name)
}

pub fn affiliation_name_canonical_id(name: &str) -> String {
    format!("affiliation:{}", slug(name))
}

pub fn publication_canonical_id(pub_: &crate::proto::Publication) -> String {
    if let Some(doi) = pub_.doi.as_deref().filter(|doi| !doi.trim().is_empty()) {
        return format!("publication:doi:{}", slug(doi));
    }
    if let Some(enrichment_doi) = pub_
        .enrichment_doi
        .as_deref()
        .filter(|doi| !doi.trim().is_empty())
    {
        return format!("publication:doi:{}", slug(enrichment_doi));
    }
    format!("pub:{}", pub_.entity_id)
}

pub fn journal_canonical_id(source_title: &str) -> String {
    format!("journal:{}", slug(source_title))
}

pub fn concept_canonical_id(concept: &str) -> String {
    format!("concept:{}", slug(concept))
}

pub fn identifier_canonical_id(scheme: &str, value: &str) -> String {
    format!("{scheme}:{value}")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_author_canonical_with_orcid() {
        let author = crate::proto::Author {
            name: "Alice Smith".into(),
            orcid: Some("0000-0001-0000-0001".into()),
            external_id: Some("A1".into()),
            ..Default::default()
        };
        assert_eq!(author_canonical_id(&author), "orcid:0000-0001-0000-0001");
    }

    #[test]
    fn test_author_canonical_with_external_id() {
        let author = crate::proto::Author {
            name: "Bob Jones".into(),
            external_id: Some("https://openalex.org/A123".into()),
            ..Default::default()
        };
        assert_eq!(
            author_canonical_id(&author),
            "author:https://openalex.org/A123"
        );
    }

    #[test]
    fn test_author_canonical_name_only() {
        let author = crate::proto::Author {
            name: "Dr. María García-López".into(),
            ..Default::default()
        };
        // After NFD decomposition and diacritic removal: "dr-mar-a-garc-a-l-pez"
        let result = author_canonical_id(&author);
        assert!(result.starts_with("author:"));
        assert!(result.contains("mar"));
    }

    #[test]
    fn test_slug_normalization() {
        assert_eq!(slug("Hello  World!!"), "hello-world");
        assert_eq!(slug("  spaces  "), "spaces");
        assert_eq!(slug("café résumé"), "cafe-resume");
    }

    #[test]
    fn test_concept_canonical_id() {
        assert_eq!(
            concept_canonical_id("Machine Learning"),
            "concept:machine-learning"
        );
    }

    #[test]
    fn test_journal_canonical_id() {
        assert_eq!(
            journal_canonical_id("Nature Reviews"),
            "journal:nature-reviews"
        );
    }

    #[test]
    fn test_affiliation_canonical_with_external_id() {
        let aff = crate::proto::Affiliation {
            name: "MIT".into(),
            external_id: Some("https://openalex.org/I1".into()),
            ..Default::default()
        };
        assert_eq!(
            affiliation_canonical_id(&aff),
            "affiliation:https://openalex.org/I1"
        );
    }

    #[test]
    fn test_affiliation_canonical_name_only() {
        let aff = crate::proto::Affiliation {
            name: "MIT".into(),
            ..Default::default()
        };
        assert_eq!(affiliation_canonical_id(&aff), "affiliation:mit");
    }

    #[test]
    fn test_publication_canonical_prefers_doi() {
        let pub_ = crate::proto::Publication {
            entity_id: 7,
            doi: Some("10.1234/example".into()),
            ..Default::default()
        };
        assert_eq!(
            publication_canonical_id(&pub_),
            "publication:doi:10-1234-example"
        );
    }
}
