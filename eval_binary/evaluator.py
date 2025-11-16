from __future__ import annotations

import json
import zlib
from dataclasses import dataclass
from importlib import resources as importlib_resources
from pathlib import Path
from typing import Dict, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class Document:
    document_id: str
    fields: Mapping[str, object]


class GroundTruthNotFoundError(FileNotFoundError):
    """Raised when the baked binary cannot locate the ground truth payload."""


_DEF_GT_FILENAME = "ground_truth.bin"


def _parse_payload(payload: Sequence[object]) -> Dict[str, Document]:
    if not isinstance(payload, Iterable):
        raise ValueError("Ground truth and prediction files must contain a list of documents")

    documents: Dict[str, Document] = {}
    for entry in payload:
        if not isinstance(entry, dict):
            raise ValueError("Each document entry must be a JSON object")
        document_id = entry.get("document_id")
        fields = entry.get("fields")
        if not isinstance(document_id, str) or not isinstance(fields, dict):
            raise ValueError("Each document requires 'document_id' (str) and 'fields' (object)")
        documents[document_id] = Document(document_id=document_id, fields=fields)
    return documents


def _load_ground_truth_from_package() -> Dict[str, Document]:
    try:
        payload = importlib_resources.files(__package__).joinpath(_DEF_GT_FILENAME).read_bytes()
    except FileNotFoundError as exc:  # pragma: no cover - IO errors
        raise GroundTruthNotFoundError(
            "The baked evaluation binary is missing its ground_truth.json payload. "
            "Use scripts/bake_eval_binary.py to embed one."
        ) from exc
    data = zlib.decompress(payload).decode("utf-8")
    parsed = json.loads(data)
    return _parse_payload(parsed)


def load_ground_truth(path: Path | None = None) -> Dict[str, Document]:
    """Load ground truth records either from the baked file or a provided override."""

    if path is not None:
        payload = json.loads(path.read_text())
        return _parse_payload(payload)
    return _load_ground_truth_from_package()


def load_predictions(path: Path) -> Dict[str, Document]:
    """Load predictions from a JSON file using the same schema as the ground truth."""

    if not path.exists():
        raise FileNotFoundError(f"Prediction file not found: {path}")
    payload = json.loads(path.read_text())
    return _parse_payload(payload)


def evaluate_predictions(
    ground_truth: Mapping[str, Document],
    predictions: Mapping[str, Document],
) -> Dict[str, object]:
    total_fields = sum(len(doc.fields) for doc in ground_truth.values())
    correct_fields = 0
    exact_doc_matches = 0
    docs_with_predictions = 0

    missing_docs = []
    extra_docs = sorted(set(predictions.keys()) - set(ground_truth.keys()))

    for doc_id, gt_doc in ground_truth.items():
        pred_doc = predictions.get(doc_id)
        if pred_doc is None:
            missing_docs.append(doc_id)
            continue

        docs_with_predictions += 1
        gt_fields = gt_doc.fields
        pred_fields = pred_doc.fields
        doc_correct = True
        for field_name, expected_value in gt_fields.items():
            value = pred_fields.get(field_name)
            if value == expected_value:
                correct_fields += 1
            else:
                doc_correct = False
        if doc_correct and len(pred_fields) == len(gt_fields):
            exact_doc_matches += 1

    field_accuracy = correct_fields / total_fields if total_fields else 0.0
    document_exact_match = exact_doc_matches / len(ground_truth) if ground_truth else 0.0
    coverage = docs_with_predictions / len(ground_truth) if ground_truth else 0.0

    return {
        "num_documents": len(ground_truth),
        "num_fields": total_fields,
        "document_coverage": round(coverage, 4),
        "field_accuracy": round(field_accuracy, 4),
        "document_exact_match_rate": round(document_exact_match, 4),
        "missing_documents": sorted(missing_docs),
        "extra_documents": extra_docs,
        "correct_fields": correct_fields,
    }
