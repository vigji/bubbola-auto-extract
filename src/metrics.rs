use serde::Serialize;
use std::collections::BTreeMap;

#[derive(Debug, Serialize)]
pub struct EvaluationMetrics {
    pub num_documents: u32,
    pub num_fields: u32,
    pub document_coverage: f64,
    pub numeric_field_similarity: f64,
    pub text_field_similarity: f64,
    pub structural_completeness: f64,
    pub overall_score: f64,
    pub missing_documents: Vec<String>,
    pub extra_documents: Vec<String>,
    pub missing_field_count: u32,
    pub extra_field_count: u32,
    pub missing_fields: BTreeMap<String, Vec<String>>,
    pub extra_fields: BTreeMap<String, Vec<String>>,
}

impl EvaluationMetrics {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        num_documents: u32,
        num_fields: u32,
        document_coverage: f64,
        numeric_field_similarity: f64,
        text_field_similarity: f64,
        structural_completeness: f64,
        overall_score: f64,
        missing_documents: Vec<String>,
        extra_documents: Vec<String>,
        missing_field_count: u32,
        extra_field_count: u32,
        missing_fields: BTreeMap<String, Vec<String>>,
        extra_fields: BTreeMap<String, Vec<String>>,
    ) -> Self {
        Self {
            num_documents,
            num_fields,
            document_coverage: round(document_coverage),
            numeric_field_similarity: round(numeric_field_similarity),
            text_field_similarity: round(text_field_similarity),
            structural_completeness: round(structural_completeness),
            overall_score: round(overall_score),
            missing_documents,
            extra_documents,
            missing_field_count,
            extra_field_count,
            missing_fields,
            extra_fields,
        }
    }
}

fn round(value: f64) -> f64 {
    (value * 10_000.0).round() / 10_000.0
}
