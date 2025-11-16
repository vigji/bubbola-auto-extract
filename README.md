# bubbola-auto-extract

A fully self-contained evaluator for PDF parsing tasks. The evaluator is implemented in Rust and bakes a compressed copy of the ground truth directly into the compiled binary so it can be safely shared with solution developers.

## Building a Private Evaluator

1. Install the Rust toolchain (https://rustup.rs/).
2. Provide the path to your private `ground_truth.json` via `GROUND_TRUTH_PATH` when building:

```bash
GROUND_TRUTH_PATH=/secure/ground_truth.json cargo build --release
```

3. The resulting executable lives at `target/release/pdf_eval`. Distribute only the binary—none of the private data is stored in the repository.

The build script validates the JSON structure, compresses it into an opaque blob, and records metadata such as the SHA256 hash of the original file. That metadata is emitted by the `--info` flag so collaborators can confirm which payload they are running without revealing its contents.

## Running Evaluations

```bash
./target/release/pdf_eval --predictions /path/to/predictions.json
```

Optional flags:

- `--output metrics.json` – write the metrics JSON to disk in addition to printing it.
- `--ground-truth local.json` – override the embedded payload (useful for local smoke tests before baking a private binary).
- `--info` – print build metadata and exit.

## End-to-End Test Cycle

The repository ships dummy fixtures under `tests/data/` that exercise the entire flow:

```bash
# Embed the dummy ground truth and run the Rust test suite
cargo test

# Build a release binary with the dummy data and run it against sample predictions
cargo build --release
./target/release/pdf_eval --predictions tests/data/dummy_predictions.json
```

Both commands should report metrics matching the assertions in `tests/cli.rs`, demonstrating that the binary can be rebuilt locally, executed with test predictions, and distributed with only the compiled artifact.
