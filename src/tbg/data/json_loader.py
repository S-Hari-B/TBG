"""Low-level JSON helpers for repositories."""
from __future__ import annotations

import json
from pathlib import Path

from .errors import DataLoadError


def load_json(path: Path) -> object:
    """Load JSON from disk and raise DataLoadError on failure."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise DataLoadError(f"Definition file not found: {path}") from exc
    except OSError as exc:
        raise DataLoadError(f"Unable to read definition file: {path}") from exc

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise DataLoadError(f"Invalid JSON in {path}: {exc}") from exc


