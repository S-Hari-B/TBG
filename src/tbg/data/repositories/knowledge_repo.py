"""Repository for battle knowledge data."""
from __future__ import annotations

from typing import Dict, List

from tbg.data.errors import DataValidationError
from tbg.data.repositories.base import RepositoryBase
from tbg.domain.defs import KnowledgeEntry


class KnowledgeRepository(RepositoryBase[List[KnowledgeEntry]]):
    """Loads per-member knowledge about enemy tags."""

    def __init__(self, base_path=None) -> None:
        super().__init__("knowledge.json", base_path)

    def _build(self, raw: dict[str, object]) -> Dict[str, List[KnowledgeEntry]]:
        knowledge: Dict[str, List[KnowledgeEntry]] = {}
        for member_id, payload in raw.items():
            member_data = self._require_mapping(payload, f"knowledge '{member_id}'")
            entries: List[KnowledgeEntry] = []
            for entry in self._require_list(member_data.get("known_enemies"), f"knowledge '{member_id}' known_enemies"):
                entry_map = self._require_mapping(entry, f"knowledge '{member_id}' entry")
                revealed_fields = self._require_mapping(
                    entry_map.get("revealed_fields"), f"knowledge '{member_id}' entry.revealed_fields"
                )
                hp_range = None
                if "hp_range" in revealed_fields:
                    hp_range = self._require_hp_range(revealed_fields["hp_range"], f"knowledge '{member_id}' hp_range")
                entries.append(
                    KnowledgeEntry(
                        enemy_tags=tuple(
                            self._require_str_list(entry_map.get("enemy_tags", []), f"knowledge '{member_id}' enemy_tags")
                        ),
                        max_level=self._require_optional_int(entry_map.get("max_level"), f"knowledge '{member_id}' max_level"),
                        hp_range=hp_range,
                        speed_hint=self._require_optional_str(revealed_fields.get("speed_hint"), "speed_hint"),
                        behavior=self._require_optional_str(revealed_fields.get("behavior"), "behavior"),
                    )
                )
            knowledge[member_id] = entries
        return knowledge

    def get_entries(self, member_id: str) -> List[KnowledgeEntry]:
        self._ensure_loaded()
        return self._definitions.get(member_id, [])

    @staticmethod
    def _require_mapping(value: object, context: str) -> dict[str, object]:
        if not isinstance(value, dict):
            raise DataValidationError(f"{context} must be an object.")
        return value

    @staticmethod
    def _require_list(value: object, context: str) -> List[object]:
        if not isinstance(value, list):
            raise DataValidationError(f"{context} must be a list.")
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
    def _require_optional_int(value: object, context: str) -> int | None:
        if value is None:
            return None
        if not isinstance(value, int):
            raise DataValidationError(f"{context} must be an integer.")
        return value

    @staticmethod
    def _require_hp_range(value: object, context: str) -> tuple[int, int]:
        if not isinstance(value, list) or len(value) != 2:
            raise DataValidationError(f"{context} must be a two-value list.")
        low, high = value
        if not isinstance(low, int) or not isinstance(high, int):
            raise DataValidationError(f"{context} values must be integers.")
        return low, high

    @staticmethod
    def _require_optional_str(value: object, context: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise DataValidationError(f"{context} must be a string.")
        return value


