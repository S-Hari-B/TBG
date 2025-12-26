"""Party member repository."""
from __future__ import annotations

from typing import Dict, List

from tbg.data.errors import DataValidationError
from tbg.data.repositories.base import RepositoryBase
from tbg.domain.defs import PartyMemberDef


class PartyMembersRepository(RepositoryBase[PartyMemberDef]):
    """Loads recruitable party member definitions."""

    def __init__(self, base_path=None) -> None:
        super().__init__("party_members.json", base_path)

    def _build(self, raw: dict[str, object]) -> Dict[str, PartyMemberDef]:
        members: Dict[str, PartyMemberDef] = {}
        for raw_id, payload in raw.items():
            member_data = self._require_mapping(payload, f"party member '{raw_id}'")
            base_stats = self._require_mapping(member_data.get("base_stats"), f"party member '{raw_id}' base_stats")
            equipment = self._require_mapping(member_data.get("equipment"), f"party member '{raw_id}' equipment")

            members[raw_id] = PartyMemberDef(
                id=raw_id,
                name=self._require_str(member_data.get("name"), f"party member '{raw_id}' name"),
                base_hp=self._require_int(base_stats.get("max_hp"), f"party member '{raw_id}' base_stats.max_hp"),
                base_mp=self._require_int(base_stats.get("max_mp"), f"party member '{raw_id}' base_stats.max_mp"),
                speed=self._require_int(base_stats.get("speed"), f"party member '{raw_id}' base_stats.speed"),
                weapon_ids=tuple(
                    self._require_str_list(equipment.get("weapons", []), f"party member '{raw_id}' equipment.weapons")
                ),
                armour_id=self._require_optional_str(equipment.get("armour"), f"party member '{raw_id}' equipment.armour"),
                tags=tuple(self._require_str_list(member_data.get("tags", []), f"party member '{raw_id}' tags")),
            )
        return members

    @staticmethod
    def _require_str(value: object, context: str) -> str:
        if not isinstance(value, str):
            raise DataValidationError(f"{context} must be a string.")
        return value

    @staticmethod
    def _require_optional_str(value: object, context: str) -> str | None:
        if value is None:
            return None
        return PartyMembersRepository._require_str(value, context)

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
    def _require_str_list(value: object, context: str) -> List[str]:
        if not isinstance(value, list):
            raise DataValidationError(f"{context} must be a list.")
        result: List[str] = []
        for item in value:
            if not isinstance(item, str):
                raise DataValidationError(f"{context} entries must be strings.")
            result.append(item)
        return result


