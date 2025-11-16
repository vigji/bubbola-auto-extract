# bubbola-auto-extract

This repository now ships two cooperating components:

1. **Python data generation and extraction scripts** – generate deterministic ground truth data, render it as a PDF, and prototype an extractor that converts the PDF back into the structured payload.
2. **Rust evaluator** – embeds the private ground truth and scores predictions emitted by any PDF parsing system.

Together they allow you to iterate locally on both the PDF extraction logic and the private evaluator that will be shared with solution developers.

## Shared extraction template

Every extractor implementation must emit a payload that matches the JSON schema stored at `schema/page_extraction_template.json`. The schema is language-agnostic and documents every field requested for each parsed PDF page.

The repository exposes helpers so every language consumes exactly the same definition:

- `pdf_eval --template` prints the schema verbatim so solvers can vendor it alongside the evaluator binary.
- `pdf_eval::template::extraction_template()` returns the parsed `serde_json::Value` for Rust callers.
- `python/template_loader.py` exposes `load_template()` and `template_path()` for Python prototypes.

Rust sources continue to live under `src/` while Python helpers remain under `python/` so cargo tooling keeps functioning without additional configuration. Keep new Python code in the `python/` tree (or another dedicated folder) instead of moving it into `src/`.

## Python pipeline

Install the lightweight dependencies once:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r python/requirements.txt
```

The shared data model lives in `bubbola_pipeline/models.py` and is implemented with Pydantic to guarantee that the generator, extractor, and evaluator agree on the schema.

### Generate a demo ground truth JSON + PDF

```bash
python -m bubbola_pipeline.generator --output tests/generated
```

This writes `tests/generated/ground_truth.json` and `tests/generated/demo_invoice.pdf`.

Pass `--ground-truth path/to/payload.json` to regenerate the PDF and JSON from a payload that already follows the evaluator schema (the same shape accepted by the CI workflows described below).

### Extract predictions from the PDF

```bash
python -m bubbola_pipeline.extractor tests/generated/demo_invoice.pdf --output tests/generated/predictions.json
```

The extractor performs a simple rule-based parse of the PDF content and emits predictions following the evaluator schema.

### Full circle smoke test

The `full_cycle` helper script exercises the entire flow described by the user story:

1. Generate ground truth data and a PDF from the shared Pydantic models.
2. Build and test the Rust evaluator with that ground truth baked in.
3. Run the extractor against the generated PDF and evaluate the predictions with the Rust binary.

```bash
python -m bubbola_pipeline.full_cycle
```

All artifacts are written into `tests/generated/full_cycle/`. The script sets `GROUND_TRUTH_PATH` so `cargo test` and `cargo run` operate against the newly generated data.

## Building the Rust evaluator

1. Install the Rust toolchain (https://rustup.rs/).
2. Provide the path to your private `ground_truth.json` via `GROUND_TRUTH_PATH` when building:

```bash
GROUND_TRUTH_PATH=/secure/ground_truth.json cargo build --release
```

3. The resulting executable lives at `target/release/pdf_eval`. Distribute only the binary—none of the private data is stored in the repository.

The build script validates the JSON structure, compresses it into an opaque blob, and records metadata such as the SHA256 hash of the original file. That metadata is emitted by the `--info` flag so collaborators can confirm which payload they are running without revealing its contents.

## Running evaluations

```bash
./target/release/pdf_eval --predictions /path/to/predictions.json
```

Optional flags:

- `--output metrics.json` – write the metrics JSON to disk in addition to printing it.
- `--ground-truth local.json` – override the embedded payload (useful for local smoke tests before baking a private binary).
- `--info` – print build metadata and exit.

## End-to-end Rust test cycle

The repository still ships dummy fixtures under `tests/data/` that exercise the Rust evaluator on its own:

```bash
# Embed the dummy ground truth and run the Rust test suite
cargo test

# Build a release binary with the dummy data and run it against sample predictions
cargo build --release
./target/release/pdf_eval --predictions tests/data/dummy_predictions.json
```

Both commands should report metrics matching the assertions in `tests/cli.rs`, demonstrating that the binary can be rebuilt locally, executed with test predictions, and distributed with only the compiled artifact.

## Automation pipelines

Two GitHub Actions workflows automate the flows described above. Both workflows live under `.github/workflows/`.

### 1. Publish evaluator binary

`publish-evaluator.yml` is triggered manually through **Run workflow** in the GitHub UI or remotely through the REST API. The dispatcher pastes the private ground-truth JSON array into the `ground_truth_payload` input. The workflow:

1. Stores the payload on disk only long enough to validate that it matches the shared schema.
2. Builds a release-mode `pdf_eval` binary with `GROUND_TRUTH_PATH` pointing at the uploaded JSON.
3. Captures the payload hash for auditability, securely deletes `ground_truth.json`, and creates a release tagged `eval-<run-id>` containing **only** the compiled binary (`pdf_eval.tar.gz`).

The JSON payload never leaves the runner's ephemeral filesystem; the released artifact embeds it inside the Rust binary.

Trigger the workflow from a local terminal (no manual UI steps required) by POSTing to the GitHub Actions workflow-dispatch endpoint. The helper snippet below reads your local payload, escapes it with `jq`, and injects it into the workflow input:

```bash
GH_TOKEN=ghp_yourtoken              # Needs repo + workflow scope
REPO=owner/bubbola-auto-extract
WORKFLOW=publish-evaluator.yml      # Workflow filename or numeric ID
REF=main                            # Branch to build from
PAYLOAD_JSON=/secure/ground_truth.json

curl -L \
  -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${GH_TOKEN}" \
  "https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches" \
  --data @<(jq -n \
    --arg ref "$REF" \
    --arg payload "$(jq -c . "$PAYLOAD_JSON")" \
    '{ref: $ref, inputs: {ground_truth_payload: $payload}}')
```

The JSON file is never uploaded to the repository itself; it only flows through this HTTPS call into the transient runner that builds the binary.

### 2. Run release evaluation

`run-release-evaluation.yml` is also triggered manually via **Run workflow** (or the REST API) and accepts the `release_tag` produced by the workflow above plus a `pdf_path` pointing at the PDF that already lives in the repository. It performs the following steps:

1. Downloads `pdf_eval.tar.gz` from the requested release.
2. Treats `python -m bubbola_pipeline.extractor <pdf_path>` as the default submission, generating `payload/predictions.json`.
3. Executes the downloaded evaluator against those predictions and prints the metrics in the workflow logs.
4. Uploads `evaluation-metrics` artifacts (`metrics.json` + the stdout log) so they can be fetched from any terminal.

Provide the PDF path relative to the repository root (for example, `docs/contest_invoice.pdf`). Keep the matching ground-truth JSON on your local machine; only the PDF needs to be tracked in Git for solvers to test against.

Fetch results locally with:

```bash
gh run download <run-id> -n evaluation-metrics --repo <owner>/<repo>
cat metrics.json
```

The `<run-id>` is visible in the Actions UI. This makes the evaluation output scriptable for local workflows.
