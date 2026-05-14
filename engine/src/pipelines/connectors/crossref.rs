//! Crossref connector: DOI resolution and metadata extraction.

use reqwest::Client;
use serde::Deserialize;

use super::rate_limiter::RateLimiter;
use super::retry::{is_retryable, retry_delay, RetryConfig};
use crate::proto::Publication;

const BASE_URL: &str = "https://api.crossref.org";

/// Fetch publications from Crossref by DOI or title search.
pub async fn fetch(
    client: &Client,
    limiter: &RateLimiter,
    query_type: &str,
    queries: &[String],
    limit: usize,
) -> Result<Vec<Publication>, String> {
    let mut publications = Vec::new();
    let retry_config = RetryConfig::default();

    for query in queries {
        limiter.acquire("crossref").await;

        let url = match query_type {
            "doi" => format!("{}/works/{}", BASE_URL, query),
            "search" | "title" => format!(
                "{}/works?query={}&rows={}",
                BASE_URL,
                urlencoding::encode(query),
                limit.min(50)
            ),
            _ => return Err(format!("unsupported query_type: {}", query_type)),
        };

        let mut last_err = String::new();
        for attempt in 0..=retry_config.max_retries {
            if attempt > 0 {
                tokio::time::sleep(retry_delay(&retry_config, attempt - 1)).await;
            }

            match client.get(&url).send().await {
                Ok(resp) => {
                    if resp.status().is_success() {
                        match super::guarded_json::<CrossrefResponse>(resp).await {
                            Ok(cr) => {
                                if let Some(msg) = cr.message {
                                    match msg {
                                        CrossrefMessage::Single(item) => {
                                            publications.push(item.into_publication());
                                        }
                                        CrossrefMessage::List { items } => {
                                            for item in items {
                                                publications.push(item.into_publication());
                                            }
                                        }
                                    }
                                }
                            }
                            Err(e) => last_err = e,
                        }
                        break;
                    } else if is_retryable(resp.status()) {
                        last_err = format!("HTTP {}", resp.status());
                        continue;
                    } else {
                        last_err = format!("HTTP {}", resp.status());
                        break;
                    }
                }
                Err(e) => {
                    last_err = format!("request error: {}", e);
                    continue;
                }
            }
        }

        if !last_err.is_empty() && publications.is_empty() {
            tracing::warn!(source = "crossref", query = %query, error = %last_err, "fetch failed");
        }
    }

    Ok(publications)
}

#[derive(Deserialize)]
struct CrossrefResponse {
    message: Option<CrossrefMessage>,
}

#[derive(Deserialize)]
#[serde(untagged)]
enum CrossrefMessage {
    Single(CrossrefItem),
    List { items: Vec<CrossrefItem> },
}

#[derive(Deserialize)]
struct CrossrefItem {
    #[serde(default, rename = "DOI")]
    doi: Option<String>,
    #[serde(default)]
    title: Option<Vec<String>>,
    #[serde(default)]
    publisher: Option<String>,
    #[serde(rename = "type", default)]
    work_type: Option<String>,
    #[serde(default, rename = "is-referenced-by-count")]
    citation_count: Option<i32>,
    #[serde(default, rename = "references-count")]
    reference_count: Option<i32>,
    #[serde(default)]
    author: Option<Vec<CrossrefAuthor>>,
    #[serde(default, rename = "container-title")]
    container_title: Option<Vec<String>>,
    #[serde(default)]
    published: Option<DateParts>,
}

#[derive(Deserialize)]
struct CrossrefAuthor {
    #[serde(default)]
    given: Option<String>,
    #[serde(default)]
    family: Option<String>,
    #[serde(default, rename = "ORCID")]
    orcid: Option<String>,
    #[serde(default)]
    #[allow(dead_code)]
    sequence: Option<String>,
}

#[derive(Deserialize)]
struct DateParts {
    #[serde(default, rename = "date-parts")]
    date_parts: Option<Vec<Vec<i32>>>,
}

impl CrossrefItem {
    fn into_publication(self) -> Publication {
        let title = self
            .title
            .as_ref()
            .and_then(|t| t.first().cloned())
            .unwrap_or_default();

        let year = self.published.and_then(|d| {
            d.date_parts
                .and_then(|parts| parts.first().and_then(|p| p.first().copied()))
        });

        let source_title = self
            .container_title
            .as_ref()
            .and_then(|c| c.first().cloned());

        let authors: Vec<crate::proto::Author> = self
            .author
            .unwrap_or_default()
            .into_iter()
            .map(|a| {
                let name = match (&a.given, &a.family) {
                    (Some(g), Some(f)) => format!("{} {}", g, f),
                    (None, Some(f)) => f.clone(),
                    (Some(g), None) => g.clone(),
                    (None, None) => String::new(),
                };
                crate::proto::Author {
                    name,
                    orcid: a.orcid,
                    order: None,
                    external_id: None,
                    affiliations: vec![],
                }
            })
            .collect();

        Publication {
            entity_id: 0,
            title,
            doi: self.doi,
            year,
            abstract_text: None,
            source_title,
            publisher: self.publisher,
            publication_type: self.work_type,
            citation_count: self.citation_count,
            reference_count: self.reference_count,
            authors,
            affiliations: vec![],
            identifiers: vec![],
            concepts: vec![],
            enrichment_source: Some("crossref".to_string()),
            attributes_json: None,
            enrichment_doi: None,
        }
    }
}
