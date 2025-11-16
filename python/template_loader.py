"""Helpers for loading the shared extraction template from Python code."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TEMPLATE_PATH = _REPO_ROOT / "schema" / "page_extraction_template.json"


def template_path() -> Path:
    """Return the canonical path to the extraction template JSON file."""

    return _TEMPLATE_PATH


def load_template() -> Dict[str, Any]:
    """Load the extraction template into memory as a Python dictionary."""

    with _TEMPLATE_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


__all__ = ["load_template", "template_path"]
