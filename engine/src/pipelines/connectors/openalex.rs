//! OpenAlex connector: search and DOI resolution via the OpenAlex API.

use reqwest::Client;
use serde::Deserialize;

use super::rate_limiter::RateLimiter;
use super::retry::{is_retryable, retry_delay, RetryConfig};
use crate::proto::Publication;

const BASE_URL: &str = "https://api.openalex.org";

/// Fetch publications from OpenAlex by DOI, title search, or general query.
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
        limiter.acquire("openalex").await;

        let url = match query_type {
            "doi" => format!("{}/works/doi:{}", BASE_URL, query),
            "search" | "title" => format!(
                "{}/works?search={}&per_page={}",
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
                        if query_type == "doi" {
                            match super::guarded_json::<OpenAlexWork>(resp).await {
                                Ok(work) => {
                                    publications.push(work.into_publication());
                                }
                                Err(e) => last_err = e,
                            }
                        } else {
                            match super::guarded_json::<OpenAlexResults>(resp).await {
                                Ok(results) => {
                                    for work in results.results {
                                        publications.push(work.into_publication());
                                    }
                                }
                                Err(e) => last_err = e,
                            }
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
            tracing::warn!(source = "openalex", query = %query, error = %last_err, "fetch failed");
        }
    }

    Ok(publications)
}

#[derive(Deserialize)]
struct OpenAlexResults {
    results: Vec<OpenAlexWork>,
}

#[derive(Deserialize)]
struct OpenAlexWork {
    #[serde(default)]
    title: Option<String>,
    #[serde(default)]
    doi: Option<String>,
    #[serde(default)]
    publication_year: Option<i32>,
    #[serde(default)]
    cited_by_count: Option<i32>,
    #[serde(rename = "type", default)]
    work_type: Option<String>,
    #[serde(default)]
    primary_location: Option<PrimaryLocation>,
    #[serde(default)]
    authorships: Vec<Authorship>,
    #[serde(default)]
    concepts: Vec<Concept>,
}

#[derive(Deserialize, Default)]
struct PrimaryLocation {
    #[serde(default)]
    source: Option<Source>,
}

#[derive(Deserialize, Default)]
struct Source {
    #[serde(default)]
    display_name: Option<String>,
    #[serde(default)]
    publisher: Option<String>,
}

#[derive(Deserialize)]
struct Authorship {
    #[serde(default)]
    author: Option<AuthorInfo>,
}

#[derive(Deserialize)]
struct AuthorInfo {
    #[serde(default)]
    display_name: Option<String>,
}

#[derive(Deserialize)]
struct Concept {
    #[serde(default)]
    display_name: Option<String>,
}

impl OpenAlexWork {
    fn into_publication(self) -> Publication {
        let source_title = self
            .primary_location
            .as_ref()
            .and_then(|l| l.source.as_ref())
            .and_then(|s| s.display_name.clone());

        let publisher = self
            .primary_location
            .as_ref()
            .and_then(|l| l.source.as_ref())
            .and_then(|s| s.publisher.clone());

        let authors: Vec<crate::proto::Author> = self
            .authorships
            .iter()
            .filter_map(|a| {
                a.author.as_ref().and_then(|info| {
                    info.display_name.as_ref().map(|name| crate::proto::Author {
                        name: name.clone(),
                        orcid: None,
                        order: None,
                        external_id: None,
                        affiliations: vec![],
                    })
                })
            })
            .collect();

        let concepts: Vec<String> = self
            .concepts
            .iter()
            .filter_map(|c| c.display_name.clone())
            .collect();

        Publication {
            entity_id: 0,
            title: self.title.unwrap_or_default(),
            doi: self.doi,
            year: self.publication_year,
            abstract_text: None,
            source_title,
            publisher,
            publication_type: self.work_type,
            citation_count: self.cited_by_count,
            reference_count: None,
            authors,
            affiliations: vec![],
            identifiers: vec![],
            concepts,
            enrichment_source: Some("openalex".to_string()),
            attributes_json: None,
            enrichment_doi: None,
        }
    }
}
