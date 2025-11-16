from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

from eval_binary import evaluate_predictions, load_predictions

TESTS_ROOT = Path(__file__).parent
DATA_DIR = TESTS_ROOT / "data"


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
                        "invoice_number": "1001",
                        "total": "123.45",
                    },
                },
                {
                    "document_id": "doc-2",
                    "fields": {
                        "invoice_number": "1002",
                        "total": "40.00",
                    },
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
    assert metrics["num_fields"] == 5
    assert metrics["document_coverage"] == 1.0
    assert metrics["document_exact_match_rate"] == 0.5
    assert metrics["field_accuracy"] == 0.6
    assert metrics["missing_documents"] == []


def test_evaluator_handles_missing_docs(tmp_path: Path) -> None:
    ground_truth_path = DATA_DIR / "dummy_ground_truth.json"
    predictions_path = tmp_path / "predictions_missing.json"
    predictions_path.write_text(
        json.dumps(
            [
                {
                    "document_id": "doc-1",
                    "fields": {
                        "invoice_number": "1001",
                        "total": "123.45",
                    },
                }
            ]
        )
    )

    predictions = load_predictions(predictions_path)
    ground_truth = load_predictions(ground_truth_path)
    metrics = evaluate_predictions(ground_truth, predictions)

    assert metrics["missing_documents"] == ["doc-2"]
    assert metrics["document_coverage"] == 0.5


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
