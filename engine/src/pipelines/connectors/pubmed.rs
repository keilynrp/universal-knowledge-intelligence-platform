//! PubMed connector: E-utilities API for PMID lookup and search.

use reqwest::Client;
use serde::Deserialize;

use super::rate_limiter::RateLimiter;
use super::retry::{is_retryable, retry_delay, RetryConfig};
use crate::proto::Publication;

const ESEARCH_URL: &str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi";
const ESUMMARY_URL: &str = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi";

/// Fetch publications from PubMed by PMID or search query.
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
        limiter.acquire("pubmed").await;

        let pmids = match query_type {
            "pmid" => vec![query.clone()],
            "search" | "title" => search_pmids(client, query, limit, &retry_config).await?,
            _ => return Err(format!("unsupported query_type: {}", query_type)),
        };

        for pmid in &pmids {
            limiter.acquire("pubmed").await;
            match fetch_summary(client, pmid, &retry_config).await {
                Ok(Some(pub_)) => publications.push(pub_),
                Ok(None) => {}
                Err(e) => {
                    tracing::warn!(source = "pubmed", pmid = %pmid, error = %e, "fetch failed");
                }
            }
        }
    }

    Ok(publications)
}

async fn search_pmids(
    client: &Client,
    query: &str,
    limit: usize,
    retry_config: &RetryConfig,
) -> Result<Vec<String>, String> {
    let url = format!(
        "{}?db=pubmed&retmode=json&retmax={}&term={}",
        ESEARCH_URL,
        limit.min(50),
        urlencoding::encode(query)
    );

    for attempt in 0..=retry_config.max_retries {
        if attempt > 0 {
            tokio::time::sleep(retry_delay(retry_config, attempt - 1)).await;
        }

        match client.get(&url).send().await {
            Ok(resp) => {
                if resp.status().is_success() {
                    match resp.json::<ESearchResult>().await {
                        Ok(result) => {
                            return Ok(result
                                .esearchresult
                                .map(|r| r.idlist)
                                .unwrap_or_default());
                        }
                        Err(e) => return Err(format!("json parse: {}", e)),
                    }
                } else if is_retryable(resp.status()) {
                    continue;
                } else {
                    return Err(format!("HTTP {}", resp.status()));
                }
            }
            Err(e) => {
                if attempt == retry_config.max_retries {
                    return Err(format!("request error: {}", e));
                }
                continue;
            }
        }
    }

    Err("max retries exceeded".to_string())
}

async fn fetch_summary(
    client: &Client,
    pmid: &str,
    retry_config: &RetryConfig,
) -> Result<Option<Publication>, String> {
    let url = format!("{}?db=pubmed&retmode=json&id={}", ESUMMARY_URL, pmid);

    for attempt in 0..=retry_config.max_retries {
        if attempt > 0 {
            tokio::time::sleep(retry_delay(retry_config, attempt - 1)).await;
        }

        match client.get(&url).send().await {
            Ok(resp) => {
                if resp.status().is_success() {
                    match resp.json::<ESummaryResult>().await {
                        Ok(result) => {
                            if let Some(summary) = result.result.and_then(|r| r.get(pmid).cloned())
                            {
                                return Ok(Some(summary.into_publication(pmid)));
                            }
                            return Ok(None);
                        }
                        Err(e) => return Err(format!("json parse: {}", e)),
                    }
                } else if is_retryable(resp.status()) {
                    continue;
                } else {
                    return Err(format!("HTTP {}", resp.status()));
                }
            }
            Err(e) => {
                if attempt == retry_config.max_retries {
                    return Err(format!("request error: {}", e));
                }
                continue;
            }
        }
    }

    Err("max retries exceeded".to_string())
}

#[derive(Deserialize)]
struct ESearchResult {
    esearchresult: Option<ESearchInner>,
}

#[derive(Deserialize)]
struct ESearchInner {
    #[serde(default)]
    idlist: Vec<String>,
}

#[derive(Deserialize)]
struct ESummaryResult {
    result: Option<std::collections::HashMap<String, PubMedSummary>>,
}

#[derive(Deserialize, Clone)]
struct PubMedSummary {
    #[serde(default)]
    title: Option<String>,
    #[serde(default)]
    source: Option<String>,
    #[serde(default)]
    pubdate: Option<String>,
    #[serde(default)]
    authors: Option<Vec<PubMedAuthor>>,
    #[serde(default)]
    articleids: Option<Vec<ArticleId>>,
}

#[derive(Deserialize, Clone)]
struct PubMedAuthor {
    #[serde(default)]
    name: Option<String>,
}

#[derive(Deserialize, Clone)]
struct ArticleId {
    #[serde(default)]
    idtype: Option<String>,
    #[serde(default)]
    value: Option<String>,
}

impl PubMedSummary {
    fn into_publication(self, pmid: &str) -> Publication {
        let doi = self
            .articleids
            .as_ref()
            .and_then(|ids| {
                ids.iter()
                    .find(|id| id.idtype.as_deref() == Some("doi"))
                    .and_then(|id| id.value.clone())
            });

        let year = self.pubdate.as_ref().and_then(|d| {
            d.split_whitespace()
                .next()
                .and_then(|y| y.parse::<i32>().ok())
        });

        let authors: Vec<crate::proto::Author> = self
            .authors
            .unwrap_or_default()
            .into_iter()
            .filter_map(|a| {
                a.name.map(|name| crate::proto::Author {
                    name,
                    orcid: None,
                    order: None,
                    external_id: None,
                    affiliations: vec![],
                })
            })
            .collect();

        let identifiers = vec![crate::proto::Identifier {
            scheme: "pmid".to_string(),
            value: pmid.to_string(),
        }];

        Publication {
            entity_id: 0,
            title: self.title.unwrap_or_default(),
            doi,
            year,
            abstract_text: None,
            source_title: self.source,
            publisher: None,
            publication_type: None,
            citation_count: None,
            reference_count: None,
            authors,
            affiliations: vec![],
            identifiers,
            concepts: vec![],
            enrichment_source: Some("pubmed".to_string()),
            attributes_json: None,
            enrichment_doi: None,
        }
    }
}
