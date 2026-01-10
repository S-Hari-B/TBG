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

            weapon_ids = tuple(
                self._require_str_list(equipment.get("weapons", []), f"party member '{raw_id}' equipment.weapons")
            )
            armour_slots = self._parse_armour_slots(equipment.get("armour_slots"), raw_id)
            armour_id = self._require_optional_str(equipment.get("armour"), f"party member '{raw_id}' equipment.armour")

            members[raw_id] = PartyMemberDef(
                id=raw_id,
                name=self._require_str(member_data.get("name"), f"party member '{raw_id}' name"),
                base_hp=self._require_int(base_stats.get("max_hp"), f"party member '{raw_id}' base_stats.max_hp"),
                base_mp=self._require_int(base_stats.get("max_mp"), f"party member '{raw_id}' base_stats.max_mp"),
                speed=self._require_int(base_stats.get("speed"), f"party member '{raw_id}' base_stats.speed"),
                starting_level=self._require_int(member_data.get("starting_level"), f"party member '{raw_id}' starting_level"),
                weapon_ids=weapon_ids,
                armour_id=armour_id,
                armour_slots=armour_slots,
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

    @staticmethod
    def _require_slot_name(value: str, context: str) -> str:
        if value not in {"head", "body", "hands", "boots"}:
            raise DataValidationError(f"{context} must be one of head, body, hands, boots.")
        return value

    def _parse_armour_slots(
        self,
        raw_slots: object,
        member_id: str,
    ) -> dict[str, str]:
        if raw_slots is None:
            return {}
        mapping = self._require_mapping(raw_slots, f"party member '{member_id}' equipment.armour_slots")
        parsed: dict[str, str] = {}
        for slot_name, armour_id in mapping.items():
            slot = self._require_slot_name(slot_name, f"party member '{member_id}' armour slot")
            parsed[slot] = self._require_str(armour_id, f"party member '{member_id}' armour slot '{slot}'")
        return parsed


