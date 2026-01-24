"""Helpers for resolving data file locations."""
from __future__ import annotations

import sys
from pathlib import Path


def get_repo_root() -> Path:
    """Return the repository root."""
    return Path(__file__).resolve().parents[3]


def get_app_base_dir() -> Path | None:
    """Return the base directory for packaged builds, if applicable."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return None


def get_definitions_path(base_path: Path | str | None = None) -> Path:
    """Return the directory containing JSON definition files."""
    if base_path is not None:
        return Path(base_path)
    base_dir = get_app_base_dir()
    if base_dir is not None:
        return base_dir / "data" / "definitions"
    return get_repo_root() / "data" / "definitions"


