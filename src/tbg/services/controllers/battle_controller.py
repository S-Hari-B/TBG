"""UI-agnostic battle controller that separates state progression from rendering."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Sequence, Tuple

from tbg.core.rng import RNG
from tbg.domain.battle_models import BattleState, Combatant
from tbg.domain.defs import SkillDef
from tbg.domain.state import GameState
from tbg.services.battle_service import (
    BattleEvent,
    BattleInventoryItem,
    BattleService,
    BattleView,
    PartyTalkPreviewGroup,
)


BattleActionType = Literal["attack", "skill", "talk", "item"]


@dataclass(slots=True)
class BattleAction:
    """Represents a structured action decision from the player."""

    action_type: BattleActionType
    target_id: str | None = None
    target_ids: Sequence[str] | None = None
    skill_id: str | None = None
    speaker_id: str | None = None
    item_id: str | None = None


class BattleController:
    """
    UI-agnostic controller for battle state progression.

    This controller wraps BattleService and exposes only structured state and actions.
    It does NOT handle rendering, formatting, or input prompts.

    Responsibilities:
    - Wrap existing BattleService behavior
    - Expose structured state (current actor, available actions, etc.)
    - Apply player/AI actions and return events
    - Determine if state panel should be shown

    Non-responsibilities (handled by presentation layer):
    - Rendering state panels, results, or events
    - Prompting for user input
    - Formatting text or boxed panels
    """

    def __init__(self, battle_service: BattleService) -> None:
        self._service = battle_service

    def get_battle_view(self, battle_state: BattleState) -> BattleView:
        """Return structured view of current battle state for rendering."""
        return self._service.get_battle_view(battle_state)

    def refresh_knowledge_snapshot(self, battle_state: BattleState, state: GameState) -> None:
        self._service.refresh_knowledge_snapshot(battle_state, state)

    def is_player_controlled_turn(self, battle_state: BattleState, state: GameState) -> bool:
        """Check if the current actor is the player-controlled character."""
        if not state.player:
            return False
        actor_id = battle_state.current_actor_id
        if not actor_id:
            return False
        return actor_id == state.player.id

    def is_ally_ai_turn(self, battle_state: BattleState, state: GameState) -> bool:
        """Check if the current actor is a non-player ally."""
        actor_id = battle_state.current_actor_id
        if not actor_id:
            return False
        if self.is_player_controlled_turn(battle_state, state):
            return False
        for ally in battle_state.allies:
            if ally.instance_id == actor_id:
                return True
        return False

    def is_enemy_turn(self, battle_state: BattleState) -> bool:
        """Check if the current actor is an enemy."""
        actor_id = battle_state.current_actor_id
        if not actor_id:
            return False
        for enemy in battle_state.enemies:
            if enemy.instance_id == actor_id:
                return True
        return False

    def get_available_actions(self, battle_state: BattleState, state: GameState) -> dict:
        """
        Return structured data about available actions for the current player turn.

        Returns a dict with:
        - can_attack: bool
        - can_use_skill: bool
        - can_use_item: bool
        - can_talk: bool
        - available_skills: List[SkillDef]
        - items: List[BattleInventoryItem]
        """
        actor_id = battle_state.current_actor_id
        if not actor_id:
            return {
                "can_attack": False,
                "can_use_skill": False,
                "can_use_item": False,
                "can_talk": False,
                "available_skills": [],
                "items": [],
            }

        available_skills = self._service.get_available_skills(battle_state, actor_id)
        battle_items = self._service.get_battle_items(state)
        return {
            "can_attack": True,
            "can_use_skill": bool(available_skills),
            "can_use_item": bool(battle_items),
            "can_talk": bool(state.party_members),
            "available_skills": available_skills,
            "items": battle_items,
        }

    def apply_player_action(
        self, battle_state: BattleState, state: GameState, action: BattleAction
    ) -> List[BattleEvent]:
        """
        Apply a player action and return the resulting events.

        This method does NOT print or format anything. It only executes game logic.
        """
        actor_id = battle_state.current_actor_id
        if not actor_id:
            raise ValueError("No current actor.")

        if action.action_type == "attack":
            if not action.target_id:
                raise ValueError("Attack action requires target_id.")
            return self._service.basic_attack(battle_state, actor_id, action.target_id)

        if action.action_type == "skill":
            if not action.skill_id or action.target_ids is None:
                raise ValueError("Skill action requires skill_id and target_ids.")
            return self._service.use_skill(battle_state, actor_id, action.skill_id, action.target_ids)

        if action.action_type == "talk":
            if not action.speaker_id:
                raise ValueError("Talk action requires speaker_id.")
            return self._service.party_talk(battle_state, state, action.speaker_id)

        if action.action_type == "item":
            if not action.item_id or not action.target_id:
                raise ValueError("Item action requires item_id and target_id.")
            return self._service.use_item(battle_state, state, actor_id, action.item_id, action.target_id)

        raise ValueError(f"Unknown action type: {action.action_type}")

    def run_ally_ai_turn(self, battle_state: BattleState, rng: RNG) -> List[BattleEvent]:
        """Execute ally AI logic and return events."""
        actor_id = battle_state.current_actor_id
        if not actor_id:
            return []
        return self._service.run_ally_ai_turn(battle_state, actor_id, rng)

    def run_enemy_turn(self, battle_state: BattleState, rng: RNG) -> List[BattleEvent]:
        """Execute enemy AI logic and return events."""
        return self._service.run_enemy_turn(battle_state, rng)

    def should_render_state_panel(
        self, battle_state: BattleState, state: GameState, *, is_first_turn: bool
    ) -> bool:
        """
        Determine whether to render the full state panel for the current turn.

        Rules:
        - Always render on the first turn of the battle
        - Render at the start of each player-controlled turn
        - Do NOT render for AI ally or enemy turns (compact results only)
        """
        if is_first_turn:
            return True
        return self.is_player_controlled_turn(battle_state, state)

    def apply_victory_rewards(self, battle_state: BattleState, state: GameState) -> List[BattleEvent]:
        """Apply victory rewards and return events."""
        return self._service.apply_victory_rewards(battle_state, state)

    def party_talk_preview(
        self, battle_state: BattleState, state: GameState, speaker_id: str
    ) -> List[PartyTalkPreviewGroup]:
        """Preview Party Talk output without mutating state."""
        return self._service.party_talk_preview(battle_state, state, speaker_id)

    def has_knowledge_of_enemy(self, state: GameState, enemy_tags: Tuple[str, ...]) -> bool:
        """
        Check if any party member has knowledge of an enemy with the given tags.
        
        Returns True if at least one party member knows about enemies with these tags.
        """
        return self._service.party_has_knowledge(state, enemy_tags)

    def estimate_damage(
        self,
        battle_state: BattleState,
        attacker_id: str,
        target_id: str,
        *,
        bonus_power: int = 0,
        minimum: int = 1,
        skill_tags: Sequence[str] | None = None,
    ) -> int:
        """Estimate damage without mutating battle state."""
        return self._service.estimate_damage_for_ids(
            battle_state,
            attacker_id,
            target_id,
            bonus_power=bonus_power,
            minimum=minimum,
            skill_tags=skill_tags,
        )