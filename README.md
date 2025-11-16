# bubbola-auto-extract

This repository now ships two cooperating components:

1. **Python data generation and extraction scripts** – generate deterministic ground truth data, render it as a PDF, and prototype an extractor that converts the PDF back into the structured payload.
2. **Rust evaluator** – embeds the private ground truth and scores predictions emitted by any PDF parsing system.

Together they allow you to iterate locally on both the PDF extraction logic and the private evaluator that will be shared with solution developers.

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
