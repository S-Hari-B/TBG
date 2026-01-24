"""Attribute allocation service (player-only, derived points)."""
from __future__ import annotations

from dataclasses import dataclass

from tbg.data.repositories import ClassesRepository
from tbg.domain.attribute_scaling import apply_attribute_scaling
from tbg.domain.state import GameState

POINTS_PER_LEVEL = 1
ALLOWED_ATTRIBUTES = ("STR", "DEX", "INT", "VIT", "BOND")


@dataclass(frozen=True, slots=True)
class AttributePointSummary:
    earned: int
    spent: int
    available: int
    debug_bonus: int
    starting_level: int
    current_level: int


@dataclass(frozen=True, slots=True)
class AttributeSpendResult:
    success: bool
    message: str
    summary: AttributePointSummary


@dataclass(frozen=True, slots=True)
class AttributeGrantResult:
    success: bool
    message: str
    summary: AttributePointSummary


class AttributeAllocationService:
    """Compute derived attribute points and apply player allocations."""

    def __init__(self, *, classes_repo: ClassesRepository) -> None:
        self._classes_repo = classes_repo

    def get_player_attribute_points_summary(self, state: GameState) -> AttributePointSummary:
        player = self._require_player(state)
        starting_level = self._classes_repo.get_starting_level(player.class_id)
        current_level = state.member_levels.get(player.id, starting_level)
        total_earned = max(0, (current_level - starting_level) * POINTS_PER_LEVEL)
        spent = max(0, state.player_attribute_points_spent)
        derived_available = max(0, total_earned - spent)
        debug_bonus = max(0, state.player_attribute_points_debug_bonus)
        available = derived_available + debug_bonus
        return AttributePointSummary(
            earned=total_earned,
            spent=spent,
            available=available,
            debug_bonus=debug_bonus,
            starting_level=starting_level,
            current_level=current_level,
        )

    def spend_player_attribute_point(self, state: GameState, attribute: str) -> AttributeSpendResult:
        player = self._require_player(state)
        if attribute not in ALLOWED_ATTRIBUTES:
            summary = self.get_player_attribute_points_summary(state)
            return AttributeSpendResult(
                success=False,
                message="Invalid attribute selection.",
                summary=summary,
            )
        summary = self.get_player_attribute_points_summary(state)
        if summary.available <= 0:
            return AttributeSpendResult(
                success=False,
                message="No attribute points available.",
                summary=summary,
            )
        derived_available = max(0, summary.earned - summary.spent)
        if derived_available > 0:
            state.player_attribute_points_spent = summary.spent + 1
        else:
            state.player_attribute_points_debug_bonus = max(0, summary.debug_bonus - 1)
        current_value = getattr(player.attributes, attribute)
        setattr(player.attributes, attribute, current_value + 1)
        player.stats = apply_attribute_scaling(
            player.base_stats,
            player.attributes,
            current_hp=player.stats.hp,
            current_mp=player.stats.mp,
        )
        updated = self.get_player_attribute_points_summary(state)
        return AttributeSpendResult(
            success=True,
            message=f"{attribute} increased to {getattr(player.attributes, attribute)}.",
            summary=updated,
        )

    def grant_debug_attribute_points(self, state: GameState, amount: int) -> AttributeGrantResult:
        if amount <= 0:
            summary = self.get_player_attribute_points_summary(state)
            return AttributeGrantResult(
                success=False,
                message="Grant amount must be at least 1.",
                summary=summary,
            )
        state.player_attribute_points_debug_bonus = (
            max(0, state.player_attribute_points_debug_bonus) + amount
        )
        summary = self.get_player_attribute_points_summary(state)
        return AttributeGrantResult(
            success=True,
            message=f"Granted {amount} attribute points.",
            summary=summary,
        )

    @staticmethod
    def _require_player(state: GameState):
        if not state.player:
            raise ValueError("Player is not initialized.")
        return state.player
