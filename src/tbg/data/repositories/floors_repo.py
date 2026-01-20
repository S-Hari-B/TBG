"""Repository for floor definitions."""
from __future__ import annotations

from typing import Dict

from tbg.data.errors import DataReferenceError, DataValidationError
from tbg.data.json_loader import load_json
from tbg.data import paths
from tbg.data.repositories.base import RepositoryBase
from tbg.domain.defs import FloorDef


class FloorsRepository(RepositoryBase[FloorDef]):
    """Loads and validates floor definitions."""

    def __init__(self, base_path=None) -> None:
        super().__init__("floors.json", base_path)

    def _build(self, raw: dict[str, object]) -> Dict[str, FloorDef]:
        floors_raw = self._require_mapping(raw, "floors.json")
        location_ids = self._load_location_ids()
        definitions: Dict[str, FloorDef] = {}
        for floor_id, payload in floors_raw.items():
            if not isinstance(floor_id, str) or not floor_id.strip():
                raise DataValidationError("floor id must be a non-empty string.")
            if floor_id in definitions:
                raise DataValidationError(f"Duplicate floor id '{floor_id}'.")
            mapping = self._require_mapping(payload, f"floor '{floor_id}'")
            if "id" in mapping:
                embedded_id = self._require_str(mapping.get("id"), f"floor '{floor_id}' id")
                if embedded_id != floor_id:
                    raise DataValidationError(
                        f"floor '{floor_id}' id must match its key ('{embedded_id}' found)."
                    )
            name = self._require_str(mapping.get("name"), f"floor '{floor_id}' name").strip()
            if not name:
                raise DataValidationError(f"floor '{floor_id}' name must not be empty.")
            level = self._require_int(mapping.get("level"), f"floor '{floor_id}' level")
            if level < 0:
                raise DataValidationError(f"floor '{floor_id}' level must be >= 0.")
            starting_location_id = self._require_str(
                mapping.get("starting_location_id"), f"floor '{floor_id}' starting_location_id"
            ).strip()
            if not starting_location_id:
                raise DataValidationError(
                    f"floor '{floor_id}' starting_location_id must not be empty."
                )
            if starting_location_id not in location_ids:
                raise DataReferenceError(
                    f"floor '{floor_id}' starting_location_id '{starting_location_id}' not found in locations.json."
                )

            boss_location_id = mapping.get("boss_location_id")
            if boss_location_id is not None:
                boss_location_id = self._require_str(
                    boss_location_id, f"floor '{floor_id}' boss_location_id"
                ).strip()
                if not boss_location_id:
                    raise DataValidationError(
                        f"floor '{floor_id}' boss_location_id must not be empty if provided."
                    )
                if boss_location_id not in location_ids:
                    raise DataReferenceError(
                        f"floor '{floor_id}' boss_location_id '{boss_location_id}' not found in locations.json."
                    )

            next_floor_id = mapping.get("next_floor_id")
            if next_floor_id is not None:
                next_floor_id = self._require_str(
                    next_floor_id, f"floor '{floor_id}' next_floor_id"
                ).strip()
                if not next_floor_id:
                    raise DataValidationError(
                        f"floor '{floor_id}' next_floor_id must not be empty if provided."
                    )

            notes = mapping.get("notes")
            if notes is not None:
                notes = self._require_str(notes, f"floor '{floor_id}' notes")

            definitions[floor_id] = FloorDef(
                id=floor_id,
                name=name,
                level=level,
                starting_location_id=starting_location_id,
                boss_location_id=boss_location_id,
                next_floor_id=next_floor_id,
                notes=notes,
            )
        return definitions

    def _load_location_ids(self) -> set[str]:
        definitions_dir = paths.get_definitions_path(self._base_path)
        locations_path = definitions_dir / "locations.json"
        raw = load_json(locations_path)
        if not isinstance(raw, dict):
            raise DataValidationError("locations.json must be an object.")
        return {key for key in raw.keys() if isinstance(key, str)}

    @staticmethod
    def _require_str(value: object, context: str) -> str:
        if not isinstance(value, str):
            raise DataValidationError(f"{context} must be a string.")
        return value

    @staticmethod
    def _require_int(value: object, context: str) -> int:
        if not isinstance(value, int):
            raise DataValidationError(f"{context} must be an integer.")
        return value
