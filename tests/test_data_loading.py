import json
from pathlib import Path

import pytest

from tbg.data.errors import DataReferenceError, DataValidationError
from tbg.data.repositories import (
    ArmourRepository,
    ClassesRepository,
    ItemsRepository,
    WeaponsRepository,
)


def test_items_repo_loads_two_items(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _write_json(
        definitions_dir / "items.json",
        {
            "hp_potion": {
                "name": "HP Potion",
                "description": "Restores health.",
                "type": "consumable",
                "effects": [{"kind": "heal_hp", "amount": 10}],
                "value": 5,
            },
            "mp_potion": {
                "name": "MP Potion",
                "description": "Restores mana.",
                "type": "consumable",
                "effects": [{"kind": "heal_mp", "amount": 7}],
                "value": 6,
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
                "description": "Invalid",
                "type": "consumable",
                "effects": [],
                "value": 1,
                "extra": "nope",
            }
        },
    )

    repo = ItemsRepository(base_path=definitions_dir)
    with pytest.raises(DataValidationError):
        repo.all()


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


