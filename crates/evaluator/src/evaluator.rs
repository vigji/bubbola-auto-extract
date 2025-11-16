use serde::Deserialize;
use serde_json::{Map, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::io::{Cursor, Read};
use std::path::{Path, PathBuf};

use crate::embedded;
use crate::error::EvaluationError;
use crate::metrics::EvaluationMetrics;

#[derive(Debug, Clone)]
pub struct Document {
    pub document_id: String,
    pub fields: Value,
}

#[derive(Debug, Deserialize)]
struct RawDocument {
    document_id: String,
    fields: Value,
}

pub fn load_ground_truth_from_embed() -> Result<BTreeMap<String, Document>, EvaluationError> {
    let bytes = embedded::ground_truth_bytes();
    let mut decoder = flate2::read::ZlibDecoder::new(Cursor::new(bytes));
    let mut payload = String::new();
    decoder.read_to_string(&mut payload)?;
    parse_documents(&payload)
}

pub fn load_ground_truth_from_path(
    path: &Path,
) -> Result<BTreeMap<String, Document>, EvaluationError> {
    let payload = fs::read_to_string(path)?;
    parse_documents(&payload)
}

pub fn load_predictions(path: &Path) -> Result<BTreeMap<String, Document>, EvaluationError> {
    if !path.exists() {
        return Err(EvaluationError::FileNotFound(path.to_path_buf()));
    }
    let payload = fs::read_to_string(path)?;
    parse_documents(&payload)
}

fn parse_documents(payload: &str) -> Result<BTreeMap<String, Document>, EvaluationError> {
    let records: Vec<RawDocument> = serde_json::from_str(payload)?;
    if records.is_empty() {
        return Err(EvaluationError::EmptyInput);
    }
    let mut documents = BTreeMap::new();
    for record in records {
        if !record.fields.is_object() {
            return Err(EvaluationError::InvalidFields(record.document_id));
        }
        documents.insert(
            record.document_id.clone(),
            Document {
                document_id: record.document_id,
                fields: record.fields,
            },
        );
    }
    Ok(documents)
}

pub fn evaluate_predictions(
    ground_truth: &BTreeMap<String, Document>,
    predictions: &BTreeMap<String, Document>,
) -> Result<EvaluationMetrics, EvaluationError> {
    if ground_truth.is_empty() {
        return Err(EvaluationError::EmptyInput);
    }

    let mut total_fields = 0_u32;
    let mut docs_with_predictions = 0_u32;
    let mut matched_fields = 0_u32;

    let mut numeric_total = 0_u32;
    let mut numeric_score = 0.0_f64;
    let mut text_total = 0_u32;
    let mut text_score = 0.0_f64;

    let mut missing_docs: Vec<String> = Vec::new();
    let extra_docs: Vec<String> = predictions
        .keys()
        .filter(|key| !ground_truth.contains_key(*key))
        .cloned()
        .collect();

    let mut missing_field_count = 0_u32;
    let mut extra_field_count = 0_u32;
    let mut missing_fields: BTreeMap<String, Vec<String>> = BTreeMap::new();
    let mut extra_fields: BTreeMap<String, Vec<String>> = BTreeMap::new();

    for (doc_id, gt_doc) in ground_truth {
        let gt_flat = flatten_fields(&gt_doc.fields, Vec::new())?;
        total_fields += gt_flat.len() as u32;
        let Some(pred_doc) = predictions.get(doc_id) else {
            missing_docs.push(doc_id.clone());
            missing_field_count += gt_flat.len() as u32;
            if !gt_flat.is_empty() {
                missing_fields.insert(doc_id.clone(), gt_flat.keys().cloned().collect());
            }
            for value in gt_flat.values() {
                if value.is_number() {
                    numeric_total += 1;
                } else {
                    text_total += 1;
                }
            }
            continue;
        };

        docs_with_predictions += 1;
        let pred_flat = flatten_fields(&pred_doc.fields, Vec::new())?;
        let gt_paths: BTreeSet<_> = gt_flat.keys().cloned().collect();
        let pred_paths: BTreeSet<_> = pred_flat.keys().cloned().collect();
        let matched: Vec<_> = gt_paths.intersection(&pred_paths).collect();
        matched_fields += matched.len() as u32;

        let missing_paths: Vec<String> = gt_paths.difference(&pred_paths).cloned().collect();
        if !missing_paths.is_empty() {
            missing_field_count += missing_paths.len() as u32;
            missing_fields.insert(doc_id.clone(), missing_paths);
        }

        let extra_paths: Vec<String> = pred_paths.difference(&gt_paths).cloned().collect();
        if !extra_paths.is_empty() {
            extra_field_count += extra_paths.len() as u32;
            extra_fields.insert(doc_id.clone(), extra_paths);
        }

        for (path, expected) in gt_flat.iter() {
            let predicted = pred_flat.get(path);
            if expected.is_number() {
                numeric_total += 1;
                if let Some(score) = numeric_similarity(expected, predicted) {
                    numeric_score += score;
                }
            } else {
                text_total += 1;
                if let Some(score) = text_similarity(expected, predicted) {
                    text_score += score;
                }
            }
        }
    }

    for doc_id in extra_docs.iter() {
        if let Some(pred_doc) = predictions.get(doc_id) {
            let flat = flatten_fields(&pred_doc.fields, Vec::new())?;
            if !flat.is_empty() {
                extra_field_count += flat.len() as u32;
                extra_fields.insert(doc_id.clone(), flat.keys().cloned().collect());
            }
        }
    }

    let numeric_similarity = if numeric_total > 0 {
        numeric_score / f64::from(numeric_total)
    } else {
        1.0
    };
    let text_similarity = if text_total > 0 {
        text_score / f64::from(text_total)
    } else {
        1.0
    };
    let structural_completeness = if total_fields > 0 {
        f64::from(matched_fields) / f64::from(total_fields)
    } else {
        1.0
    };
    let coverage = if ground_truth.is_empty() {
        0.0
    } else {
        f64::from(docs_with_predictions) / f64::from(ground_truth.len() as u32)
    };

    let overall_score =
        (coverage + structural_completeness + numeric_similarity + text_similarity) / 4.0;

    Ok(EvaluationMetrics::new(
        ground_truth.len() as u32,
        total_fields,
        coverage,
        numeric_similarity,
        text_similarity,
        structural_completeness,
        overall_score,
        missing_docs,
        extra_docs,
        missing_field_count,
        extra_field_count,
        missing_fields,
        extra_fields,
    ))
}

fn flatten_fields(
    value: &Value,
    path: Vec<String>,
) -> Result<BTreeMap<String, Value>, EvaluationError> {
    let mut flattened = BTreeMap::new();
    match value {
        Value::Object(map) => {
            for key in sorted_keys(map) {
                let mut new_path = path.clone();
                new_path.push(key.clone());
                flattened.extend(flatten_fields(
                    map.get(&key).expect("key present"),
                    new_path,
                )?);
            }
        }
        Value::Array(items) => {
            for (idx, item) in items.iter().enumerate() {
                let mut new_path = path.clone();
                new_path.push(idx.to_string());
                flattened.extend(flatten_fields(item, new_path)?);
            }
        }
        _ => {
            if path.is_empty() {
                return Err(EvaluationError::InvalidFieldStructure);
            }
            flattened.insert(path.join("."), value.clone());
        }
    }
    Ok(flattened)
}

fn sorted_keys(map: &Map<String, Value>) -> Vec<String> {
    let mut keys: Vec<String> = map.keys().cloned().collect();
    keys.sort();
    keys
}

fn numeric_similarity(expected: &Value, predicted: Option<&Value>) -> Option<f64> {
    let expected_value = expected.as_f64()?;
    let predicted_value = predicted?.as_f64()?;
    let scale = expected_value.abs().max(predicted_value.abs()).max(1.0);
    let diff = (expected_value - predicted_value).abs() / scale;
    Some((1.0 - diff.min(1.0)).max(0.0))
}

fn text_similarity(expected: &Value, predicted: Option<&Value>) -> Option<f64> {
    let predicted_str = predicted?.as_str()?;
    let expected_str = if expected.is_string() {
        expected.as_str().unwrap().to_string()
    } else {
        normalized_json(expected)
    };
    Some(ratcliff_obershelp(&expected_str, predicted_str))
}

fn normalized_json(value: &Value) -> String {
    fn normalize(value: &Value) -> Value {
        match value {
            Value::Object(map) => {
                let mut entries: Vec<_> = map.iter().collect();
                entries.sort_by(|a, b| a.0.cmp(b.0));
                let normalized: Map<String, Value> = entries
                    .into_iter()
                    .map(|(k, v)| (k.clone(), normalize(v)))
                    .collect();
                Value::Object(normalized)
            }
            Value::Array(items) => Value::Array(items.iter().map(normalize).collect()),
            _ => value.clone(),
        }
    }

    serde_json::to_string(&normalize(value)).unwrap_or_else(|_| "null".into())
}

fn ratcliff_obershelp(a: &str, b: &str) -> f64 {
    let a_chars: Vec<char> = a.chars().collect();
    let b_chars: Vec<char> = b.chars().collect();
    if a_chars.is_empty() && b_chars.is_empty() {
        return 1.0;
    }
    let matches = gestalt_match(&a_chars, &b_chars) as f64;
    (2.0 * matches) / (a_chars.len() + b_chars.len()) as f64
}

fn gestalt_match(a: &[char], b: &[char]) -> usize {
    if a.is_empty() || b.is_empty() {
        return 0;
    }
    if let Some((start_a, start_b, length)) = longest_common_substring(a, b) {
        let prefix = gestalt_match(&a[..start_a], &b[..start_b]);
        let suffix = gestalt_match(&a[start_a + length..], &b[start_b + length..]);
        length + prefix + suffix
    } else {
        0
    }
}

fn longest_common_substring(a: &[char], b: &[char]) -> Option<(usize, usize, usize)> {
    let mut best: Option<(usize, usize, usize)> = None;
    for (i, _) in a.iter().enumerate() {
        for (j, _) in b.iter().enumerate() {
            let mut length = 0;
            while i + length < a.len() && j + length < b.len() && a[i + length] == b[j + length] {
                length += 1;
            }
            match (&best, length) {
                (None, l) if l > 0 => best = Some((i, j, l)),
                (Some((_, _, best_len)), l) if l > *best_len => best = Some((i, j, l)),
                _ => {}
            }
        }
    }
    best
}

pub fn save_metrics(path: &Path, metrics: &EvaluationMetrics) -> Result<(), EvaluationError> {
    let payload = serde_json::to_string_pretty(metrics)?;
    fs::write(path, payload + "\n")?;
    Ok(())
}

pub fn parse_path(value: &str) -> PathBuf {
    PathBuf::from(value)
}
