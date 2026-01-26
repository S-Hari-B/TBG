"""Knowledge progression and policy service."""
from __future__ import annotations

from typing import Dict

from tbg.data.repositories import KnowledgeRulesRepository
from tbg.domain.knowledge_models import EnemyHpVisibilityMode, KnowledgeTier
from tbg.domain.state import GameState


class KnowledgeService:
    """Deterministic knowledge progression service."""

    def __init__(self, rules_repo: KnowledgeRulesRepository) -> None:
        self._rules_repo = rules_repo

    def get_kill_count(self, state: GameState, key: str) -> int:
        count = state.knowledge_kill_counts.get(key, 0)
        return count if isinstance(count, int) and count >= 0 else 0

    def get_tier_for_key(self, state: GameState, key: str) -> KnowledgeTier:
        kills = self.get_kill_count(state, key)
        thresholds = self._rules_repo.get_rules().thresholds
        if kills >= thresholds.tier3_kills:
            return KnowledgeTier.TIER_3
        if kills >= thresholds.tier2_kills:
            return KnowledgeTier.TIER_2
        if kills >= thresholds.tier1_kills:
            return KnowledgeTier.TIER_1
        return KnowledgeTier.TIER_0

    def get_hp_visibility_mode_for_tier(self, tier: KnowledgeTier) -> EnemyHpVisibilityMode:
        return self._rules_repo.get_rules().hp_visibility_by_tier[tier]

    def get_hp_visibility_mode_for_key(self, state: GameState, key: str) -> EnemyHpVisibilityMode:
        tier = self.get_tier_for_key(state, key)
        return self.get_hp_visibility_mode_for_tier(tier)

    def record_kills(self, state: GameState, kills_by_key: Dict[str, int]) -> None:
        if not isinstance(kills_by_key, dict):
            return
        for key, increment in kills_by_key.items():
            if not isinstance(key, str):
                continue
            if not isinstance(increment, int) or increment <= 0:
                continue
            current = state.knowledge_kill_counts.get(key, 0)
            if not isinstance(current, int) or current < 0:
                current = 0
            state.knowledge_kill_counts[key] = current + increment

    def set_kill_count(self, state: GameState, key: str, value: int) -> int:
        if not isinstance(key, str):
            return 0
        normalized_key = key.strip()
        if not normalized_key:
            return 0
        if not isinstance(value, int) or value < 0:
            return 0
        state.knowledge_kill_counts[normalized_key] = value
        return value

    def add_kill_count(self, state: GameState, key: str, delta: int) -> int:
        if not isinstance(key, str):
            return 0
        normalized_key = key.strip()
        if not normalized_key:
            return 0
        if not isinstance(delta, int):
            return self.get_kill_count(state, normalized_key)
        current = self.get_kill_count(state, normalized_key)
        total = max(0, current + delta)
        state.knowledge_kill_counts[normalized_key] = total
        return total
