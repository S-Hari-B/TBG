"""Repository for quest definitions."""
from __future__ import annotations

from typing import Dict, List

from tbg.data.errors import DataReferenceError, DataValidationError
from tbg.data.repositories.base import RepositoryBase
from tbg.data.repositories.items_repo import ItemsRepository
from tbg.data.repositories.locations_repo import LocationsRepository
from tbg.data.repositories.story_repo import StoryRepository
from tbg.domain.defs import (
    QuestDef,
    QuestObjectiveDef,
    QuestPrereqDef,
    QuestRewardDef,
    QuestRewardItemDef,
    QuestTurnInDef,
)


class QuestsRepository(RepositoryBase[QuestDef]):
    """Loads and validates quest definitions."""

    def __init__(
        self,
        *,
        items_repo: ItemsRepository,
        locations_repo: LocationsRepository,
        story_repo: StoryRepository,
        base_path=None,
    ) -> None:
        super().__init__("quests.json", base_path)
        self._items_repo = items_repo
        self._locations_repo = locations_repo
        self._story_repo = story_repo

    def _build(self, raw: dict[str, object]) -> Dict[str, QuestDef]:
        container = self._require_mapping(raw, "quests.json")
        raw_quests = self._require_mapping(container.get("quests"), "quests.json.quests")
        definitions: Dict[str, QuestDef] = {}
        for quest_id, quest_payload in raw_quests.items():
            quest_map = self._require_mapping(quest_payload, f"quest '{quest_id}'")
            quest_id_value = self._require_str(quest_map.get("quest_id"), f"quest '{quest_id}' quest_id")
            if quest_id_value != quest_id:
                raise DataValidationError(
                    f"quest '{quest_id}' quest_id must match key (found '{quest_id_value}')."
                )
            name = self._require_str(quest_map.get("name"), f"quest '{quest_id}' name")
            prereqs = self._parse_prereqs(quest_map.get("prereqs"), quest_id)
            objectives = self._parse_objectives(quest_map.get("objectives"), quest_id)
            turn_in = self._parse_turn_in(quest_map.get("turn_in"), quest_id)
            rewards = self._parse_rewards(quest_map.get("rewards"), quest_id)
            accept_flags = tuple(
                self._require_str_list(
                    quest_map.get("accept_flags", []), f"quest '{quest_id}' accept_flags"
                )
            )
            complete_flags = tuple(
                self._require_str_list(
                    quest_map.get("complete_flags", []), f"quest '{quest_id}' complete_flags"
                )
            )
            definitions[quest_id] = QuestDef(
                quest_id=quest_id,
                name=name,
                prereqs=prereqs,
                objectives=tuple(objectives),
                turn_in=turn_in,
                rewards=rewards,
                accept_flags=accept_flags,
                complete_flags=complete_flags,
            )
        return definitions

    def _parse_prereqs(self, value: object, quest_id: str) -> QuestPrereqDef:
        if value is None:
            return QuestPrereqDef(required_flags=tuple(), forbidden_flags=tuple())
        mapping = self._require_mapping(value, f"quest '{quest_id}' prereqs")
        required = tuple(
            self._require_str_list(
                mapping.get("required_flags", []), f"quest '{quest_id}' prereqs.required_flags"
            )
        )
        forbidden = tuple(
            self._require_str_list(
                mapping.get("forbidden_flags", []), f"quest '{quest_id}' prereqs.forbidden_flags"
            )
        )
        return QuestPrereqDef(required_flags=required, forbidden_flags=forbidden)

    def _parse_objectives(self, value: object, quest_id: str) -> List[QuestObjectiveDef]:
        objectives_data = self._require_list(value, f"quest '{quest_id}' objectives")
        objectives: List[QuestObjectiveDef] = []
        if not objectives_data:
            raise DataValidationError(f"quest '{quest_id}' must define at least one objective.")
        for index, entry in enumerate(objectives_data):
            ctx = f"quest '{quest_id}' objectives[{index}]"
            mapping = self._require_mapping(entry, ctx)
            objective_type = self._require_str(mapping.get("type"), f"{ctx}.type")
            label = self._require_str(mapping.get("label"), f"{ctx}.label")
            quantity = mapping.get("quantity", 1)
            if not isinstance(quantity, int) or quantity <= 0:
                raise DataValidationError(f"{ctx}.quantity must be a positive integer.")
            tag = mapping.get("tag")
            item_id = mapping.get("item_id")
            area_id = mapping.get("area_id")
            if objective_type == "kill_tag":
                tag = self._require_str(tag, f"{ctx}.tag")
            elif objective_type == "collect_item":
                item_id = self._require_str(item_id, f"{ctx}.item_id")
                self._validate_item_id(item_id, ctx)
            elif objective_type == "visit_area":
                area_id = self._require_str(area_id, f"{ctx}.area_id")
                self._validate_area_id(area_id, ctx)
            else:
                raise DataValidationError(f"{ctx}.type must be one of kill_tag, collect_item, visit_area.")
            objectives.append(
                QuestObjectiveDef(
                    objective_type=objective_type,  # type: ignore[arg-type]
                    label=label,
                    tag=tag if isinstance(tag, str) else None,
                    item_id=item_id if isinstance(item_id, str) else None,
                    area_id=area_id if isinstance(area_id, str) else None,
                    quantity=quantity,
                )
            )
        return objectives

    def _parse_turn_in(self, value: object, quest_id: str) -> QuestTurnInDef | None:
        if value is None:
            return None
        mapping = self._require_mapping(value, f"quest '{quest_id}' turn_in")
        node_id = self._require_str(mapping.get("node_id"), f"quest '{quest_id}' turn_in.node_id")
        self._validate_story_node_id(node_id, f"quest '{quest_id}' turn_in.node_id")
        npc_id = mapping.get("npc_id")
        if npc_id is not None:
            npc_id = self._require_str(npc_id, f"quest '{quest_id}' turn_in.npc_id")
        return QuestTurnInDef(node_id=node_id, npc_id=npc_id)

    def _parse_rewards(self, value: object, quest_id: str) -> QuestRewardDef:
        mapping = self._require_mapping(value, f"quest '{quest_id}' rewards")
        gold = mapping.get("gold", 0)
        party_exp = mapping.get("party_exp", 0)
        if not isinstance(gold, int) or gold < 0:
            raise DataValidationError(f"quest '{quest_id}' rewards.gold must be a non-negative integer.")
        if not isinstance(party_exp, int) or party_exp < 0:
            raise DataValidationError(
                f"quest '{quest_id}' rewards.party_exp must be a non-negative integer."
            )
        items_data = mapping.get("items", [])
        items: List[QuestRewardItemDef] = []
        for index, entry in enumerate(self._require_list(items_data, f"quest '{quest_id}' rewards.items")):
            item_map = self._require_mapping(entry, f"quest '{quest_id}' rewards.items[{index}]")
            item_id = self._require_str(item_map.get("item_id"), f"quest '{quest_id}' rewards.items[{index}].item_id")
            quantity = item_map.get("quantity", 1)
            if not isinstance(quantity, int) or quantity <= 0:
                raise DataValidationError(
                    f"quest '{quest_id}' rewards.items[{index}].quantity must be positive."
                )
            self._validate_item_id(item_id, f"quest '{quest_id}' rewards.items[{index}]")
            items.append(QuestRewardItemDef(item_id=item_id, quantity=quantity))
        flags_map = mapping.get("set_flags", {})
        flags_mapping = self._require_mapping(flags_map, f"quest '{quest_id}' rewards.set_flags")
        set_flags: List[tuple[str, bool]] = []
        for flag_id, flag_value in flags_mapping.items():
            if not isinstance(flag_id, str) or not isinstance(flag_value, bool):
                raise DataValidationError(f"quest '{quest_id}' rewards.set_flags must map flags to booleans.")
            set_flags.append((flag_id, flag_value))
        return QuestRewardDef(
            gold=gold,
            party_exp=party_exp,
            items=tuple(items),
            set_flags=tuple(set_flags),
        )

    def _validate_item_id(self, item_id: str, context: str) -> None:
        try:
            self._items_repo.get(item_id)
        except KeyError as exc:
            raise DataReferenceError(f"{context} references unknown item '{item_id}'.") from exc

    def _validate_area_id(self, area_id: str, context: str) -> None:
        try:
            self._locations_repo.get(area_id)
            return
        except KeyError as exc:
            raise DataReferenceError(
                f"{context} references unknown location '{area_id}'."
            ) from exc

    def _validate_story_node_id(self, node_id: str, context: str) -> None:
        try:
            self._story_repo.get(node_id)
        except KeyError as exc:
            raise DataReferenceError(f"{context} references unknown story node '{node_id}'.") from exc

    @staticmethod
    def _require_mapping(value: object, context: str) -> dict[str, object]:
        if not isinstance(value, dict):
            raise DataValidationError(f"{context} must be an object.")
        return value

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
    def _require_str_list(value: object, context: str) -> List[str]:
        if not isinstance(value, list):
            raise DataValidationError(f"{context} must be a list.")
        result: List[str] = []
        for entry in value:
            if not isinstance(entry, str):
                raise DataValidationError(f"{context} entries must be strings.")
            result.append(entry)
        return result
