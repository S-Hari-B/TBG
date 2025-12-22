"""Helpers for resolving data file locations."""
from __future__ import annotations

from pathlib import Path


def get_repo_root() -> Path:
    """Return the repository root."""
    return Path(__file__).resolve().parents[3]


def get_definitions_path(base_path: Path | str | None = None) -> Path:
    """Return the directory containing JSON definition files."""
    if base_path is not None:
        return Path(base_path)
    return get_repo_root() / "data" / "definitions"


