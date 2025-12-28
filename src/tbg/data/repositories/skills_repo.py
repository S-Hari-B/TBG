"""Skills repository."""
from __future__ import annotations

from typing import Dict, List

from tbg.data.errors import DataValidationError
from tbg.data.repositories.base import RepositoryBase
from tbg.domain.defs import SkillDef

VALID_TARGET_MODES = {"single_enemy", "multi_enemy", "self"}
VALID_EFFECT_TYPES = {"damage", "guard"}


class SkillsRepository(RepositoryBase[SkillDef]):
    """Loads weapon-tag skills."""

    def __init__(self, base_path=None) -> None:
        super().__init__("skills.json", base_path)

    def _build(self, raw: dict[str, object]) -> Dict[str, SkillDef]:
        skills: Dict[str, SkillDef] = {}
        for raw_id, payload in raw.items():
            if not isinstance(raw_id, str):
                raise DataValidationError("Skill IDs must be strings.")
            skill_data = self._require_mapping(payload, f"skill '{raw_id}'")
            self._assert_required(
                skill_data,
                {
                    "name",
                    "description",
                    "tags",
                    "required_weapon_tags",
                    "target_mode",
                    "max_targets",
                    "mp_cost",
                    "base_power",
                    "effect_type",
                    "gold_value",
                },
                f"skill '{raw_id}'",
            )

            target_mode = self._require_literal(
                skill_data["target_mode"], VALID_TARGET_MODES, f"skill '{raw_id}' target_mode"
            )
            effect_type = self._require_literal(
                skill_data["effect_type"], VALID_EFFECT_TYPES, f"skill '{raw_id}' effect_type"
            )

            skills[raw_id] = SkillDef(
                id=raw_id,
                name=self._require_str(skill_data["name"], f"skill '{raw_id}' name"),
                description=self._require_str(skill_data["description"], f"skill '{raw_id}' description"),
                tags=tuple(self._require_str_list(skill_data["tags"], f"skill '{raw_id}' tags")),
                required_weapon_tags=tuple(
                    self._require_str_list(skill_data["required_weapon_tags"], f"skill '{raw_id}' required_weapon_tags")
                ),
                target_mode=target_mode,
                max_targets=self._require_int(skill_data["max_targets"], f"skill '{raw_id}' max_targets"),
                mp_cost=self._require_int(skill_data["mp_cost"], f"skill '{raw_id}' mp_cost"),
                base_power=self._require_int(skill_data["base_power"], f"skill '{raw_id}' base_power"),
                effect_type=effect_type,
                gold_value=self._require_int(skill_data["gold_value"], f"skill '{raw_id}' gold_value"),
            )
        return skills

    @staticmethod
    def _require_mapping(value: object, context: str) -> dict[str, object]:
        if not isinstance(value, dict):
            raise DataValidationError(f"{context} must be an object.")
        return value

    @staticmethod
    def _assert_required(payload: dict[str, object], required: set[str], context: str) -> None:
        missing = required - payload.keys()
        if missing:
            raise DataValidationError(f"{context} missing fields: {sorted(missing)}")

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
    def _require_str_list(value: object, context: str) -> List[str]:
        if not isinstance(value, list):
            raise DataValidationError(f"{context} must be a list.")
        result: List[str] = []
        for entry in value:
            if not isinstance(entry, str):
                raise DataValidationError(f"{context} entries must be strings.")
            result.append(entry)
        return result

    @staticmethod
    def _require_literal(value: object, allowed: set[str], context: str) -> str:
        if not isinstance(value, str):
            raise DataValidationError(f"{context} must be a string.")
        if value not in allowed:
            raise DataValidationError(f"{context} must be one of {sorted(allowed)}.")
        return value

