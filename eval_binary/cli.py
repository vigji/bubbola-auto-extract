from __future__ import annotations

import argparse
import json
from importlib import resources as importlib_resources
from pathlib import Path
from typing import Sequence

from .evaluator import evaluate_predictions, load_ground_truth, load_predictions

_BUILD_INFO_FILENAME = "_build_info.json"


def _load_build_info() -> dict[str, object]:
    try:
        payload = importlib_resources.files(__package__).joinpath(_BUILD_INFO_FILENAME).read_text()
    except FileNotFoundError:
        return {}
    return json.loads(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Score prediction JSON files against the baked ground truth.",
    )
    parser.add_argument(
        "--predictions",
        type=Path,
        help="Path to the predictions JSON file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write the metrics JSON. Defaults to stdout only.",
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Print build metadata for the baked binary and exit.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.info:
        info = _load_build_info()
        print(json.dumps(info, indent=2, sort_keys=True))
        return 0

    if args.predictions is None:
        parser.error("--predictions is required unless --info is provided")

    ground_truth = load_ground_truth()
    predictions = load_predictions(args.predictions)
    metrics = evaluate_predictions(ground_truth, predictions)

    payload = json.dumps(metrics, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(payload + "\n")
    print(payload)
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
