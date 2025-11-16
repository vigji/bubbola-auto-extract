# bubbola-auto-extract

This repository bundles everything required to iterate on the Bubbola PDF parsing challenge. It exposes:

1. **Python generation + extraction helpers (`extractor/`)** – synthesize a deterministic ground truth JSON payload, render it as a PDF, and implement a reference parser that converts the PDF back into structured data.
2. **Rust evaluator (`crates/evaluator/`)** – embed the private payload into a redistributable binary that scores predictions produced by any extractor.

Shared assets such as the JSON schema and reusable fixtures now live under `resources/`, while release tooling (Dockerfiles, helper scripts) is consolidated in `tools/`.

## Repository layout

| Path | Description |
| ---- | ----------- |
| `extractor/` | Python package with the generator, extractor, and orchestration CLIs. Installed with [uv](https://github.com/astral-sh/uv). |
| `crates/evaluator/` | Standalone Rust crate that embeds the ground-truth payload and exposes the `pdf_eval` binary. |
| `resources/schema/` | Canonical evaluator schema (`page_extraction_template.json`). |
| `resources/fixtures/` | Dummy ground-truth + predictions used in tests and local smoke runs. |
| `tools/docker/` | Container definitions, e.g., to run the Python full-cycle helper in isolation. |

## Python pipeline (uv powered)

All Python commands assume you are at the repository root. Create and reuse a virtual environment managed by uv:

```bash
uv venv
source .venv/bin/activate
uv pip install --upgrade pip
uv pip install --editable extractor
```

### Generate a demo ground truth JSON + PDF

```bash
uv run --project extractor bubbola-generate --output tests/generated
```

The command writes `tests/generated/ground_truth.json` and `tests/generated/demo_invoice.pdf`. Pass `--ground-truth path/to/payload.json` to rebuild the PDF from a payload that already matches the evaluator schema (for example, the JSON accepted by the CI workflows below).

### Extract predictions from the PDF

```bash
uv run --project extractor bubbola-extract tests/generated/demo_invoice.pdf --output tests/generated/predictions.json
```

The extractor performs a rule-based parse of the synthetic PDF and emits predictions that satisfy the evaluator schema enforced by `resources/schema/page_extraction_template.json`.

### Run the full-cycle smoke test

```bash
uv run --project extractor bubbola-full-cycle
```

`bubbola-full-cycle` exercises the entire pipeline:

1. Generate ground truth data and the PDF from the shared Pydantic models (`extractor/src/bubbola_pipeline/models.py`).
2. Build and test the Rust evaluator with `GROUND_TRUTH_PATH` pointing at the newly written JSON.
3. Execute the extractor against the PDF and evaluate the resulting predictions via the compiled `pdf_eval` binary.

All scratch artifacts live under `tests/generated/full_cycle/`. Override the build profile with `--cargo-profile release` to bake a release-mode evaluator.

## Rust evaluator

### Building the evaluator with private data

1. Install the Rust toolchain via [rustup](https://rustup.rs/).
2. Provide the path to your private `ground_truth.json` through the `GROUND_TRUTH_PATH` environment variable (or inline JSON via `GROUND_TRUTH_JSON`).
3. Build the workspace from the repository root:

```bash
GROUND_TRUTH_PATH=/secure/ground_truth.json cargo build --release --locked
```

The resulting binary is available at `target/release/pdf_eval`. Only the compiled executable needs to be distributed; the payload is compressed and embedded inside the binary. `pdf_eval --info` prints metadata (schema version, payload hash, source commit) so collaborators can confirm which payload is bundled without revealing its contents.

### Running evaluations

```bash
./target/release/pdf_eval --predictions /path/to/predictions.json
```

Useful flags:

- `--output metrics.json` – also persist the metrics to disk.
- `--ground-truth local.json` – temporarily override the embedded payload (handy for local smoke tests before baking a private binary).
- `--template` – print the evaluator schema (the same JSON stored in `resources/schema/page_extraction_template.json`).

### End-to-end Rust test cycle

The shared fixtures under `resources/fixtures/` ensure both Rust and Python components validate against the same canonical data:

```bash
cargo test
cargo build --release
./target/release/pdf_eval --predictions resources/fixtures/dummy_predictions.json
```

Both commands should match the assertions defined in `crates/evaluator/tests/cli.rs`, proving the evaluator can be rebuilt locally, executed with sample predictions, and redistributed as a standalone binary.

## Automation and workflows

The repository ships three GitHub Actions workflows under `.github/workflows/`.

### 1. Full-cycle CI (`full-cycle.yml`)

Runs on pushes and pull requests. The workflow installs the Rust toolchain plus uv, installs the Python extractor package (`uv pip install --system ./extractor`), and runs `uv run --project extractor bubbola-full-cycle --work-dir tests/generated/full_cycle_ci`. This keeps the end-to-end loop green in CI and ensures both toolchains work with the current tree layout.

### 2. Publish evaluator binary (`publish-evaluator.yml`)

Triggered manually through **Run workflow** (or via the workflow-dispatch REST API). The dispatcher pastes the private ground-truth JSON array into the `ground_truth_payload` input. The workflow:

1. Writes the payload to `ground_truth.json` and validates that it matches the shared schema by importing `bubbola_pipeline.generator` through uv (`uv run --project extractor python - <<'PY' ...`).
2. Builds a release `pdf_eval` binary with `GROUND_TRUTH_PATH` pointing at the uploaded JSON.
3. Captures the payload hash for auditability, securely deletes `ground_truth.json`, and creates a release tagged `eval-<run-id>` containing **only** `pdf_eval.tar.gz`.

Trigger the workflow from a local terminal without touching the UI:

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

### 3. Run release evaluation (`run-release-evaluation.yml`)

Also triggered manually. It accepts the `release_tag` produced by the publish workflow plus a `pdf_path` that already exists in the repository. The workflow downloads the chosen evaluator release, runs the reference Python extractor via uv (`uv run --project extractor bubbola-extract <pdf_path>`), and executes the evaluator against those predictions. The metrics (`metrics.json` + stdout log) are uploaded as the `evaluation-metrics` artifact so they can be fetched with `gh run download`.

## Containerized helper

`tools/docker/bake_eval_binary.Dockerfile` builds a Python + uv + Rust environment that copies the current workspace layout (`Cargo.toml`, `crates/`, `extractor/`, `resources/`) and runs `bubbola-full-cycle` in release mode. Use it when you need an isolated container that exercises the new directory structure without polluting your host toolchains.
