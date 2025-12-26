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
                self._group_definitions[raw_id] = EnemyDef(
                    id=raw_id,
                    name=self._require_str(enemy_data.get("name"), f"enemy '{raw_id}' name"),
                    enemy_ids=tuple(group_ids),
                    tags=tuple(tags),
                )
                continue

            required_fields = {"name", "hp", "mp", "attack", "defense", "speed", "rewards_exp", "rewards_gold"}
            self._assert_required(enemy_data, required_fields, f"enemy '{raw_id}'")

            tags = self._require_str_list(enemy_data.get("tags", []), f"enemy '{raw_id}' tags")

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
    def _assert_required(payload: dict[str, object], required: set[str], context: str) -> None:
        missing = required - payload.keys()
        if missing:
            raise DataValidationError(f"{context} missing fields: {sorted(missing)}")


