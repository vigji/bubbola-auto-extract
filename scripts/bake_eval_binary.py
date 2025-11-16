#!/usr/bin/env python3
"""Utility for baking an evaluation binary with a ground truth payload."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import tempfile
import zipapp
import zlib
from datetime import UTC, datetime
from pathlib import Path

import tomllib

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "eval_binary"
MAIN_ENTRYPOINT = f"{PACKAGE_NAME}.cli:main"
GROUND_TRUTH_FILENAME = "ground_truth.bin"
BUILD_INFO_FILENAME = "_build_info.json"
SCHEMA_VERSION = 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ground-truth",
        required=True,
        type=Path,
        help="Path to the ground_truth.json file that should be embedded into the binary.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Where to write the baked binary (e.g. data/eval_binary.pyz).",
    )
    return parser


def _project_version() -> str:
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)
    return data["project"]["version"]


def _git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def _compress_ground_truth(path: Path) -> tuple[bytes, str]:
    raw = path.read_bytes()
    try:
        json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - user input validation
        raise SystemExit(f"Ground truth file must contain valid JSON: {exc}")
    digest = hashlib.sha256(raw).hexdigest()
    compressed = zlib.compress(raw, level=9)
    return compressed, digest


def _write_ground_truth(package_dst: Path, blob: bytes) -> None:
    target = package_dst / GROUND_TRUTH_FILENAME
    target.write_bytes(blob)


def _write_build_info(package_dst: Path, *, gt_hash: str) -> None:
    info = {
        "schema_version": SCHEMA_VERSION,
        "package_version": _project_version(),
        "python_version": platform.python_version(),
        "build_platform": platform.platform(),
        "build_timestamp_utc": datetime.now(tz=UTC).isoformat(),
        "ground_truth_sha256": gt_hash,
    }
    commit = _git_commit()
    if commit:
        info["source_commit"] = commit
    (package_dst / BUILD_INFO_FILENAME).write_text(json.dumps(info, indent=2, sort_keys=True) + "\n")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    ground_truth_path = args.ground_truth
    if not ground_truth_path.exists():
        raise SystemExit(f"Ground truth file not found: {ground_truth_path}")

    package_src = REPO_ROOT / PACKAGE_NAME
    if not package_src.exists():
        raise SystemExit(f"Unable to locate source package at {package_src}")

    with tempfile.TemporaryDirectory() as tmpdir:
        build_root = Path(tmpdir) / "app"
        build_root.mkdir()
        package_dst = build_root / PACKAGE_NAME
        shutil.copytree(package_src, package_dst, ignore=shutil.ignore_patterns("__pycache__"))

        blob, digest = _compress_ground_truth(ground_truth_path)
        _write_ground_truth(package_dst, blob)
        _write_build_info(package_dst, gt_hash=digest)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        zipapp.create_archive(
            build_root,
            target=args.output,
            main=MAIN_ENTRYPOINT,
            interpreter="/usr/bin/env python3",
            compressed=True,
        )

    print(f"Baked evaluation binary written to {args.output}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
