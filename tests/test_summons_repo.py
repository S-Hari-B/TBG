import json
from pathlib import Path

import pytest

from tbg.data.errors import DataValidationError
from tbg.data.repositories import SummonsRepository


def test_summons_repo_loads_defs() -> None:
    repo = SummonsRepository()
    summon = repo.get("micro_raptor")

    assert summon.id == "micro_raptor"
    assert summon.name == "Micro Raptor"
    assert summon.bond_cost > 0


def test_summons_repo_rejects_extra_fields(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _write_json(
        definitions_dir / "summons.json",
        {
            "bad_summon": {
                "name": "Bad",
                "max_hp": 10,
                "max_mp": 0,
                "attack": 2,
                "defense": 1,
                "speed": 3,
                "bond_cost": 1,
                "extra": "nope",
            }
        },
    )
    repo = SummonsRepository(base_path=definitions_dir)

    with pytest.raises(DataValidationError):
        repo.all()


def test_summons_repo_rejects_missing_required_field(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _write_json(
        definitions_dir / "summons.json",
        {
            "bad_summon": {
                "name": "Bad",
                "max_hp": 10,
                "max_mp": 0,
                "defense": 1,
                "speed": 3,
                "bond_cost": 1,
            }
        },
    )
    repo = SummonsRepository(base_path=definitions_dir)

    with pytest.raises(DataValidationError):
        repo.all()


@pytest.mark.parametrize(
    "payload",
    [
        {
            "name": "Bad",
            "max_hp": 10,
            "max_mp": 0,
            "attack": 2,
            "defense": 1,
            "speed": 3,
            "bond_cost": "5",
        },
        {
            "name": "Bad",
            "max_hp": 10,
            "max_mp": 0,
            "attack": 2,
            "defense": 1,
            "speed": 3.5,
            "bond_cost": 5,
        },
        {
            "name": "Bad",
            "max_hp": 10,
            "max_mp": 0,
            "attack": 2,
            "defense": 1,
            "speed": 3,
            "bond_cost": 5,
            "tags": "beast",
        },
        {
            "name": "Bad",
            "max_hp": 10,
            "max_mp": 0,
            "attack": 2,
            "defense": 1,
            "speed": 3,
            "bond_cost": 5,
            "bond_scaling": "fast",
        },
        {
            "name": "Bad",
            "max_hp": 10,
            "max_mp": 0,
            "attack": 2,
            "defense": 1,
            "speed": 3,
            "bond_cost": 5,
            "bond_scaling": {
                "hp_per_bond": 1,
                "atk_per_bond": 1,
                "def_per_bond": 0,
                "init_per_bond": "0",
            },
        },
        {
            "name": "Bad",
            "max_hp": 10,
            "max_mp": 0,
            "attack": 2,
            "defense": 1,
            "speed": 3,
            "bond_cost": 5,
            "bond_scaling": {
                "hp_per_bond": -1,
                "atk_per_bond": 1,
                "def_per_bond": 0,
                "init_per_bond": 0,
            },
        },
    ],
)
def test_summons_repo_rejects_invalid_types(tmp_path: Path, payload: dict) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _write_json(definitions_dir / "summons.json", {"bad_summon": payload})
    repo = SummonsRepository(base_path=definitions_dir)

    with pytest.raises(DataValidationError):
        repo.all()


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _make_definitions_dir(tmp_path: Path) -> Path:
    definitions_dir = tmp_path / "definitions"
    definitions_dir.mkdir()
    return definitions_dir
