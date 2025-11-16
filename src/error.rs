use std::io;
use std::path::PathBuf;

use thiserror::Error;

#[derive(Debug, Error)]
pub enum EvaluationError {
    #[error("prediction file not found: {0}")]
    FileNotFound(PathBuf),
    #[error("embedded ground truth payload is missing")]
    MissingGroundTruth,
    #[error("ground truth or prediction payload was empty")]
    EmptyInput,
    #[error("each document requires an object-valued 'fields' entry (document: {0})")]
    InvalidFields(String),
    #[error("field structures must be JSON objects or arrays")]
    InvalidFieldStructure,
    #[error("failed to parse JSON: {0}")]
    InvalidJson(#[from] serde_json::Error),
    #[error(transparent)]
    Io(#[from] io::Error),
}
