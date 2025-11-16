from __future__ import annotations

import json
import zlib
from dataclasses import dataclass
from difflib import SequenceMatcher
from importlib import resources as importlib_resources
from numbers import Number
from pathlib import Path
from typing import Dict, Iterable, Mapping, MutableMapping, Sequence


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


def _is_number(value: object) -> bool:
    return isinstance(value, Number) and not isinstance(value, bool)


def _flatten_fields(data: object, path: tuple[str, ...] | None = None) -> Dict[str, object]:
    path = path or ()
    flattened: Dict[str, object] = {}
    if isinstance(data, Mapping):
        for key, value in data.items():
            flattened.update(_flatten_fields(value, path + (str(key),)))
    elif isinstance(data, list):
        for idx, value in enumerate(data):
            flattened.update(_flatten_fields(value, path + (str(idx),)))
    else:
        if not path:
            raise ValueError("Field structures must be JSON objects or arrays")
        flattened[".".join(path)] = data
    return flattened


def _numeric_similarity(expected: Number, actual: object) -> float:
    if not _is_number(actual):
        return 0.0
    exp = float(expected)
    act = float(actual)
    scale = max(abs(exp), abs(act), 1.0)
    diff = abs(exp - act) / scale
    return max(0.0, 1.0 - min(diff, 1.0))


def _text_similarity(expected: str, actual: object) -> float:
    if not isinstance(actual, str):
        return 0.0
    return SequenceMatcher(None, expected, actual).ratio()


def _record_missing_fields(
    *,
    doc_id: str,
    gt_fields: Mapping[str, object],
    missing_fields: MutableMapping[str, list[str]],
) -> None:
    paths = sorted(gt_fields.keys())
    if not paths:
        return
    missing_fields[doc_id] = paths


def evaluate_predictions(
    ground_truth: Mapping[str, Document],
    predictions: Mapping[str, Document],
) -> Dict[str, object]:
    total_fields = 0
    docs_with_predictions = 0
    matched_fields = 0

    numeric_total = 0
    numeric_score = 0.0
    text_total = 0
    text_score = 0.0

    missing_docs: list[str] = []
    extra_docs = sorted(set(predictions.keys()) - set(ground_truth.keys()))
    missing_field_count = 0
    extra_field_count = 0
    missing_fields_by_doc: Dict[str, list[str]] = {}
    extra_fields_by_doc: Dict[str, list[str]] = {}

    for doc_id, gt_doc in ground_truth.items():
        gt_flat = _flatten_fields(gt_doc.fields)
        total_fields += len(gt_flat)
        pred_doc = predictions.get(doc_id)
        if pred_doc is None:
            missing_docs.append(doc_id)
            missing_field_count += len(gt_flat)
            _record_missing_fields(doc_id=doc_id, gt_fields=gt_flat, missing_fields=missing_fields_by_doc)
            for value in gt_flat.values():
                if _is_number(value):
                    numeric_total += 1
                else:
                    text_total += 1
            continue

        docs_with_predictions += 1
        pred_flat = _flatten_fields(pred_doc.fields)
        common_paths = set(gt_flat.keys()) & set(pred_flat.keys())
        matched_fields += len(common_paths)

        missing_paths = sorted(set(gt_flat.keys()) - set(pred_flat.keys()))
        if missing_paths:
            missing_fields_by_doc[doc_id] = missing_paths
            missing_field_count += len(missing_paths)

        extra_paths = sorted(set(pred_flat.keys()) - set(gt_flat.keys()))
        if extra_paths:
            extra_fields_by_doc[doc_id] = extra_paths
            extra_field_count += len(extra_paths)

        for path, expected in gt_flat.items():
            predicted = pred_flat.get(path)
            if _is_number(expected):
                numeric_total += 1
                if predicted is not None:
                    numeric_score += _numeric_similarity(expected, predicted)
            else:
                text_total += 1
                if predicted is not None:
                    expected_text = expected if isinstance(expected, str) else json.dumps(expected, sort_keys=True)
                    text_score += _text_similarity(expected_text, predicted)

    for doc_id in extra_docs:
        extra_flat = _flatten_fields(predictions[doc_id].fields)
        if extra_flat:
            extra_fields_by_doc[doc_id] = sorted(extra_flat.keys())
            extra_field_count += len(extra_flat)

    numeric_similarity = numeric_score / numeric_total if numeric_total else 1.0
    text_similarity = text_score / text_total if text_total else 1.0
    structural_completeness = matched_fields / total_fields if total_fields else 1.0
    coverage = docs_with_predictions / len(ground_truth) if ground_truth else 0.0

    overall_score = (coverage + structural_completeness + numeric_similarity + text_similarity) / 4

    return {
        "num_documents": len(ground_truth),
        "num_fields": total_fields,
        "document_coverage": round(coverage, 4),
        "numeric_field_similarity": round(numeric_similarity, 4),
        "text_field_similarity": round(text_similarity, 4),
        "structural_completeness": round(structural_completeness, 4),
        "overall_score": round(overall_score, 4),
        "missing_documents": sorted(missing_docs),
        "extra_documents": extra_docs,
        "missing_field_count": missing_field_count,
        "extra_field_count": extra_field_count,
        "missing_fields": dict(sorted(missing_fields_by_doc.items())),
        "extra_fields": dict(sorted(extra_fields_by_doc.items())),
    }
