from __future__ import annotations

import json
from pathlib import Path

import pytest

from tbg.data.errors import DataValidationError
from tbg.data.repositories import ArmourRepository, ClassesRepository, PartyMembersRepository, WeaponsRepository


def test_classes_repo_rejects_invalid_attribute_keys(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _seed_minimal_equipment_defs(definitions_dir)
    _write_json(
        definitions_dir / "classes.json",
        {
            "bad_class": {
                "name": "Bad Class",
                "base_hp": 20,
                "base_mp": 10,
                "speed": 4,
                "starting_attributes": {"STR": 5, "DEX": 5, "INT": 5, "VIT": 5, "FOO": 0},
                "starting_weapon": "test_blade",
                "starting_armour": {"body": "test_mail"},
            }
        },
    )
    classes_repo = ClassesRepository(
        weapons_repo=WeaponsRepository(base_path=definitions_dir),
        armour_repo=ArmourRepository(base_path=definitions_dir),
        base_path=definitions_dir,
    )
    with pytest.raises(DataValidationError):
        classes_repo.all()


def test_classes_repo_rejects_negative_attributes(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _seed_minimal_equipment_defs(definitions_dir)
    _write_json(
        definitions_dir / "classes.json",
        {
            "bad_class": {
                "name": "Bad Class",
                "base_hp": 20,
                "base_mp": 10,
                "speed": 4,
                "starting_attributes": {"STR": -1, "DEX": 5, "INT": 5, "VIT": 5, "BOND": 0},
                "starting_weapon": "test_blade",
                "starting_armour": {"body": "test_mail"},
            }
        },
    )
    classes_repo = ClassesRepository(
        weapons_repo=WeaponsRepository(base_path=definitions_dir),
        armour_repo=ArmourRepository(base_path=definitions_dir),
        base_path=definitions_dir,
    )
    with pytest.raises(DataValidationError):
        classes_repo.all()


def test_party_members_repo_rejects_non_int_attributes(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _write_json(
        definitions_dir / "party_members.json",
        {
            "ally": {
                "name": "Ally",
                "role": "support",
                "description": "Test ally",
                "tags": ["human"],
                "base_stats": {"max_hp": 20, "max_mp": 10, "speed": 4},
                "starting_attributes": {"STR": "5", "DEX": 5, "INT": 5, "VIT": 5, "BOND": 0},
                "equipment": {"weapons": [], "armour_slots": {}},
                "starting_level": 1,
                "starting_abilities": [],
            }
        },
    )
    party_repo = PartyMembersRepository(base_path=definitions_dir)
    with pytest.raises(DataValidationError):
        party_repo.all()


def _seed_minimal_equipment_defs(definitions_dir: Path) -> None:
    _write_json(
        definitions_dir / "weapons.json",
        {
            "test_blade": {
                "name": "Test Blade",
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
            "test_mail": {
                "name": "Test Mail",
                "slot": "body",
                "defense": 2,
                "value": 12,
                "tags": ["heavy"],
                "hp_bonus": 0,
            }
        },
    )


def _make_definitions_dir(tmp_path: Path) -> Path:
    definitions_dir = tmp_path / "definitions"
    definitions_dir.mkdir()
    return definitions_dir


def _write_json(path: Path, data: dict[str, object]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
