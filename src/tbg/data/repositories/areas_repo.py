"""Repository for overworld area definitions."""
from __future__ import annotations

from typing import Dict, List

from tbg.data.errors import DataReferenceError, DataValidationError
from tbg.data.repositories.base import RepositoryBase
from tbg.domain.defs import AreaConnectionDef, AreaDef


class AreasRepository(RepositoryBase[AreaDef]):
    """Loads and validates travel area definitions."""

    def __init__(self, base_path=None) -> None:
        super().__init__("areas.json", base_path)

    def _build(self, raw: dict[str, object]) -> Dict[str, AreaDef]:
        container = self._require_mapping(raw, "areas.json")
        raw_areas = self._require_list(container.get("areas"), "areas.json.areas")
        staged: Dict[str, dict[str, object]] = {}
        for entry in raw_areas:
            area_map = self._require_mapping(entry, "area entry")
            area_id = self._require_str(area_map.get("id"), "area.id").strip()
            if not area_id:
                raise DataValidationError("area.id must not be empty.")
            if area_id in staged:
                raise DataValidationError(f"Duplicate area id '{area_id}'.")
            staged[area_id] = area_map

        definitions: Dict[str, AreaDef] = {}
        for area_id, area_map in staged.items():
            name = self._require_str(area_map.get("name"), f"area '{area_id}' name")
            description = self._require_str(
                area_map.get("description"), f"area '{area_id}' description"
            )
            tags = tuple(
                self._require_str_list(
                    area_map.get("tags", []), f"area '{area_id}' tags"
                )
            )
            if not tags:
                raise DataValidationError(f"area '{area_id}' must define at least one tag.")
            if any(tag.lower() != tag for tag in tags):
                raise DataValidationError(f"area '{area_id}' tags must be lowercase.")
            connections_data = self._require_list(
                area_map.get("connections"), f"area '{area_id}' connections"
            )
            connections: List[AreaConnectionDef] = []
            for index, connection in enumerate(connections_data):
                conn_map = self._require_mapping(
                    connection, f"area '{area_id}' connections[{index}]"
                )
                to_id = self._require_str(
                    conn_map.get("to"),
                    f"area '{area_id}' connections[{index}].to",
                ).strip()
                if to_id not in staged:
                    raise DataReferenceError(
                        f"area '{area_id}' connection references unknown area '{to_id}'."
                    )
                label = self._require_str(
                    conn_map.get("label"),
                    f"area '{area_id}' connections[{index}].label",
                )
                connections.append(AreaConnectionDef(to_id=to_id, label=label))
            entry_story_node_id = area_map.get("entry_story_node_id")
            if entry_story_node_id is not None:
                entry_story_node_id = self._require_str(
                    entry_story_node_id, f"area '{area_id}' entry_story_node_id"
                )

            definitions[area_id] = AreaDef(
                id=area_id,
                name=name,
                description=description,
                tags=tuple(tags),
                connections=tuple(connections),
                entry_story_node_id=entry_story_node_id,
            )
        return definitions

    @staticmethod
    def _require_list(value: object, context: str) -> list[object]:
        if not isinstance(value, list):
            raise DataValidationError(f"{context} must be a list.")
        return value

    @staticmethod
    def _require_str(value: object, context: str) -> str:
        if not isinstance(value, str):
            raise DataValidationError(f"{context} must be a string.")
        return value

    @staticmethod
    def _require_mapping(value: object, context: str) -> dict[str, object]:
        if not isinstance(value, dict):
            raise DataValidationError(f"{context} must be an object/dict.")
        return value

    @staticmethod
    def _require_str_list(value: object, context: str) -> List[str]:
        if not isinstance(value, list):
            raise DataValidationError(f"{context} must be a list.")
        result: List[str] = []
        for entry in value:
            if not isinstance(entry, str):
                raise DataValidationError(f"{context} entries must be strings.")
            result.append(entry)
        return result

