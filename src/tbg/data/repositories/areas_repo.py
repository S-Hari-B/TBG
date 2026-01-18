"""Repository for overworld area definitions."""
from __future__ import annotations

from typing import Dict, List

from tbg.data.errors import DataReferenceError, DataValidationError
from tbg.data.repositories.base import RepositoryBase
from tbg.domain.defs import AreaConnectionDef, AreaDef, NpcPresenceDef


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
                progresses_story = conn_map.get("progresses_story", False)
                if not isinstance(progresses_story, bool):
                    raise DataValidationError(
                        f"area '{area_id}' connections[{index}].progresses_story must be a boolean if provided."
                    )
                requires_quest_active = conn_map.get("requires_quest_active")
                if requires_quest_active is not None and not isinstance(requires_quest_active, str):
                    raise DataValidationError(
                        f"area '{area_id}' connections[{index}].requires_quest_active must be a string if provided."
                    )
                hide_if_quest_completed = conn_map.get("hide_if_quest_completed")
                if hide_if_quest_completed is not None and not isinstance(hide_if_quest_completed, str):
                    raise DataValidationError(
                        f"area '{area_id}' connections[{index}].hide_if_quest_completed must be a string if provided."
                    )
                hide_if_quest_turned_in = conn_map.get("hide_if_quest_turned_in")
                if hide_if_quest_turned_in is not None and not isinstance(hide_if_quest_turned_in, str):
                    raise DataValidationError(
                        f"area '{area_id}' connections[{index}].hide_if_quest_turned_in must be a string if provided."
                    )
                show_if_flag_true = conn_map.get("show_if_flag_true")
                if show_if_flag_true is not None and not isinstance(show_if_flag_true, str):
                    raise DataValidationError(
                        f"area '{area_id}' connections[{index}].show_if_flag_true must be a string if provided."
                    )
                hide_if_flag_true = conn_map.get("hide_if_flag_true")
                if hide_if_flag_true is not None and not isinstance(hide_if_flag_true, str):
                    raise DataValidationError(
                        f"area '{area_id}' connections[{index}].hide_if_flag_true must be a string if provided."
                    )
                connections.append(
                    AreaConnectionDef(
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
            entry_story_node_id = area_map.get("entry_story_node_id")
            if entry_story_node_id is not None:
                entry_story_node_id = self._require_str(
                    entry_story_node_id, f"area '{area_id}' entry_story_node_id"
                )
            npcs_present: List[NpcPresenceDef] = []
            npcs_data = area_map.get("npcs_present", [])
            if npcs_data:
                for index, npc in enumerate(self._require_list(npcs_data, f"area '{area_id}' npcs_present")):
                    npc_map = self._require_mapping(npc, f"area '{area_id}' npcs_present[{index}]")
                    npc_id = self._require_str(
                        npc_map.get("npc_id"), f"area '{area_id}' npcs_present[{index}].npc_id"
                    )
                    talk_node_id = self._require_str(
                        npc_map.get("talk_node_id"),
                        f"area '{area_id}' npcs_present[{index}].talk_node_id",
                    )
                    quest_hub_node_id = npc_map.get("quest_hub_node_id")
                    if quest_hub_node_id is not None:
                        quest_hub_node_id = self._require_str(
                            quest_hub_node_id,
                            f"area '{area_id}' npcs_present[{index}].quest_hub_node_id",
                        )
                    npcs_present.append(
                        NpcPresenceDef(
                            npc_id=npc_id,
                            talk_node_id=talk_node_id,
                            quest_hub_node_id=quest_hub_node_id,
                        )
                    )

            definitions[area_id] = AreaDef(
                id=area_id,
                name=name,
                description=description,
                tags=tuple(tags),
                connections=tuple(connections),
                entry_story_node_id=entry_story_node_id,
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

