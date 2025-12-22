"""Enemies repository."""
from __future__ import annotations

from typing import Dict

from tbg.data.errors import DataValidationError
from tbg.data.repositories.base import RepositoryBase
from tbg.domain.defs import EnemyDef


class EnemiesRepository(RepositoryBase[EnemyDef]):
    """Loads and validates enemy definitions."""

    def __init__(self, base_path=None) -> None:
        super().__init__("enemies.json", base_path)

    def _build(self, raw: dict[str, object]) -> Dict[str, EnemyDef]:
        enemies: Dict[str, EnemyDef] = {}
        for raw_id, payload in raw.items():
            if not isinstance(raw_id, str):
                raise DataValidationError("Enemy IDs must be strings.")
            enemy_data = self._require_mapping(payload, f"enemy '{raw_id}'")
            self._assert_exact_fields(
                enemy_data,
                {"name", "max_hp", "attack", "defense", "xp", "gold"},
                f"enemy '{raw_id}'",
            )

            name = self._require_str(enemy_data["name"], f"enemy '{raw_id}' name")
            max_hp = self._require_int(enemy_data["max_hp"], f"enemy '{raw_id}' max_hp")
            attack = self._require_int(enemy_data["attack"], f"enemy '{raw_id}' attack")
            defense = self._require_int(enemy_data["defense"], f"enemy '{raw_id}' defense")
            xp = self._require_int(enemy_data["xp"], f"enemy '{raw_id}' xp")
            gold = self._require_int(enemy_data["gold"], f"enemy '{raw_id}' gold")

            enemies[raw_id] = EnemyDef(
                id=raw_id,
                name=name,
                max_hp=max_hp,
                attack=attack,
                defense=defense,
                xp=xp,
                gold=gold,
            )
        return enemies

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
    def _assert_exact_fields(payload: dict[str, object], expected_keys: set[str], context: str) -> None:
        actual_keys = set(payload.keys())
        if actual_keys != expected_keys:
            missing = expected_keys - actual_keys
            unknown = actual_keys - expected_keys
            msg_parts = []
            if missing:
                msg_parts.append(f"missing fields: {sorted(missing)}")
            if unknown:
                msg_parts.append(f"unknown fields: {sorted(unknown)}")
            raise DataValidationError(f"{context} has schema issues ({'; '.join(msg_parts)}).")


