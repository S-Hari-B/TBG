import json
from pathlib import Path

import pytest

from tbg.data.errors import DataReferenceError, DataValidationError
from tbg.data.repositories import (
    ArmourRepository,
    ClassesRepository,
    EnemiesRepository,
    ItemsRepository,
    PartyMembersRepository,
    WeaponsRepository,
)


def test_items_repo_loads_two_items(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _write_json(
        definitions_dir / "items.json",
        {
            "hp_potion": {
                "name": "HP Potion",
                "kind": "consumable",
                "value": 5,
                "heal_hp": 10,
                "targeting": "ally",
            },
            "mp_potion": {
                "name": "MP Potion",
                "kind": "consumable",
                "value": 6,
                "heal_mp": 7,
                "targeting": "self",
            },
            "enemy_dust": {
                "name": "Enemy Dust",
                "kind": "consumable",
                "value": 9,
                "targeting": "enemy",
                "debuff_defense_flat": 2,
            },
        },
    )
    repo = ItemsRepository(base_path=definitions_dir)
    items = repo.all()

    assert len(items) >= 2
    assert {"hp_potion", "mp_potion"}.issubset({item.id for item in items})


def test_weapons_repo_get_missing_raises(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _write_json(
        definitions_dir / "weapons.json",
        {
            "training_sword": {
                "name": "Training Sword",
                "attack": 3,
                "value": 1,
            }
        },
    )
    repo = WeaponsRepository(base_path=definitions_dir)
    with pytest.raises(KeyError):
        repo.get("missing_weapon")


def test_validation_rejects_unknown_field(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _write_json(
        definitions_dir / "items.json",
        {
            "bad_item": {
                "name": "Bad",
                "kind": "material",
                "value": 1,
                "heal_hp": 0,
                "extra": "nope",
            }
        },
    )

    repo = ItemsRepository(base_path=definitions_dir)
    with pytest.raises(DataValidationError):
        repo.all()


def test_bond_baseline_for_classes_and_party_members() -> None:
    classes_repo = ClassesRepository()
    party_repo = PartyMembersRepository()

    for class_id in ("warrior", "rogue", "mage", "commoner"):
        assert classes_repo.get(class_id).starting_attributes.BOND >= 0
    assert classes_repo.get("beastmaster").starting_attributes.BOND > 0

    assert party_repo.get("emma").starting_attributes.BOND >= 0
    assert party_repo.get("niale").starting_attributes.BOND >= 0


def test_validation_rejects_wrong_type(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _write_json(
        definitions_dir / "weapons.json",
        {
            "bad_weapon": {
                "name": "Bad Weapon",
                "attack": "high",
                "value": 5,
            }
        },
    )

    repo = WeaponsRepository(base_path=definitions_dir)
    with pytest.raises(DataValidationError):
        repo.all()


def test_enemies_repo_loads_goblin_rampager() -> None:
    repo = EnemiesRepository()
    enemy = repo.get("goblin_rampager")

    assert enemy.name == "Goblin Rampager"
    assert "rampager" in enemy.tags


def test_enemies_repo_allows_optional_knowledge_key(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _write_json(
        definitions_dir / "enemies.json",
        {
            "goblin_grunt": {
                "name": "Goblin Grunt",
                "knowledge_key": "k_ch00_goblin_grunt",
                "hp": 10,
                "mp": 0,
                "attack": 3,
                "defense": 1,
                "speed": 2,
                "rewards_exp": 1,
                "rewards_gold": 1,
            },
            "wolf": {
                "name": "Forest Wolf",
                "hp": 12,
                "mp": 0,
                "attack": 4,
                "defense": 1,
                "speed": 3,
                "rewards_exp": 2,
                "rewards_gold": 1,
            },
        },
    )
    repo = EnemiesRepository(base_path=definitions_dir)
    assert repo.get("goblin_grunt").knowledge_key == "k_ch00_goblin_grunt"
    assert repo.get("wolf").knowledge_key is None


def test_enemies_repo_rejects_empty_knowledge_key(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _write_json(
        definitions_dir / "enemies.json",
        {
            "goblin_grunt": {
                "name": "Goblin Grunt",
                "knowledge_key": "  ",
                "hp": 10,
                "mp": 0,
                "attack": 3,
                "defense": 1,
                "speed": 2,
                "rewards_exp": 1,
                "rewards_gold": 1,
            }
        },
    )
    repo = EnemiesRepository(base_path=definitions_dir)
    with pytest.raises(DataValidationError):
        repo.all()


def test_classes_repo_reference_validation_fails_when_weapon_missing(tmp_path: Path) -> None:
    definitions_dir = tmp_path / "definitions"
    definitions_dir.mkdir()
    _write_json(
        definitions_dir / "weapons.json",
        {
            "training_staff": {
                "name": "Training Staff",
                "attack": 1,
                "value": 5,
            }
        },
    )
    _write_json(
        definitions_dir / "armour.json",
        {
            "cloth_robe": {
                "name": "Cloth Robe",
                    "slot": "body",
                    "defense": 1,
                    "value": 5,
                    "tags": ["light"],
                    "hp_bonus": 0,
            }
        },
    )
    _write_json(
        definitions_dir / "classes.json",
        {
            "apprentice": {
                "name": "Apprentice",
                "base_hp": 30,
                "base_mp": 25,
                "speed": 5,
                "starting_attributes": {
                    "STR": 2,
                    "DEX": 4,
                    "INT": 8,
                    "VIT": 6,
                    "BOND": 0
                },
                "starting_weapon": "missing_weapon",
                    "starting_armour": {"body": "cloth_robe"},
            }
        },
    )

    weapons_repo = WeaponsRepository(base_path=definitions_dir)
    armour_repo = ArmourRepository(base_path=definitions_dir)
    classes_repo = ClassesRepository(
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        base_path=definitions_dir,
    )

    with pytest.raises(DataReferenceError):
        classes_repo.all()



def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _make_definitions_dir(tmp_path: Path) -> Path:
    definitions_dir = tmp_path / "definitions"
    definitions_dir.mkdir()
    return definitions_dir


