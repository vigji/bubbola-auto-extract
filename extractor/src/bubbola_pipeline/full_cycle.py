"""Run the full PDF extraction workflow for local smoke tests."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from . import extractor, generator


def _run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, check=True, env=env)


def _build_command(cargo_profile: str) -> list[str]:
    cmd = ["cargo", "build", "--bin", "pdf_eval"]
    if cargo_profile == "release":
        cmd.append("--release")
    elif cargo_profile != "debug":
        cmd.extend(["--profile", cargo_profile])
    return cmd


def _binary_path(env: dict[str, str], cargo_profile: str) -> Path:
    target_dir = Path(env.get("CARGO_TARGET_DIR", "target"))
    profile_dir = "release" if cargo_profile == "release" else cargo_profile
    binary_name = "pdf_eval.exe" if os.name == "nt" else "pdf_eval"
    return target_dir / profile_dir / binary_name


def run_full_cycle(
    work_dir: Path = Path("tests/generated/full_cycle"),
    cargo_profile: str = "debug",
) -> None:
    work_dir.mkdir(parents=True, exist_ok=True)
    ground_truth_path, pdf_path = generator.generate_dataset(work_dir)

    ground_truth_path = ground_truth_path.resolve()

    env = os.environ.copy()
    env["GROUND_TRUTH_PATH"] = str(ground_truth_path)
    _run(_build_command(cargo_profile), env=env)
    binary_path = _binary_path(env, cargo_profile)
    if not binary_path.is_file():
        raise FileNotFoundError(
            f"Expected compiled evaluator at {binary_path}, but it does not exist."
        )

    invoice = extractor.extract_invoice(pdf_path)
    predictions_path = work_dir / "predictions.json"
    extractor.save_predictions(invoice, predictions_path)

    _run(
        [
            str(binary_path),
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
    parser.add_argument(
        "--cargo-profile",
        default="debug",
        help=(
            "Cargo profile to build (e.g. 'debug' or 'release'). "
            "The evaluator binary is resolved from this profile."
        ),
    )
    args = parser.parse_args()
    run_full_cycle(args.work_dir, args.cargo_profile)


if __name__ == "__main__":
    main()
