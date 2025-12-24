"""Repository for story node definitions."""
from __future__ import annotations

from typing import Dict, List

from tbg.data.errors import DataValidationError
from tbg.data.repositories.base import RepositoryBase
from tbg.domain.defs import StoryChoiceDef, StoryEffectDef, StoryNodeDef


class StoryRepository(RepositoryBase[StoryNodeDef]):
    """Loads story nodes and validates their structure."""

    def __init__(self, base_path=None) -> None:
        super().__init__("story.json", base_path)

    def _build(self, raw: dict[str, object]) -> Dict[str, StoryNodeDef]:
        nodes: Dict[str, StoryNodeDef] = {}
        for node_id, node_payload in raw.items():
            if not isinstance(node_id, str):
                raise DataValidationError("Story node ids must be strings.")
            node_data = self._require_mapping(node_payload, f"story node '{node_id}'")
            text = self._require_str(node_data.get("text"), f"story node '{node_id}' text")
            effects = self._parse_effects(node_data.get("effects"), f"story node '{node_id}' effects")
            choices = self._parse_choices(node_data.get("choices"), node_id)
            next_node_id = None
            if "next" in node_data:
                next_node_id = self._require_str(node_data["next"], f"story node '{node_id}' next")

            nodes[node_id] = StoryNodeDef(
                id=node_id,
                text=text,
                effects=effects,
                choices=choices,
                next_node_id=next_node_id,
            )
        return nodes

    def _parse_effects(self, raw_effects: object, context: str) -> List[StoryEffectDef]:
        if raw_effects is None:
            return []
        if not isinstance(raw_effects, list):
            raise DataValidationError(f"{context} must be a list if provided.")
        effects: List[StoryEffectDef] = []
        for index, entry in enumerate(raw_effects):
            effect_ctx = f"{context}[{index}]"
            effect_data = self._require_mapping(entry, effect_ctx)
            effect_type = self._require_str(effect_data.get("type"), f"{effect_ctx} type")
            payload = {key: value for key, value in effect_data.items() if key != "type"}
            effects.append(StoryEffectDef(type=effect_type, data=payload))
        return effects

    def _parse_choices(self, raw_choices: object, node_id: str) -> List[StoryChoiceDef]:
        if raw_choices is None:
            return []
        if not isinstance(raw_choices, list):
            raise DataValidationError(f"story node '{node_id}' choices must be a list if provided.")
        choices: List[StoryChoiceDef] = []
        for index, entry in enumerate(raw_choices):
            choice_ctx = f"story node '{node_id}' choices[{index}]"
            choice_mapping = self._require_mapping(entry, choice_ctx)
            label = self._require_str(choice_mapping.get("label"), f"{choice_ctx} label")
            next_node = self._require_str(choice_mapping.get("next"), f"{choice_ctx} next")
            effects = self._parse_effects(choice_mapping.get("effects"), f"{choice_ctx} effects")
            choices.append(
                StoryChoiceDef(
                    label=label,
                    next_node_id=next_node,
                    effects=effects,
                )
            )
        return choices

    @staticmethod
    def _require_str(value: object, context: str) -> str:
        if not isinstance(value, str):
            raise DataValidationError(f"{context} must be a string.")
        return value


