use assert_cmd::assert::OutputAssertExt;
use assert_fs::prelude::*;
use predicates::prelude::*;
use std::path::PathBuf;
use std::process::Command;

fn fixture_path(name: &str) -> String {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../resources/fixtures")
        .join(name)
        .to_string_lossy()
        .into_owned()
}

#[test]
fn cli_scoring_matches_reference() {
    let mut cmd = Command::new(assert_cmd::cargo::cargo_bin!("pdf_eval"));
    cmd.arg("--predictions")
        .arg(fixture_path("dummy_predictions.json"));
    cmd.assert()
        .success()
        .stdout(predicate::str::contains("\"overall_score\": 0.8518"));
}

#[test]
fn cli_writes_output_file() {
    let temp = assert_fs::TempDir::new().unwrap();
    let output = temp.child("metrics.json");
    let mut cmd = Command::new(assert_cmd::cargo::cargo_bin!("pdf_eval"));
    cmd.arg("--predictions")
        .arg(fixture_path("dummy_predictions.json"))
        .arg("--output")
        .arg(output.path());
    cmd.assert().success();

    output.assert(predicate::path::exists());
    output.assert(predicate::str::contains("\"document_coverage\": 1.0"));
}

#[test]
fn cli_reports_build_info() {
    let mut cmd = Command::new(assert_cmd::cargo::cargo_bin!("pdf_eval"));
    cmd.arg("--info");
    cmd.assert()
        .success()
        .stdout(predicate::str::contains("\"schema_version\":1"));
}

#[test]
fn cli_prints_template() {
    let mut cmd = Command::new(assert_cmd::cargo::cargo_bin!("pdf_eval"));
    cmd.arg("--template");
    cmd.assert()
        .success()
        .stdout(predicate::str::contains("\"items\""))
        .stdout(predicate::str::contains("\"pending_description\""));
}
