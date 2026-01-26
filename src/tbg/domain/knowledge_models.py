"""Core knowledge system models."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum


class KnowledgeTier(IntEnum):
    """Progression tiers for knowledge unlocks."""

    TIER_0 = 0
    TIER_1 = 1
    TIER_2 = 2
    TIER_3 = 3


class EnemyHpVisibilityMode(Enum):
    """Policy describing how enemy HP should be displayed."""

    HIDDEN = "HIDDEN"
    STATIC_RANGE = "STATIC_RANGE"
    REALTIME = "REALTIME"


@dataclass(frozen=True, slots=True)
class KnowledgeThresholds:
    tier1_kills: int
    tier2_kills: int
    tier3_kills: int


@dataclass(frozen=True, slots=True)
class KnowledgeRules:
    thresholds: KnowledgeThresholds
    hp_visibility_by_tier: dict[KnowledgeTier, EnemyHpVisibilityMode]
    overrides: dict[str, dict]
