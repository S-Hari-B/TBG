"""Repository for story node definitions."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from tbg.data.errors import DataValidationError
from tbg.data.repositories.base import RepositoryBase
from tbg.data.json_loader import load_json
from tbg.domain.defs import StoryChoiceDef, StoryEffectDef, StoryNodeDef


class StoryRepository(RepositoryBase[StoryNodeDef]):
    """Loads story nodes and validates their structure."""

    def __init__(self, base_path=None) -> None:
        super().__init__("story/index.json", base_path)

    def _load_raw(self) -> dict[str, object]:
        index_path = self._get_file_path()
        index_data = self._load_and_require_dict(index_path, "story index")
        chapters_value = index_data.get("chapters")
        if not isinstance(chapters_value, list) or not chapters_value:
            raise DataValidationError("story index must define a non-empty 'chapters' list.")

        combined: dict[str, object] = {}
        story_root = index_path.parent
        chapters_dir = story_root / "chapters"
        for chapter_entry in chapters_value:
            chapter_name = self._require_str(chapter_entry, "story index chapter entry")
            chapter_path = chapters_dir / chapter_name
            chapter_data = self._load_and_require_dict(chapter_path, f"chapter '{chapter_name}'")
            for node_id, payload in chapter_data.items():
                if not isinstance(node_id, str):
                    raise DataValidationError(f"Story node ids must be strings (found {type(node_id)!r}).")
                if node_id in combined:
                    raise DataValidationError(f"Duplicate story node id '{node_id}' detected across chapters.")
                combined[node_id] = payload
        return combined

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
        self._validate_links(nodes)
        return nodes

    def _validate_links(self, nodes: Dict[str, StoryNodeDef]) -> None:
        node_ids = set(nodes.keys())
        for node in nodes.values():
            if node.next_node_id and node.next_node_id not in node_ids:
                raise DataValidationError(
                    f"Story node '{node.id}' references missing next node '{node.next_node_id}'."
                )
            for choice in node.choices:
                if choice.next_node_id not in node_ids:
                    raise DataValidationError(
                        f"Story node '{node.id}' choice '{choice.label}' references missing node '{choice.next_node_id}'."
                    )

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

    @staticmethod
    def _load_and_require_dict(path: Path, context: str) -> dict[str, object]:
        data = load_json(path)
        if not isinstance(data, dict):
            raise DataValidationError(f"{context} must be a JSON object.")
        return data


