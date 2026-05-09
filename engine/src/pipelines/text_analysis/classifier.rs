/// Classification result for an entity type.
#[derive(Debug, Clone)]
pub struct Classification {
    pub entity_type: String,
    pub confidence: f32,
}

/// Rule-based entity type classifier.
/// Classifies a publication based on DOI prefix, source title, and publisher.
pub fn classify(
    doi: Option<&str>,
    source_title: Option<&str>,
    publisher: Option<&str>,
) -> Classification {
    // 1. Check DOI prefix for preprint servers
    if let Some(doi) = doi {
        let doi_lower = doi.to_lowercase();
        if doi_lower.starts_with("10.48550/arxiv") || doi_lower.contains("arxiv") {
            return Classification {
                entity_type: "preprint".to_string(),
                confidence: 0.95,
            };
        }
        if doi_lower.starts_with("10.1101/") {
            // bioRxiv / medRxiv
            return Classification {
                entity_type: "preprint".to_string(),
                confidence: 0.95,
            };
        }
        if doi_lower.starts_with("10.20944/") {
            // Preprints.org
            return Classification {
                entity_type: "preprint".to_string(),
                confidence: 0.90,
            };
        }
    }

    // 2. Check source title for conference indicators
    if let Some(title) = source_title {
        let title_lower = title.to_lowercase();
        if title_lower.contains("proceedings")
            || title_lower.contains("conference")
            || title_lower.contains("symposium")
            || title_lower.contains("workshop")
            || title_lower.contains("acl")
            || title_lower.contains("nips")
            || title_lower.contains("icml")
            || title_lower.contains("cvpr")
            || title_lower.contains("iccv")
            || title_lower.contains("aaai")
        {
            return Classification {
                entity_type: "conference_paper".to_string(),
                confidence: 0.85,
            };
        }

        // Check for book chapters
        if title_lower.contains("handbook")
            || title_lower.contains("textbook")
            || title_lower.contains("book chapter")
        {
            return Classification {
                entity_type: "book_chapter".to_string(),
                confidence: 0.80,
            };
        }

        // Source title present but doesn't match above — likely journal article
        return Classification {
            entity_type: "journal_article".to_string(),
            confidence: 0.75,
        };
    }

    // 3. Check publisher for book indicators
    if let Some(pub_) = publisher {
        let pub_lower = pub_.to_lowercase();
        if pub_lower.contains("springer")
            || pub_lower.contains("elsevier")
            || pub_lower.contains("wiley")
            || pub_lower.contains("taylor")
        {
            return Classification {
                entity_type: "journal_article".to_string(),
                confidence: 0.70,
            };
        }
    }

    // 4. Default: preprint (unknown source)
    Classification {
        entity_type: "preprint".to_string(),
        confidence: 0.60,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_arxiv_preprint_by_doi() {
        let result = classify(Some("10.48550/arXiv.2301.00001"), None, None);
        assert_eq!(result.entity_type, "preprint");
        assert!(result.confidence >= 0.9);
    }

    #[test]
    fn test_biorxiv_preprint() {
        let result = classify(Some("10.1101/2023.01.01.524000"), None, None);
        assert_eq!(result.entity_type, "preprint");
        assert!(result.confidence >= 0.9);
    }

    #[test]
    fn test_conference_paper() {
        let result = classify(None, Some("Proceedings of ACL 2024"), None);
        assert_eq!(result.entity_type, "conference_paper");
    }

    #[test]
    fn test_journal_article_with_source() {
        let result = classify(Some("10.1234/some-doi"), Some("Nature Communications"), None);
        assert_eq!(result.entity_type, "journal_article");
    }

    #[test]
    fn test_no_source_no_publisher_is_preprint() {
        let result = classify(None, None, None);
        assert_eq!(result.entity_type, "preprint");
        assert!(result.confidence >= 0.6);
    }

    #[test]
    fn test_publisher_fallback() {
        let result = classify(None, None, Some("Elsevier"));
        assert_eq!(result.entity_type, "journal_article");
    }
}
