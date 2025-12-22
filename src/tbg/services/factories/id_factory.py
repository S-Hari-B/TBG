"""Utilities for creating deterministic instance identifiers."""
from __future__ import annotations

from tbg.core.rng import RNG


def make_instance_id(prefix: str, rng: RNG) -> str:
    """Generate a deterministic identifier using the provided RNG."""
    suffix = rng.randint(100000, 999999)
    return f"{prefix}_{suffix}"


