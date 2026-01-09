import json
from pathlib import Path

import pytest

from tbg.core.rng import RNG
from tbg.data.repositories import ArmourRepository, ClassesRepository, EnemiesRepository, WeaponsRepository
from tbg.services.errors import FactoryError
from tbg.services.factories import (
    create_enemy_instance,
    create_player_from_class_id,
    make_instance_id,
)


def test_create_player_from_class_builds_expected_stats_and_equipment(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _seed_minimal_player_definitions(definitions_dir)
    classes_repo = ClassesRepository(base_path=definitions_dir)
    weapons_repo = WeaponsRepository(base_path=definitions_dir)
    armour_repo = ArmourRepository(base_path=definitions_dir)
    rng = RNG(12345)

    player = create_player_from_class_id(
        class_id="fighter",
        name="Aldric",
        classes_repo=classes_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        rng=rng,
    )

    assert player.class_id == "fighter"
    assert player.name == "Aldric"
    assert player.stats.hp == player.stats.max_hp == 50
    assert player.stats.mp == player.stats.max_mp == 10
    assert player.stats.attack == 3
    assert player.stats.defense == 2
    assert player.stats.speed == 4
    assert player.id.startswith("player_")


def test_create_enemy_instance_builds_expected_stats_and_rewards(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _seed_minimal_enemy_definitions(definitions_dir)
    enemies_repo = EnemiesRepository(base_path=definitions_dir)
    rng = RNG(999)

    enemy = create_enemy_instance("slime", enemies_repo=enemies_repo, rng=rng)

    assert enemy.enemy_id == "slime"
    assert enemy.name == "Slime"
    assert enemy.stats.hp == enemy.stats.max_hp == 20
    assert enemy.stats.max_mp == 0 and enemy.stats.mp == 0
    assert enemy.stats.attack == 2
    assert enemy.stats.defense == 0
    assert enemy.stats.speed == 1
    assert enemy.xp_reward == 5
    assert enemy.gold_reward == 3
    assert enemy.id.startswith("enemy_")


def test_instance_ids_deterministic_for_same_seed() -> None:
    rng_a = RNG(321)
    rng_b = RNG(321)

    ids_a = [make_instance_id("player", rng_a), make_instance_id("enemy", rng_a)]
    ids_b = [make_instance_id("player", rng_b), make_instance_id("enemy", rng_b)]

    assert ids_a == ids_b


def test_create_player_missing_class_raises_clean_error(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _seed_minimal_player_definitions(definitions_dir)
    classes_repo = ClassesRepository(base_path=definitions_dir)
    weapons_repo = WeaponsRepository(base_path=definitions_dir)
    armour_repo = ArmourRepository(base_path=definitions_dir)

    with pytest.raises(FactoryError):
        create_player_from_class_id(
            class_id="missing_class",
            name="Nope",
            classes_repo=classes_repo,
            weapons_repo=weapons_repo,
            armour_repo=armour_repo,
            rng=RNG(1),
        )


def _make_definitions_dir(tmp_path: Path) -> Path:
    definitions_dir = tmp_path / "definitions"
    definitions_dir.mkdir()
    return definitions_dir


def _seed_minimal_player_definitions(definitions_dir: Path) -> None:
    _write_json(
        definitions_dir / "weapons.json",
        {
            "fighter_blade": {
                "name": "Fighter Blade",
                "attack": 3,
                "value": 10,
                "tags": ["sword"],
                "slot_cost": 1,
                "default_basic_attack_id": "basic_slash",
                "energy_bonus": 0,
            }
        },
    )
    _write_json(
        definitions_dir / "armour.json",
        {
            "fighter_mail": {
                "name": "Fighter Mail",
                "slot": "body",
                "defense": 2,
                "value": 12,
                "tags": ["heavy"],
                "hp_bonus": 0,
            }
        },
    )
    _write_json(
        definitions_dir / "classes.json",
        {
            "fighter": {
                "name": "Fighter",
                "base_hp": 50,
                "base_mp": 10,
                "speed": 4,
                "starting_weapon": "fighter_blade",
                "starting_armour": {"body": "fighter_mail"},
            }
        },
    )


def _seed_minimal_enemy_definitions(definitions_dir: Path) -> None:
    _write_json(
        definitions_dir / "enemies.json",
        {
            "slime": {
                "name": "Slime",
                "hp": 20,
                "mp": 0,
                "attack": 2,
                "defense": 0,
                "speed": 1,
                "rewards_exp": 5,
                "rewards_gold": 3,
                "tags": ["ooze"],
            }
        },
    )


def _write_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


