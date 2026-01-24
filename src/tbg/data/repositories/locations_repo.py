"""Repository for floor-based location definitions."""
from __future__ import annotations

from typing import Dict, List

from tbg.data.errors import DataReferenceError, DataValidationError
from tbg.data.repositories.base import RepositoryBase
from tbg.domain.defs import (
    LocationConnectionDef,
    LocationDef,
    LocationNpcPresenceDef,
)
from tbg.data.repositories.floors_repo import FloorsRepository


_ALLOWED_LOCATION_TYPES = {"town", "open", "side", "story", "secret", "boss", "gate"}


class LocationsRepository(RepositoryBase[LocationDef]):
    """Loads and validates location definitions."""

    def __init__(self, *, floors_repo: FloorsRepository, base_path=None) -> None:
        super().__init__("locations.json", base_path)
        self._floors_repo = floors_repo

    def _build(self, raw: dict[str, object]) -> Dict[str, LocationDef]:
        locations_raw = self._require_mapping(raw, "locations.json")
        staged: Dict[str, dict[str, object]] = {}
        for location_id, payload in locations_raw.items():
            if not isinstance(location_id, str) or not location_id.strip():
                raise DataValidationError("location id must be a non-empty string.")
            if location_id in staged:
                raise DataValidationError(f"Duplicate location id '{location_id}'.")
            staged[location_id] = self._require_mapping(payload, f"location '{location_id}'")

        definitions: Dict[str, LocationDef] = {}
        for location_id, mapping in staged.items():
            name = self._require_str(mapping.get("name"), f"location '{location_id}' name").strip()
            if not name:
                raise DataValidationError(f"location '{location_id}' name must not be empty.")
            description = self._require_str(
                mapping.get("description"), f"location '{location_id}' description"
            )
            floor_id = self._require_str(mapping.get("floor_id"), f"location '{location_id}' floor_id")
            try:
                self._floors_repo.get(floor_id)
            except KeyError as exc:
                raise DataReferenceError(
                    f"location '{location_id}' references unknown floor '{floor_id}'."
                ) from exc

            location_type = self._require_str(
                mapping.get("type"), f"location '{location_id}' type"
            )
            if location_type not in _ALLOWED_LOCATION_TYPES:
                raise DataValidationError(
                    f"location '{location_id}' type must be one of {sorted(_ALLOWED_LOCATION_TYPES)}."
                )
            area_level = mapping.get("area_level")
            if area_level is not None:
                area_level = self._require_int(
                    area_level, f"location '{location_id}' area_level"
                )
                if area_level < 0:
                    raise DataValidationError(
                        f"location '{location_id}' area_level must be >= 0."
                    )

            tags = tuple(
                self._require_str_list(mapping.get("tags"), f"location '{location_id}' tags")
            )
            if not tags:
                raise DataValidationError(f"location '{location_id}' must define at least one tag.")
            if any(tag.lower() != tag for tag in tags):
                raise DataValidationError(f"location '{location_id}' tags must be lowercase.")

            entry_story_node_id = mapping.get("entry_story_node_id")
            if entry_story_node_id is not None:
                entry_story_node_id = self._require_str(
                    entry_story_node_id, f"location '{location_id}' entry_story_node_id"
                )
            entry_story_repeatable = mapping.get("entry_story_repeatable", False)
            if not isinstance(entry_story_repeatable, bool):
                raise DataValidationError(
                    f"location '{location_id}' entry_story_repeatable must be a boolean if provided."
                )

            connections_data = self._require_list(
                mapping.get("connections"), f"location '{location_id}' connections"
            )
            connections: List[LocationConnectionDef] = []
            for index, connection in enumerate(connections_data):
                conn_map = self._require_mapping(
                    connection, f"location '{location_id}' connections[{index}]"
                )
                to_id = self._require_str(
                    conn_map.get("to"), f"location '{location_id}' connections[{index}].to"
                ).strip()
                if to_id not in staged:
                    raise DataReferenceError(
                        f"location '{location_id}' connection references unknown location '{to_id}'."
                    )
                label = self._require_str(
                    conn_map.get("label"), f"location '{location_id}' connections[{index}].label"
                )
                progresses_story = conn_map.get("progresses_story", False)
                if not isinstance(progresses_story, bool):
                    raise DataValidationError(
                        f"location '{location_id}' connections[{index}].progresses_story must be a boolean if provided."
                    )
                requires_quest_active = conn_map.get("requires_quest_active")
                if requires_quest_active is not None and not isinstance(requires_quest_active, str):
                    raise DataValidationError(
                        f"location '{location_id}' connections[{index}].requires_quest_active must be a string if provided."
                    )
                hide_if_quest_completed = conn_map.get("hide_if_quest_completed")
                if hide_if_quest_completed is not None and not isinstance(hide_if_quest_completed, str):
                    raise DataValidationError(
                        f"location '{location_id}' connections[{index}].hide_if_quest_completed must be a string if provided."
                    )
                hide_if_quest_turned_in = conn_map.get("hide_if_quest_turned_in")
                if hide_if_quest_turned_in is not None and not isinstance(hide_if_quest_turned_in, str):
                    raise DataValidationError(
                        f"location '{location_id}' connections[{index}].hide_if_quest_turned_in must be a string if provided."
                    )
                show_if_flag_true = conn_map.get("show_if_flag_true")
                if show_if_flag_true is not None and not isinstance(show_if_flag_true, str):
                    raise DataValidationError(
                        f"location '{location_id}' connections[{index}].show_if_flag_true must be a string if provided."
                    )
                hide_if_flag_true = conn_map.get("hide_if_flag_true")
                if hide_if_flag_true is not None and not isinstance(hide_if_flag_true, str):
                    raise DataValidationError(
                        f"location '{location_id}' connections[{index}].hide_if_flag_true must be a string if provided."
                    )
                connections.append(
                    LocationConnectionDef(
                        to_id=to_id,
                        label=label,
                        progresses_story=progresses_story,
                        requires_quest_active=requires_quest_active,
                        hide_if_quest_completed=hide_if_quest_completed,
                        hide_if_quest_turned_in=hide_if_quest_turned_in,
                        show_if_flag_true=show_if_flag_true,
                        hide_if_flag_true=hide_if_flag_true,
                    )
                )

            npcs_present: List[LocationNpcPresenceDef] = []
            npcs_data = mapping.get("npcs_present", [])
            if npcs_data:
                for index, npc in enumerate(
                    self._require_list(npcs_data, f"location '{location_id}' npcs_present")
                ):
                    npc_map = self._require_mapping(
                        npc, f"location '{location_id}' npcs_present[{index}]"
                    )
                    npc_id = self._require_str(
                        npc_map.get("npc_id"), f"location '{location_id}' npcs_present[{index}].npc_id"
                    )
                    talk_node_id = npc_map.get("talk_node_id")
                    if talk_node_id is not None:
                        talk_node_id = self._require_str(
                            talk_node_id,
                            f"location '{location_id}' npcs_present[{index}].talk_node_id",
                        )
                    quest_hub_node_id = npc_map.get("quest_hub_node_id")
                    if quest_hub_node_id is not None:
                        quest_hub_node_id = self._require_str(
                            quest_hub_node_id,
                            f"location '{location_id}' npcs_present[{index}].quest_hub_node_id",
                        )
                    npcs_present.append(
                        LocationNpcPresenceDef(
                            npc_id=npc_id,
                            talk_node_id=talk_node_id,
                            quest_hub_node_id=quest_hub_node_id,
                        )
                    )

            definitions[location_id] = LocationDef(
                id=location_id,
                name=name,
                description=description,
                floor_id=floor_id,
                location_type=location_type,
                area_level=area_level,
                tags=tuple(tags),
                connections=tuple(connections),
                entry_story_node_id=entry_story_node_id,
                entry_story_repeatable=entry_story_repeatable,
                npcs_present=tuple(npcs_present),
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
    def _require_int(value: object, context: str) -> int:
        if not isinstance(value, int):
            raise DataValidationError(f"{context} must be an integer.")
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
