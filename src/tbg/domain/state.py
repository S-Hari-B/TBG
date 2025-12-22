"""Domain-level state tracking."""
from __future__ import annotations

from dataclasses import dataclass

from tbg.core.rng import RNG
from tbg.core.types import GameMode


@dataclass
class GameState:
    """Minimal game state storage."""

    seed: int
    rng: RNG
    mode: GameMode


