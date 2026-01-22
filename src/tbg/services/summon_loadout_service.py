"""Service for managing summon loadouts outside battle."""
from __future__ import annotations

from typing import List

from tbg.data.repositories import ClassesRepository, SummonsRepository
from tbg.domain.defs import SummonDef
from tbg.domain.state import GameState


class SummonLoadoutService:
    """Manage known and equipped summons for the player."""

    MAX_EQUIPPED = 4

    def __init__(
        self,
        *,
        classes_repo: ClassesRepository,
        summons_repo: SummonsRepository,
    ) -> None:
        self._classes_repo = classes_repo
        self._summons_repo = summons_repo

    def list_known_summons(self, state: GameState) -> List[SummonDef]:
        if not state.player:
            return []
        try:
            class_def = self._classes_repo.get(state.player.class_id)
        except KeyError:
            return []
        return [self._summons_repo.get(summon_id) for summon_id in class_def.known_summons]

    def get_equipped_summons(self, state: GameState) -> List[str]:
        if not state.player:
            return []
        return list(state.player.equipped_summons)

    def equip_summon(self, state: GameState, summon_id: str) -> None:
        if not state.player:
            raise ValueError("Cannot equip summons without a player.")
        known = {summon.id for summon in self.list_known_summons(state)}
        if summon_id not in known:
            raise ValueError(f"Summon '{summon_id}' is not known.")
        if len(state.player.equipped_summons) >= self.MAX_EQUIPPED:
            raise ValueError("Summon loadout is full.")
        capacity = state.player.attributes.BOND
        current_cost = self._current_bond_cost(state)
        summon_cost = self._summons_repo.get(summon_id).bond_cost
        if current_cost + summon_cost > capacity:
            raise ValueError(
                f"Not enough BOND capacity ({current_cost}/{capacity}). "
                f"{summon_id} costs {summon_cost}."
            )
        state.player.equipped_summons.append(summon_id)

    def unequip_summon(self, state: GameState, index: int) -> None:
        if not state.player:
            raise ValueError("Cannot unequip summons without a player.")
        if index < 0 or index >= len(state.player.equipped_summons):
            raise ValueError("Summon slot is out of range.")
        state.player.equipped_summons.pop(index)

    def move_equipped_summon(self, state: GameState, from_index: int, to_index: int) -> None:
        if not state.player:
            raise ValueError("Cannot reorder summons without a player.")
        equipped = state.player.equipped_summons
        if from_index < 0 or from_index >= len(equipped):
            raise ValueError("Summon slot is out of range.")
        if to_index < 0 or to_index >= len(equipped):
            raise ValueError("Summon slot is out of range.")
        if from_index == to_index:
            return
        summon_id = equipped.pop(from_index)
        equipped.insert(to_index, summon_id)

    def _current_bond_cost(self, state: GameState) -> int:
        if not state.player:
            return 0
        total = 0
        for summon_id in state.player.equipped_summons:
            total += self._summons_repo.get(summon_id).bond_cost
        return total
