use std::collections::HashMap;

use regex::Regex;

use crate::pipelines::{
    ComputePayload, ComputeResult, Pipeline, PipelineCategory, PipelineContext, PipelineError,
    PipelineInput, PipelineOutput, ValidationError,
};
use crate::proto::NormalizationResponse;

use crate::pipelines::authority::normalize::{name_variants, normalize_name, strip_diacritics};

const VALID_MODES: &[&str] = &["unicode", "name_variants", "rules"];

pub struct NormalizationPipeline;

#[async_trait::async_trait]
impl Pipeline for NormalizationPipeline {
    fn name(&self) -> &'static str {
        "compute_normalization"
    }

    fn category(&self) -> PipelineCategory {
        PipelineCategory::Compute
    }

    fn validate(&self, input: &PipelineInput) -> Result<(), ValidationError> {
        match &input.payload {
            Some(ComputePayload::Normalization(req)) => {
                if req.values.is_empty() {
                    return Err(ValidationError::EmptyInput);
                }
                if !VALID_MODES.contains(&req.mode.as_str()) {
                    return Err(ValidationError::InvalidField(format!(
                        "invalid mode '{}', expected one of: {:?}",
                        req.mode, VALID_MODES
                    )));
                }
                if req.mode == "rules" && req.rules.is_empty() {
                    return Err(ValidationError::InvalidField(
                        "rules mode requires at least one rule".to_string(),
                    ));
                }
                Ok(())
            }
            _ => Err(ValidationError::EmptyInput),
        }
    }

    async fn process(
        &self,
        input: PipelineInput,
        ctx: &PipelineContext,
    ) -> Result<PipelineOutput, PipelineError> {
        let req = match input.payload {
            Some(ComputePayload::Normalization(r)) => r,
            _ => {
                return Err(PipelineError::Validation(
                    "missing normalization request payload".to_string(),
                ))
            }
        };

        ctx.progress
            .update(0.0, "normalization", &format!("Starting normalization: {}", req.mode))
            .await;

        let mut response = NormalizationResponse {
            normalized_values: vec![],
            variants: vec![],
        };

        match req.mode.as_str() {
            "unicode" => {
                response.normalized_values = req
                    .values
                    .iter()
                    .map(|v| normalize_unicode(v))
                    .collect();
            }
            "name_variants" => {
                for value in &req.values {
                    let vars = name_variants(value);
                    response.variants.push(vars.join("|"));
                    // Also provide the primary normalized form
                    response.normalized_values.push(normalize_name(value));
                }
            }
            "rules" => {
                // Compile regex rules
                let compiled: Vec<(Regex, String)> = req
                    .rules
                    .iter()
                    .filter_map(|r| {
                        Regex::new(&r.pattern)
                            .ok()
                            .map(|re| (re, r.replacement.clone()))
                    })
                    .collect();

                response.normalized_values = req
                    .values
                    .iter()
                    .map(|v| apply_rules(v, &compiled))
                    .collect();
            }
            _ => unreachable!("validated above"),
        }

        ctx.progress
            .update(1.0, "done", "Normalization complete")
            .await;

        let mut counters = HashMap::new();
        counters.insert("values_processed".to_string(), req.values.len() as i32);

        Ok(PipelineOutput {
            counters,
            compute_result: Some(ComputeResult::Normalization(response)),
            ..PipelineOutput::default()
        })
    }
}

/// Unicode normalization: NFD decomposition + diacritic stripping + ASCII folding + lowercase.
fn normalize_unicode(value: &str) -> String {
    let stripped = strip_diacritics(value);
    stripped
        .chars()
        .map(|c| if c.is_alphanumeric() || c.is_whitespace() { c } else { ' ' })
        .collect::<String>()
        .split_whitespace()
        .collect::<Vec<_>>()
        .join(" ")
        .to_lowercase()
}

/// Apply a series of regex replacement rules in order.
fn apply_rules(value: &str, rules: &[(Regex, String)]) -> String {
    let mut result = value.to_string();
    for (pattern, replacement) in rules {
        result = pattern.replace_all(&result, replacement.as_str()).to_string();
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_normalize_unicode_diacritics() {
        assert_eq!(normalize_unicode("García"), "garcia");
        assert_eq!(normalize_unicode("Müller"), "muller");
        assert_eq!(normalize_unicode("Šťěpán"), "stepan");
    }

    #[test]
    fn test_normalize_unicode_punctuation() {
        assert_eq!(normalize_unicode("O'Brien"), "o brien");
        assert_eq!(normalize_unicode("Dr. Smith-Jones"), "dr smith jones");
    }

    #[test]
    fn test_normalize_unicode_whitespace() {
        assert_eq!(normalize_unicode("  John   Doe  "), "john doe");
    }

    #[test]
    fn test_apply_rules_basic() {
        let rules = vec![
            (Regex::new(r"(?i)\bInc\.?").unwrap(), "Incorporated".to_string()),
            (Regex::new(r"\s+").unwrap(), " ".to_string()),
        ];
        assert_eq!(apply_rules("Apple Inc.", &rules), "Apple Incorporated");
    }

    #[test]
    fn test_apply_rules_sequential() {
        let rules = vec![
            (Regex::new(r"foo").unwrap(), "bar".to_string()),
            (Regex::new(r"bar").unwrap(), "baz".to_string()),
        ];
        // First rule: "foo" → "bar", second rule: "bar" → "baz"
        assert_eq!(apply_rules("foo", &rules), "baz");
    }

    #[test]
    fn test_apply_rules_no_match() {
        let rules = vec![
            (Regex::new(r"xyz").unwrap(), "abc".to_string()),
        ];
        assert_eq!(apply_rules("hello world", &rules), "hello world");
    }

    #[test]
    fn test_normalization_pipeline_validate() {
        let pipeline = NormalizationPipeline;

        // Valid unicode mode
        let input = PipelineInput {
            job_id: "t".to_string(),
            import_batch_id: 0,
            org_id: None,
            domain: "t".to_string(),
            publications: vec![],
            options: HashMap::new(),
            payload: Some(ComputePayload::Normalization(
                crate::proto::NormalizationRequest {
                    values: vec!["test".to_string()],
                    mode: "unicode".to_string(),
                    rules: vec![],
                },
            )),
        };
        assert!(pipeline.validate(&input).is_ok());

        // Invalid mode
        let input_bad = PipelineInput {
            job_id: "t".to_string(),
            import_batch_id: 0,
            org_id: None,
            domain: "t".to_string(),
            publications: vec![],
            options: HashMap::new(),
            payload: Some(ComputePayload::Normalization(
                crate::proto::NormalizationRequest {
                    values: vec!["test".to_string()],
                    mode: "invalid".to_string(),
                    rules: vec![],
                },
            )),
        };
        assert!(pipeline.validate(&input_bad).is_err());

        // Rules mode without rules
        let input_no_rules = PipelineInput {
            job_id: "t".to_string(),
            import_batch_id: 0,
            org_id: None,
            domain: "t".to_string(),
            publications: vec![],
            options: HashMap::new(),
            payload: Some(ComputePayload::Normalization(
                crate::proto::NormalizationRequest {
                    values: vec!["test".to_string()],
                    mode: "rules".to_string(),
                    rules: vec![],
                },
            )),
        };
        assert!(pipeline.validate(&input_no_rules).is_err());
    }

    #[test]
    fn test_normalization_pipeline_validate_empty_values() {
        let pipeline = NormalizationPipeline;
        let input = PipelineInput {
            job_id: "t".to_string(),
            import_batch_id: 0,
            org_id: None,
            domain: "t".to_string(),
            publications: vec![],
            options: HashMap::new(),
            payload: Some(ComputePayload::Normalization(
                crate::proto::NormalizationRequest {
                    values: vec![],
                    mode: "unicode".to_string(),
                    rules: vec![],
                },
            )),
        };
        assert!(pipeline.validate(&input).is_err());
    }

    #[test]
    fn test_name_variants_mode_output() {
        // Simulating what the pipeline would produce
        let variants = name_variants("Smith, John");
        let joined = variants.join("|");
        assert!(joined.contains("john smith"));
        assert!(joined.contains("smith john"));
    }
}
