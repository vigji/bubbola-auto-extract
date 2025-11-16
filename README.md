# bubbola-auto-extract

fully LLM designed docker for pdf data parsing

## Evaluation Binary

This repository ships a small toolchain for baking a fully self-contained
evaluation binary. The binary embeds the ground truth labels so that they do not
need to live inside the repository.

### Baking a Binary

```
python scripts/bake_eval_binary.py \
  --ground-truth /path/to/private/ground_truth.json \
  --output data/pdf_eval.pyz
```

The resulting `pdf_eval.pyz` file is a standard Python zipapp. Copy it wherever
it is needed (for example into `data/`).

The baking script validates the JSON file, compresses it into an opaque
`ground_truth.bin` blob, and strips any plain-text copy from the archive. Run a
quick sanity check that the baked file is opaque by searching for identifiers:

```
rg "some-document-id" data/pdf_eval.pyz && echo "should not print any matches"
```

If `rg` produces no matches you can be confident the ground truth does not
appear in clear-text inside the binary.

### Running Evaluations

```
python data/pdf_eval.pyz --predictions /path/to/predictions.json
```

The command prints a JSON payload with document coverage, per-field accuracy,
and exact match rate metrics.

You can always verify the binary is runnable in your environment via the
metadata mode:

```
python data/pdf_eval.pyz --info
```

The metadata includes the schema version, build timestamp, Python version, and
a SHA256 hash of the original ground truth JSON. Sharing this metadata alongside
the `.pyz` makes it easy for collaborators to confirm they are executing the
correct binary without revealing the labels themselves.

### Baking via Docker

The repository ships a tiny builder image definition at
`docker/bake_eval_binary.Dockerfile`. You can create a clean-room compiler that
matches this environment by running:

```
docker build -f docker/bake_eval_binary.Dockerfile -t pdf-eval-builder .
```

To bake a private binary using that image while keeping your ground truth file
outside of the repository:

```
docker run --rm \
  -v "$PWD":/workspace \
  -v /secure/labels:/secure:ro \
  pdf-eval-builder \
  --ground-truth /secure/ground_truth.json \
  --output /workspace/data/pdf_eval.pyz
```

This produces the same layout as the local instructions while guaranteeing that
our team can rebuild and run the archive inside an identical container in the
future.

### JSON Schema

Both ground truth and prediction files must contain a list of documents with the
following structure:

```json
[
  {
    "document_id": "doc-123",
    "fields": {
      "invoice_number": "1001",
      "total": "123.45"
    }
  }
]
```

Only the baked binary needs to know the ground truth file contents.

### Tests

The repository includes dummy fixtures that ensure the baking flow and
scoring logic works end-to-end:

```
pip install -e .[test]
pytest
```
