"""Service for managing summon loadouts outside battle."""
from __future__ import annotations

from typing import Dict, List

from tbg.data.repositories import ClassesRepository, SummonsRepository
from tbg.domain.defs import SummonDef
from tbg.domain.entities import Attributes
from tbg.domain.state import GameState


class SummonLoadoutService:
    """Manage known and equipped summons for the player."""

    def __init__(
        self,
        *,
        classes_repo: ClassesRepository,
        summons_repo: SummonsRepository,
    ) -> None:
        self._classes_repo = classes_repo
        self._summons_repo = summons_repo

    def list_known_summons(self, state: GameState) -> List[SummonDef]:
        self._ensure_owned_summons(state)
        owned = {summon_id for summon_id, count in state.owned_summons.items() if count > 0}
        if not owned:
            return []
        known: List[SummonDef] = []
        for summon_id in sorted(owned):
            try:
                known.append(self._summons_repo.get(summon_id))
            except KeyError:
                continue
        return known

    def get_owned_summons(self, state: GameState) -> Dict[str, int]:
        self._ensure_owned_summons(state)
        return dict(state.owned_summons)

    def get_equipped_summons(self, state: GameState, owner_id: str) -> List[str]:
        if not self._is_owner_available(state, owner_id):
            return []
        if state.player and owner_id == state.player.id:
            return list(state.player.equipped_summons)
        return list(state.party_member_summon_loadouts.get(owner_id, []))

    def equip_summon(self, state: GameState, owner_id: str, summon_id: str) -> None:
        if not self._is_owner_available(state, owner_id):
            raise ValueError("Summon owner is not available.")
        try:
            summon_def = self._summons_repo.get(summon_id)
        except KeyError as exc:
            raise ValueError(f"Summon '{summon_id}' is not known.") from exc
        self._ensure_owned_summons(state)
        owned_count = state.owned_summons.get(summon_id, 0)
        if owned_count <= 0:
            raise ValueError(f"You don't own another {summon_def.name}. Acquire one first.")
        equipped_total = self._total_equipped_count(state, summon_id)
        if equipped_total >= owned_count:
            raise ValueError(f"You don't own another {summon_def.name}. Acquire one first.")
        capacity = self._owner_bond_capacity(state, owner_id)
        current_cost = self._current_bond_cost_for_owner(state, owner_id)
        if current_cost + summon_def.bond_cost > capacity:
            raise ValueError(
                f"Not enough BOND capacity ({current_cost}/{capacity}). "
                f"{summon_id} costs {summon_def.bond_cost}."
            )
        self._loadout_for_owner(state, owner_id).append(summon_id)

    def unequip_summon(self, state: GameState, owner_id: str, index: int) -> None:
        if not self._is_owner_available(state, owner_id):
            raise ValueError("Summon owner is not available.")
        loadout = self._loadout_for_owner(state, owner_id)
        if index < 0 or index >= len(loadout):
            raise ValueError("Summon slot is out of range.")
        loadout.pop(index)

    def move_equipped_summon(self, state: GameState, owner_id: str, from_index: int, to_index: int) -> None:
        if not self._is_owner_available(state, owner_id):
            raise ValueError("Summon owner is not available.")
        equipped = self._loadout_for_owner(state, owner_id)
        if from_index < 0 or from_index >= len(equipped):
            raise ValueError("Summon slot is out of range.")
        if to_index < 0 or to_index >= len(equipped):
            raise ValueError("Summon slot is out of range.")
        if from_index == to_index:
            return
        summon_id = equipped.pop(from_index)
        equipped.insert(to_index, summon_id)

    def _current_bond_cost_for_owner(self, state: GameState, owner_id: str) -> int:
        total = 0
        for summon_id in self._loadout_for_owner(state, owner_id):
            total += self._summons_repo.get(summon_id).bond_cost
        return total

    def _ensure_owned_summons(self, state: GameState) -> None:
        if not state.player:
            return
        if state.owned_summons:
            return
        try:
            class_def = self._classes_repo.get(state.player.class_id)
        except KeyError:
            return
        owned: Dict[str, int] = dict(state.owned_summons)
        for summon_id in class_def.default_equipped_summons:
            owned[summon_id] = owned.get(summon_id, 0) + 1
        for summon_id in class_def.known_summons:
            owned[summon_id] = max(owned.get(summon_id, 0), 1)
        for summon_id in state.player.equipped_summons:
            owned[summon_id] = max(owned.get(summon_id, 0), 1)
        for loadout in state.party_member_summon_loadouts.values():
            for summon_id in loadout:
                owned[summon_id] = max(owned.get(summon_id, 0), 1)
        state.owned_summons = owned

    def _loadout_for_owner(self, state: GameState, owner_id: str) -> List[str]:
        if state.player and owner_id == state.player.id:
            return state.player.equipped_summons
        return state.party_member_summon_loadouts.setdefault(owner_id, [])

    def _is_owner_available(self, state: GameState, owner_id: str) -> bool:
        if state.player and owner_id == state.player.id:
            return True
        return owner_id in state.party_members

    def _owner_bond_capacity(self, state: GameState, owner_id: str) -> int:
        if state.player and owner_id == state.player.id:
            return state.player.attributes.BOND
        return state.party_member_attributes.get(
            owner_id, Attributes(STR=0, DEX=0, INT=0, VIT=0, BOND=0)
        ).BOND

    def _total_equipped_count(self, state: GameState, summon_id: str) -> int:
        total = 0
        if state.player:
            total += state.player.equipped_summons.count(summon_id)
        for loadout in state.party_member_summon_loadouts.values():
            total += loadout.count(summon_id)
        return total
