from __future__ import annotations

from tbg.core.rng import RNG
from tbg.domain.knowledge_models import EnemyHpVisibilityMode, KnowledgeTier
from tbg.domain.state import GameState
from tbg.data.repositories import KnowledgeRulesRepository
from tbg.services.knowledge_service import KnowledgeService


def _build_state(seed: int = 123) -> GameState:
    return GameState(seed=seed, rng=RNG(seed), mode="story", current_node_id="test_node")


def _build_service() -> KnowledgeService:
    return KnowledgeService(KnowledgeRulesRepository())


def test_knowledge_tier_boundaries() -> None:
    service = _build_service()
    state = _build_state()
    key = "k_test"

    state.knowledge_kill_counts[key] = 0
    assert service.get_tier_for_key(state, key) == KnowledgeTier.TIER_0

    state.knowledge_kill_counts[key] = 24
    assert service.get_tier_for_key(state, key) == KnowledgeTier.TIER_0

    state.knowledge_kill_counts[key] = 25
    assert service.get_tier_for_key(state, key) == KnowledgeTier.TIER_1

    state.knowledge_kill_counts[key] = 74
    assert service.get_tier_for_key(state, key) == KnowledgeTier.TIER_1

    state.knowledge_kill_counts[key] = 75
    assert service.get_tier_for_key(state, key) == KnowledgeTier.TIER_2

    state.knowledge_kill_counts[key] = 149
    assert service.get_tier_for_key(state, key) == KnowledgeTier.TIER_2

    state.knowledge_kill_counts[key] = 150
    assert service.get_tier_for_key(state, key) == KnowledgeTier.TIER_3


def test_knowledge_hp_visibility_policy() -> None:
    service = _build_service()
    assert service.get_hp_visibility_mode_for_tier(KnowledgeTier.TIER_0) == EnemyHpVisibilityMode.HIDDEN
    assert (
        service.get_hp_visibility_mode_for_tier(KnowledgeTier.TIER_1)
        == EnemyHpVisibilityMode.STATIC_RANGE
    )
    assert service.get_hp_visibility_mode_for_tier(KnowledgeTier.TIER_2) == EnemyHpVisibilityMode.REALTIME
    assert service.get_hp_visibility_mode_for_tier(KnowledgeTier.TIER_3) == EnemyHpVisibilityMode.REALTIME


def test_record_kills_accumulates() -> None:
    service = _build_service()
    state = _build_state()

    service.record_kills(state, {"k_x": 2})
    assert state.knowledge_kill_counts["k_x"] == 2

    service.record_kills(state, {"k_x": 3})
    assert state.knowledge_kill_counts["k_x"] == 5


def test_set_kill_count_overwrites() -> None:
    service = _build_service()
    state = _build_state()
    service.set_kill_count(state, "k_test", 7)
    assert state.knowledge_kill_counts["k_test"] == 7
    service.set_kill_count(state, "k_test", 2)
    assert state.knowledge_kill_counts["k_test"] == 2


def test_add_kill_count_clamps_non_negative() -> None:
    service = _build_service()
    state = _build_state()
    service.set_kill_count(state, "k_test", 5)
    total = service.add_kill_count(state, "k_test", -10)
    assert total == 0
    assert state.knowledge_kill_counts["k_test"] == 0


def test_knowledge_service_does_not_consume_rng() -> None:
    service = _build_service()
    state = _build_state(seed=999)
    before = state.rng.export_state()

    service.get_tier_for_key(state, "k_rng")
    service.get_hp_visibility_mode_for_key(state, "k_rng")
    service.record_kills(state, {"k_rng": 1})

    after = state.rng.export_state()
    assert after == before
