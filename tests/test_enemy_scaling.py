from __future__ import annotations

import json
from pathlib import Path

from tbg.core.rng import RNG
from tbg.data.repositories import FloorsRepository, LocationsRepository
from tbg.domain.enemy_scaling import scale_enemy_stats
from tbg.domain.entities import Stats
from tbg.domain.state import GameState
from tbg.services.battle_service import BattleService
from tbg.data.repositories import (
    ArmourRepository,
    EnemiesRepository,
    ItemsRepository,
    KnowledgeRepository,
    LootTablesRepository,
    PartyMembersRepository,
    SkillsRepository,
    WeaponsRepository,
)


def test_scale_enemy_stats_applies_flat_increases() -> None:
    base = Stats(max_hp=20, hp=20, max_mp=0, mp=0, attack=5, defense=2, speed=4)
    scaled = scale_enemy_stats(base, battle_level=2)
    assert scaled.max_hp == 40
    assert scaled.attack == 9
    assert scaled.defense == 4
    assert scaled.speed == 4


def test_battle_level_uses_area_level_override(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _write_json(
        definitions_dir / "floors.json",
        {"floor_one": {"name": "Floor One", "level": 5, "starting_location_id": "loc_a"}},
    )
    _write_json(
        definitions_dir / "locations.json",
        {
            "loc_a": {
                "name": "Loc A",
                "description": "Test",
                "floor_id": "floor_one",
                "type": "story",
                "area_level": 2,
                "tags": ["test"],
                "entry_story_node_id": None,
                "connections": [],
            }
        },
    )
    floors_repo = FloorsRepository(base_path=definitions_dir)
    locations_repo = LocationsRepository(floors_repo=floors_repo, base_path=definitions_dir)
    service = _build_battle_service(floors_repo, locations_repo)
    state = GameState(seed=1, rng=RNG(1), mode="battle", current_node_id="dummy")
    state.current_location_id = "loc_a"

    assert service._resolve_battle_level(state).level == 2


def test_battle_level_falls_back_to_floor_level(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _write_json(
        definitions_dir / "floors.json",
        {"floor_one": {"name": "Floor One", "level": 3, "starting_location_id": "loc_a"}},
    )
    _write_json(
        definitions_dir / "locations.json",
        {
            "loc_a": {
                "name": "Loc A",
                "description": "Test",
                "floor_id": "floor_one",
                "type": "story",
                "tags": ["test"],
                "entry_story_node_id": None,
                "connections": [],
            }
        },
    )
    floors_repo = FloorsRepository(base_path=definitions_dir)
    locations_repo = LocationsRepository(floors_repo=floors_repo, base_path=definitions_dir)
    service = _build_battle_service(floors_repo, locations_repo)
    state = GameState(seed=1, rng=RNG(1), mode="battle", current_node_id="dummy")
    state.current_location_id = "loc_a"

    assert service._resolve_battle_level(state).level == 3


def _build_battle_service(
    floors_repo: FloorsRepository,
    locations_repo: LocationsRepository,
) -> BattleService:
    return BattleService(
        enemies_repo=EnemiesRepository(),
        party_members_repo=PartyMembersRepository(),
        knowledge_repo=KnowledgeRepository(),
        weapons_repo=WeaponsRepository(),
        armour_repo=ArmourRepository(),
        skills_repo=SkillsRepository(),
        items_repo=ItemsRepository(),
        loot_tables_repo=LootTablesRepository(),
        floors_repo=floors_repo,
        locations_repo=locations_repo,
    )


def _make_definitions_dir(tmp_path: Path) -> Path:
    definitions_dir = tmp_path / "definitions"
    definitions_dir.mkdir()
    return definitions_dir


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
