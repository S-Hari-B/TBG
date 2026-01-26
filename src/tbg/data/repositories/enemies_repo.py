"""Enemies repository."""
from __future__ import annotations

from typing import Dict, List

from tbg.data.errors import DataValidationError
from tbg.data.repositories.base import RepositoryBase
from tbg.domain.defs import EnemyDef


class EnemiesRepository(RepositoryBase[EnemyDef]):
    """Loads and validates enemy definitions."""

    def __init__(self, base_path=None) -> None:
        super().__init__("enemies.json", base_path)
        self._group_definitions: Dict[str, EnemyDef] = {}

    def _build(self, raw: dict[str, object]) -> Dict[str, EnemyDef]:
        enemies: Dict[str, EnemyDef] = {}
        self._group_definitions = {}
        for raw_id, payload in raw.items():
            if not isinstance(raw_id, str):
                raise DataValidationError("Enemy IDs must be strings.")
            enemy_data = self._require_mapping(payload, f"enemy '{raw_id}'")
            if "enemy_ids" in enemy_data:
                group_ids = self._require_str_list(enemy_data["enemy_ids"], f"enemy '{raw_id}' enemy_ids")
                tags = self._require_str_list(enemy_data.get("tags", []), f"enemy '{raw_id}' tags")
                knowledge_key = self._require_optional_non_empty_str(
                    enemy_data.get("knowledge_key"), f"enemy '{raw_id}' knowledge_key"
                )
                self._group_definitions[raw_id] = EnemyDef(
                    id=raw_id,
                    name=self._require_str(enemy_data.get("name"), f"enemy '{raw_id}' name"),
                    enemy_ids=tuple(group_ids),
                    tags=tuple(tags),
                    knowledge_key=knowledge_key,
                )
                continue

            required_fields = {"name", "hp", "mp", "attack", "defense", "speed", "rewards_exp", "rewards_gold"}
            self._assert_required(enemy_data, required_fields, f"enemy '{raw_id}'")

            tags = self._require_str_list(enemy_data.get("tags", []), f"enemy '{raw_id}' tags")
            equipment = self._require_mapping(enemy_data.get("equipment", {}), f"enemy '{raw_id}' equipment")
            weapon_ids = tuple(
                self._require_str_list(equipment.get("weapons", []), f"enemy '{raw_id}' equipment.weapons")
            )
            armour_slots = self._parse_armour_slots(equipment.get("armour_slots"), raw_id)
            armour_id = self._require_optional_str(equipment.get("armour"), f"enemy '{raw_id}' equipment.armour")
            enemy_skill_ids = tuple(
                self._require_str_list(enemy_data.get("enemy_skill_ids", []), f"enemy '{raw_id}' enemy_skill_ids")
            )
            knowledge_key = self._require_optional_non_empty_str(
                enemy_data.get("knowledge_key"), f"enemy '{raw_id}' knowledge_key"
            )

            enemies[raw_id] = EnemyDef(
                id=raw_id,
                name=self._require_str(enemy_data["name"], f"enemy '{raw_id}' name"),
                hp=self._require_int(enemy_data["hp"], f"enemy '{raw_id}' hp"),
                mp=self._require_int(enemy_data["mp"], f"enemy '{raw_id}' mp"),
                attack=self._require_int(enemy_data["attack"], f"enemy '{raw_id}' attack"),
                defense=self._require_int(enemy_data["defense"], f"enemy '{raw_id}' defense"),
                speed=self._require_int(enemy_data["speed"], f"enemy '{raw_id}' speed"),
                rewards_exp=self._require_int(enemy_data["rewards_exp"], f"enemy '{raw_id}' rewards_exp"),
                rewards_gold=self._require_int(enemy_data["rewards_gold"], f"enemy '{raw_id}' rewards_gold"),
                tags=tuple(tags),
                knowledge_key=knowledge_key,
                weapon_ids=weapon_ids,
                armour_id=armour_id,
                armour_slots=armour_slots,
                enemy_skill_ids=enemy_skill_ids,
            )
        return enemies

    def get_group(self, group_id: str) -> EnemyDef:
        """Return a group definition."""
        self._ensure_loaded()
        try:
            return self._group_definitions[group_id]
        except KeyError as exc:
            raise KeyError(group_id) from exc

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
            raise DataValidationError(f"{context} must be an object.")
        return value

    @staticmethod
    def _require_optional_str(value: object, context: str) -> str | None:
        if value is None:
            return None
        return EnemiesRepository._require_str(value, context)

    @staticmethod
    def _require_optional_non_empty_str(value: object, context: str) -> str | None:
        if value is None:
            return None
        text = EnemiesRepository._require_str(value, context)
        if not text.strip():
            raise DataValidationError(f"{context} must be a non-empty string.")
        return text

    @staticmethod
    def _require_str_list(value: object, context: str) -> List[str]:
        if not isinstance(value, list):
            raise DataValidationError(f"{context} must be a list.")
        result: List[str] = []
        for item in value:
            if not isinstance(item, str):
                raise DataValidationError(f"{context} entries must be strings.")
            result.append(item)
        return result

    @staticmethod
    def _require_slot_name(value: str, context: str) -> str:
        if value not in {"head", "body", "hands", "boots"}:
            raise DataValidationError(f"{context} must be one of head, body, hands, boots.")
        return value

    def _parse_armour_slots(
        self,
        raw_slots: object,
        enemy_id: str,
    ) -> dict[str, str]:
        if raw_slots is None:
            return {}
        mapping = self._require_mapping(raw_slots, f"enemy '{enemy_id}' equipment.armour_slots")
        parsed: dict[str, str] = {}
        for slot_name, armour_id in mapping.items():
            slot = self._require_slot_name(slot_name, f"enemy '{enemy_id}' armour slot")
            parsed[slot] = self._require_str(armour_id, f"enemy '{enemy_id}' armour slot '{slot}'")
        return parsed

    @staticmethod
    def _assert_required(payload: dict[str, object], required: set[str], context: str) -> None:
        missing = required - payload.keys()
        if missing:
            raise DataValidationError(f"{context} missing fields: {sorted(missing)}")


