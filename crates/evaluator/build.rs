use chrono::Utc;
use flate2::{write::ZlibEncoder, Compression};
use rustc_version::version_meta;
use serde::Deserialize;
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::env;
use std::fs;
use std::io::Write;
use std::path::PathBuf;

const DEFAULT_GROUND_TRUTH: &str = concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../resources/fixtures/dummy_ground_truth.json"
);
const SCHEMA_VERSION: u32 = 1;

#[derive(Deserialize)]
struct DocumentProbe {
    document_id: String,
    fields: Value,
}

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-changed=../../resources/fixtures/dummy_ground_truth.json");
    println!("cargo:rerun-if-env-changed=GROUND_TRUTH_PATH");
    println!("cargo:rerun-if-env-changed=GROUND_TRUTH_JSON");

    let path = env::var("GROUND_TRUTH_PATH")
        .or_else(|_| env::var("GROUND_TRUTH_JSON"))
        .unwrap_or_else(|_| DEFAULT_GROUND_TRUTH.to_string());
    let raw = fs::read(&path).unwrap_or_else(|err| {
        panic!("Failed to read ground truth file '{path}': {err}");
    });

    let documents: Vec<DocumentProbe> = serde_json::from_slice(&raw).unwrap_or_else(|err| {
        panic!("Ground truth must be a JSON array of documents: {err}");
    });
    if documents.is_empty() {
        panic!("Ground truth cannot be empty");
    }
    for doc in &documents {
        if doc.document_id.trim().is_empty() {
            panic!("Each document must declare a non-empty document_id");
        }
        if !doc.fields.is_object() {
            panic!("Each document must use an object for the fields payload");
        }
    }

    let mut encoder = ZlibEncoder::new(Vec::new(), Compression::best());
    encoder.write_all(&raw).expect("compression failed");
    let compressed = encoder.finish().expect("compression finalize failed");

    let mut hasher = Sha256::new();
    hasher.update(&raw);
    let digest = format!("{:x}", hasher.finalize());

    let rustc = version_meta().expect("failed to obtain rustc version");
    let timestamp = Utc::now().to_rfc3339();
    let package_version = env::var("CARGO_PKG_VERSION").unwrap_or_else(|_| "unknown".into());
    let git_commit = env::var("GIT_COMMIT").ok().or_else(|| {
        if let Ok(output) = std::process::Command::new("git")
            .args(["rev-parse", "HEAD"])
            .output()
        {
            if output.status.success() {
                return Some(String::from_utf8_lossy(&output.stdout).trim().to_string());
            }
        }
        None
    });

    let build_info = serde_json::json!({
        "schema_version": SCHEMA_VERSION,
        "package_version": package_version,
        "rustc_version": rustc.short_version_string,
        "build_timestamp_utc": timestamp,
        "ground_truth_sha256": digest,
        "document_count": documents.len(),
        "source_commit": git_commit,
    });

    let out_dir = PathBuf::from(env::var("OUT_DIR").expect("OUT_DIR not set"));
    let dest = out_dir.join("ground_truth.rs");
    let mut file = fs::File::create(dest).expect("failed to create ground_truth.rs");
    writeln!(
        file,
        "pub const GROUND_TRUTH_BYTES: &[u8] = &{:?};",
        compressed
    )
    .unwrap();
    writeln!(
        file,
        "pub const BUILD_INFO_JSON: &str = r#\"{}\"#;",
        build_info.to_string()
    )
    .unwrap();
}
