pub mod classifier;
pub mod keywords;
pub mod language;
pub mod tokenizer;

use std::collections::HashMap;
use async_trait::async_trait;

use crate::pipelines::{Pipeline, PipelineContext, PipelineError, PipelineInput, PipelineOutput};

pub struct TextAnalysisPipeline;

#[async_trait]
impl Pipeline for TextAnalysisPipeline {
    fn name(&self) -> &'static str {
        "text_analysis"
    }

    async fn process(
        &self,
        input: PipelineInput,
        ctx: &PipelineContext,
    ) -> Result<PipelineOutput, PipelineError> {
        ctx.progress.update(0.1, "tokenizing", "Tokenizing abstracts").await;

        let mut all_tokens: Vec<Vec<String>> = Vec::new();
        let mut entity_ids: Vec<i64> = Vec::new();
        let mut languages: Vec<Option<String>> = Vec::new();
        let mut classifications: Vec<classifier::Classification> = Vec::new();

        for pub_ in &input.publications {
            let text = pub_
                .abstract_text
                .as_deref()
                .map(|a| format!("{} {}", pub_.title, a))
                .unwrap_or_else(|| pub_.title.clone());

            let tokens = tokenizer::tokenize(&text);
            all_tokens.push(tokens);
            entity_ids.push(pub_.entity_id);

            let lang = language::detect_language(&text);
            languages.push(lang);

            let classification = classifier::classify(
                pub_.doi.as_deref(),
                pub_.source_title.as_deref(),
                pub_.publisher.as_deref(),
            );
            classifications.push(classification);
        }

        ctx.progress.update(0.4, "extracting_keywords", "Extracting keywords").await;

        // TF-IDF over corpus
        let extractor = keywords::TfIdfExtractor::new(10, 0.0, 0.95);
        let keyword_results = extractor.extract(&all_tokens);

        let keywords_extracted = keyword_results.iter().map(|kws| kws.len() as i32).sum();
        let entities_classified = classifications.len() as i32;

        ctx.progress.update(0.8, "writing_results", "Updating DB with analysis results").await;

        // Write results back via batch UPDATE using unnest
        if !entity_ids.is_empty() {
            let keyword_jsons: Vec<String> = keyword_results
                .iter()
                .map(|kws| {
                    serde_json::to_string(
                        &kws.iter()
                            .map(|(w, s)| serde_json::json!({"word": w, "score": s}))
                            .collect::<Vec<_>>(),
                    )
                    .unwrap_or_else(|_| "[]".to_string())
                })
                .collect();

            let entity_type_vec: Vec<String> = classifications
                .iter()
                .map(|c| c.entity_type.clone())
                .collect();

            // Batch UPDATE via unnest — PostgreSQL only
            sqlx::query(
                "UPDATE raw_entities SET
                    enrichment_concepts = u.keywords,
                    entity_type = COALESCE(NULLIF(raw_entities.entity_type, ''), u.entity_type)
                 FROM UNNEST($1::bigint[], $2::text[], $3::text[]) AS u(id, keywords, entity_type)
                 WHERE raw_entities.id = u.id",
            )
            .bind(&entity_ids)
            .bind(&keyword_jsons)
            .bind(&entity_type_vec)
            .execute(&ctx.pool)
            .await
            .map_err(PipelineError::Database)?;
        }

        ctx.progress.update(1.0, "done", "Text analysis complete").await;

        Ok(PipelineOutput {
            nodes_created: 0,
            nodes_deduplicated: 0,
            relationships_created: 0,
            relationships_deduplicated: 0,
            keywords_extracted,
            entities_classified,
            counters: HashMap::new(),
        })
    }
}
