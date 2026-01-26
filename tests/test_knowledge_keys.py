from __future__ import annotations

from tbg.core.rng import RNG
from tbg.data.repositories import KnowledgeRulesRepository
from pathlib import Path

from tbg.data.repositories import EnemiesRepository
from tbg.domain.defs import EnemyDef
from tbg.domain.state import GameState
from tbg.services.knowledge_service import KnowledgeService
from tbg.services.knowledge_keys import list_all_knowledge_keys, resolve_enemy_knowledge_key


def test_resolve_enemy_knowledge_key_prefers_override() -> None:
    enemy = EnemyDef(id="goblin_grunt", name="Goblin Grunt", knowledge_key="k_ch00_goblin_grunt")
    assert resolve_enemy_knowledge_key(enemy) == "k_ch00_goblin_grunt"


def test_resolve_enemy_knowledge_key_falls_back_to_id() -> None:
    enemy = EnemyDef(id="wolf", name="Forest Wolf")
    assert resolve_enemy_knowledge_key(enemy) == "wolf"


def test_resolve_key_used_with_knowledge_service() -> None:
    enemy = EnemyDef(id="goblin_grunt", name="Goblin Grunt", knowledge_key="k_ch00_goblin_grunt")
    state = GameState(seed=1, rng=RNG(1), mode="story", current_node_id="test_node")
    state.knowledge_kill_counts[resolve_enemy_knowledge_key(enemy)] = 25
    service = KnowledgeService(KnowledgeRulesRepository())
    assert service.get_tier_for_key(state, resolve_enemy_knowledge_key(enemy)).value == 1


def test_list_all_knowledge_keys_sorted() -> None:
    definitions_dir = Path(__file__).parent / "fixtures" / "data" / "definitions"
    repo = EnemiesRepository(base_path=definitions_dir)
    keys = list_all_knowledge_keys(repo)
    assert keys == sorted(keys)
    assert "goblin_grunt" in keys
