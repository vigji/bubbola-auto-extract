from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

TESTS_ROOT = Path(__file__).parent
REPO_ROOT = TESTS_ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from eval_binary import evaluate_predictions, load_predictions

DATA_DIR = TESTS_ROOT / "data"


DOC1_FIELDS = {
    "invoice": {
        "number": "1001",
        "amounts": {"subtotal": 100.0, "tax": 23.45},
    },
    "customer": {
        "name": "Acme Corp",
        "address": {"city": "New York", "country": "USA"},
    },
}

def bake_binary(tmp_path: Path) -> Path:
    output = tmp_path / "eval_binary.pyz"
    ground_truth = DATA_DIR / "dummy_ground_truth.json"
    subprocess.run(
        [
            sys.executable,
            str(Path("scripts") / "bake_eval_binary.py"),
            "--ground-truth",
            str(ground_truth),
            "--output",
            str(output),
        ],
        check=True,
    )
    return output


def test_cli_scoring(tmp_path: Path) -> None:
    binary = bake_binary(tmp_path)
    predictions = tmp_path / "predictions.json"
    predictions.write_text(
        json.dumps(
            [
                {
                    "document_id": "doc-1",
                    "fields": {
                        "invoice": {
                            "number": "1001A",
                            "amounts": {"subtotal": 95.0, "tax": 23.45},
                        },
                        "customer": {
                            "name": "Acme Corporation",
                            "address": {
                                "city": "New York",
                                "country": "United States",
                            },
                        },
                    },
                },
                {
                    "document_id": "doc-2",
                    "fields": {
                        "invoice": {
                            "number": "1002",
                            "amounts": {"subtotal": 60.0},
                        },
                        "notes": "Thanks for business",
                        "extra": "ignored",
                    },
                },
                {
                    "document_id": "doc-3",
                    "fields": {"foo": "bar"},
                },
            ]
        )
    )

    result = subprocess.run(
        [sys.executable, str(binary), "--predictions", str(predictions)],
        check=True,
        capture_output=True,
        text=True,
    )

    metrics = json.loads(result.stdout)
    assert metrics["num_documents"] == 2
    assert metrics["num_fields"] == 10
    assert metrics["document_coverage"] == 1.0
    assert metrics["numeric_field_similarity"] == 0.7167
    assert metrics["text_field_similarity"] == 0.7904
    assert metrics["structural_completeness"] == 0.9
    assert metrics["overall_score"] == 0.8518
    assert metrics["missing_documents"] == []
    assert metrics["extra_documents"] == ["doc-3"]
    assert metrics["missing_field_count"] == 1
    assert metrics["extra_field_count"] == 2
    assert metrics["missing_fields"] == {"doc-2": ["invoice.amounts.tax"]}
    assert metrics["extra_fields"] == {"doc-2": ["extra"], "doc-3": ["foo"]}


def test_evaluator_handles_missing_docs(tmp_path: Path) -> None:
    ground_truth_path = DATA_DIR / "dummy_ground_truth.json"
    predictions_path = tmp_path / "predictions_missing.json"
    predictions_path.write_text(
        json.dumps(
            [
                {
                    "document_id": "doc-1",
                    "fields": DOC1_FIELDS,
                }
            ]
        )
    )

    predictions = load_predictions(predictions_path)
    ground_truth = load_predictions(ground_truth_path)
    metrics = evaluate_predictions(ground_truth, predictions)

    assert metrics["missing_documents"] == ["doc-2"]
    assert metrics["document_coverage"] == 0.5
    assert metrics["missing_field_count"] == 4
    assert metrics["numeric_field_similarity"] == 0.5
    assert metrics["text_field_similarity"] == 0.6667
    assert metrics["structural_completeness"] == 0.6
    assert metrics["overall_score"] == 0.5667


def test_cli_reports_build_info(tmp_path: Path) -> None:
    binary = bake_binary(tmp_path)

    result = subprocess.run(
        [sys.executable, str(binary), "--info"],
        check=True,
        capture_output=True,
        text=True,
    )

    info = json.loads(result.stdout)
    assert info["schema_version"] == 1
    assert "ground_truth_sha256" in info


def test_baked_binary_hides_ground_truth_plaintext(tmp_path: Path) -> None:
    binary = bake_binary(tmp_path)
    archive_bytes = binary.read_bytes()
    assert b"doc-1" not in archive_bytes

    with zipfile.ZipFile(binary) as zf:
        members = set(zf.namelist())

    assert "eval_binary/ground_truth.json" not in members
    assert "eval_binary/ground_truth.bin" in members
