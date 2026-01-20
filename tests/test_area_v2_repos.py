from __future__ import annotations

import json
from pathlib import Path

import pytest

from tbg.data.errors import DataReferenceError, DataValidationError
from tbg.data.repositories import FloorsRepository, LocationsRepository


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _make_definitions_dir(tmp_path: Path) -> Path:
    definitions_dir = tmp_path / "definitions"
    definitions_dir.mkdir()
    return definitions_dir


def test_floors_and_locations_repos_load_valid_defs(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _write_json(
        definitions_dir / "locations.json",
        {
            "start": {
                "name": "Start",
                "description": "Start here.",
                "floor_id": "floor_zero",
                "type": "town",
                "tags": ["town"],
                "entry_story_node_id": None,
                "connections": [],
            }
        },
    )
    _write_json(
        definitions_dir / "floors.json",
        {
            "floor_zero": {
                "name": "Floor Zero",
                "level": 0,
                "starting_location_id": "start",
            }
        },
    )

    floors_repo = FloorsRepository(base_path=definitions_dir)
    locations_repo = LocationsRepository(floors_repo=floors_repo, base_path=definitions_dir)

    assert floors_repo.get("floor_zero").starting_location_id == "start"
    assert locations_repo.get("start").floor_id == "floor_zero"


def test_floors_repo_rejects_unknown_starting_location(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _write_json(
        definitions_dir / "locations.json",
        {
            "start": {
                "name": "Start",
                "description": "Start here.",
                "floor_id": "floor_zero",
                "type": "town",
                "tags": ["town"],
                "entry_story_node_id": None,
                "connections": [],
            }
        },
    )
    _write_json(
        definitions_dir / "floors.json",
        {
            "floor_zero": {
                "name": "Floor Zero",
                "level": 0,
                "starting_location_id": "missing",
            }
        },
    )

    floors_repo = FloorsRepository(base_path=definitions_dir)
    with pytest.raises(DataReferenceError):
        floors_repo.all()


def test_locations_repo_rejects_invalid_type(tmp_path: Path) -> None:
    definitions_dir = _make_definitions_dir(tmp_path)
    _write_json(
        definitions_dir / "locations.json",
        {
            "start": {
                "name": "Start",
                "description": "Start here.",
                "floor_id": "floor_zero",
                "type": "invalid",
                "tags": ["town"],
                "entry_story_node_id": None,
                "connections": [],
            }
        },
    )
    _write_json(
        definitions_dir / "floors.json",
        {
            "floor_zero": {
                "name": "Floor Zero",
                "level": 0,
                "starting_location_id": "start",
            }
        },
    )

    floors_repo = FloorsRepository(base_path=definitions_dir)
    locations_repo = LocationsRepository(floors_repo=floors_repo, base_path=definitions_dir)
    with pytest.raises(DataValidationError):
        locations_repo.all()
