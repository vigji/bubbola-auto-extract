"""Run the full PDF extraction workflow for local smoke tests."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from . import extractor, generator


def _run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True, env=env)


def run_full_cycle(work_dir: Path = Path("tests/generated/full_cycle")) -> None:
    work_dir.mkdir(parents=True, exist_ok=True)
    ground_truth_path, pdf_path = generator.generate_dataset(work_dir)

    env = os.environ.copy()
    env["GROUND_TRUTH_PATH"] = str(ground_truth_path)
    _run(["cargo", "build", "--bin", "pdf_eval"], env=env)

    invoice = extractor.extract_invoice(pdf_path)
    predictions_path = work_dir / "predictions.json"
    extractor.save_predictions(invoice, predictions_path)

    _run(
        [
            "cargo",
            "run",
            "--",
            "--ground-truth",
            str(ground_truth_path),
            "--predictions",
            str(predictions_path),
        ],
    )


def main() -> None:  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path("tests/generated/full_cycle"),
        help="Scratch directory for generated artifacts",
    )
    args = parser.parse_args()
    run_full_cycle(args.work_dir)


if __name__ == "__main__":
    main()
