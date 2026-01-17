"""Story progression services."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence, Tuple

from tbg.core.rng import RNG
from tbg.data.repositories import (
    ArmourRepository,
    ClassesRepository,
    PartyMembersRepository,
    StoryRepository,
    WeaponsRepository,
)
from tbg.domain.defs import StoryEffectDef, StoryNodeDef
from tbg.domain.state import GameState
from tbg.services.factories import create_player_from_class_id
from tbg.services.inventory_service import InventoryService


@dataclass(slots=True)
class StoryNodeView:
    """Data returned to the presentation layer for rendering."""

    node_id: str
    text: str
    choices: List[str]
    segments: List[Tuple[str, str]]


@dataclass(slots=True)
class StoryEvent:
    """Base class for story events."""


@dataclass(slots=True)
class PlayerClassSetEvent(StoryEvent):
    class_id: str
    player_id: str


@dataclass(slots=True)
class BattleRequestedEvent(StoryEvent):
    enemy_id: str


@dataclass(slots=True)
class PartyMemberJoinedEvent(StoryEvent):
    member_id: str


@dataclass(slots=True)
class GoldGainedEvent(StoryEvent):
    amount: int
    total_gold: int


@dataclass(slots=True)
class ExpGainedEvent(StoryEvent):
    amount: int
    total_exp: int


@dataclass(slots=True)
class GameMenuEnteredEvent(StoryEvent):
    message: str


@dataclass(slots=True)
class ChoiceResult:
    """Result returned after applying a choice."""

    events: List[StoryEvent] = field(default_factory=list)
    node_view: StoryNodeView | None = None


class StoryService:
    """Application service that drives the story graph."""

    def __init__(
        self,
        story_repo: StoryRepository,
        classes_repo: ClassesRepository,
        weapons_repo: WeaponsRepository,
        armour_repo: ArmourRepository,
        party_members_repo: PartyMembersRepository,
        *,
        inventory_service: InventoryService | None = None,
        default_player_name: str = "Hero",
    ) -> None:
        self._story_repo = story_repo
        self._classes_repo = classes_repo
        self._weapons_repo = weapons_repo
        self._armour_repo = armour_repo
        self._party_members_repo = party_members_repo
        self._inventory_service = inventory_service or InventoryService(
            weapons_repo=self._weapons_repo,
            armour_repo=self._armour_repo,
            party_members_repo=self._party_members_repo,
        )
        self._default_player_name = default_player_name

    def start_new_game(self, seed: int, player_name: str | None = None) -> GameState:
        """Create a fresh game state and position the story at the intro node."""
        rng = RNG(seed)
        state = GameState(
            seed=seed,
            rng=rng,
            mode="story",
            current_node_id="intro_decree",
        )
        state.player_name = player_name or self._default_player_name
        self._enter_node(state, "intro_decree", [])
        return state

    def get_current_node_view(self, state: GameState) -> StoryNodeView:
        """Return the view model for the currently active node."""
        node = self._current_node(state)
        segments = state.pending_narration or [(node.id, node.text)]
        return StoryNodeView(
            node_id=node.id,
            text=segments[-1][1],
            choices=[choice.label for choice in node.choices],
            segments=list(segments),
        )

    def choose(self, state: GameState, choice_index: int) -> ChoiceResult:
        """Apply the selected choice and advance the story."""
        node = self._current_node(state)
        if not node.choices:
            raise ValueError(f"Story node '{node.id}' has no choices to select.")
        try:
            selected_choice = node.choices[choice_index]
        except IndexError as exc:
            raise IndexError(f"Choice index {choice_index} is invalid for node '{node.id}'.") from exc

        events: List[StoryEvent] = []
        choice_events, halt = self._apply_effects(selected_choice.effects, state)
        events.extend(choice_events)
        if halt:
            state.pending_story_node_id = selected_choice.next_node_id
        else:
            state.pending_story_node_id = None
            self._enter_node(state, selected_choice.next_node_id, events)
        node_view = self.get_current_node_view(state)
        return ChoiceResult(events=events, node_view=node_view)

    def _current_node(self, state: GameState) -> StoryNodeDef:
        return self._story_repo.get(state.current_node_id)

    def _enter_node(self, state: GameState, node_id: str, events: List[StoryEvent]) -> None:
        """Move state to the given node, applying auto-advance rules."""
        state.mode = "story"
        state.camp_message = None
        state.current_node_id = node_id
        state.pending_narration = []
        state.pending_story_node_id = None
        while True:
            node = self._story_repo.get(state.current_node_id)
            state.pending_narration.append((node.id, node.text))
            node_events, halt = self._apply_effects(node.effects, state)
            events.extend(node_events)
            if halt:
                state.pending_story_node_id = node.next_node_id
                return
            if node.choices or not node.next_node_id:
                state.pending_story_node_id = None
                return
            state.current_node_id = node.next_node_id

    def resume_after_battle(self, state: GameState) -> List[StoryEvent]:
        """Resume story flow after a blocking battle."""
        return self.resume_pending_flow(state)

    def resume_pending_flow(self, state: GameState) -> List[StoryEvent]:
        """Resume story flow after any blocking effect."""
        if (
            state.story_checkpoint_node_id
            and state.story_checkpoint_thread_id in (None, "main_story")
            and not state.pending_story_node_id
        ):
            self.rewind_to_checkpoint(state)
        if not state.pending_story_node_id:
            return []
        next_node_id = state.pending_story_node_id
        state.pending_story_node_id = None
        events: List[StoryEvent] = []
        self._enter_node(state, next_node_id, events)
        return events

    def play_node(self, state: GameState, node_id: str) -> List[StoryEvent]:
        """Force-enter a node (used for optional entry hooks)."""
        events: List[StoryEvent] = []
        self._enter_node(state, node_id, events)
        return events

    def _apply_effects(self, effects: Sequence[StoryEffectDef], state: GameState) -> tuple[List[StoryEvent], bool]:
        emitted: List[StoryEvent] = []
        halt_flow = False
        for effect in effects:
            effect_type = effect.type
            if effect_type == "set_class":
                class_id = self._require_str(effect.data.get("class_id"), "set_class.class_id")
                class_def = self._classes_repo.get(class_id)
                starting_level = self._classes_repo.get_starting_level(class_id)
                player = create_player_from_class_id(
                    class_id=class_id,
                    name=state.player_name,
                    classes_repo=self._classes_repo,
                    weapons_repo=self._weapons_repo,
                    armour_repo=self._armour_repo,
                    rng=state.rng,
                )
                state.player = player
                state.member_levels[player.id] = starting_level
                state.member_exp[player.id] = 0
                self._inventory_service.initialize_player_loadout(state, player.id, class_def)
                emitted.append(PlayerClassSetEvent(class_id=class_id, player_id=player.id))
            elif effect_type == "start_battle":
                enemy_id = self._require_str(effect.data.get("enemy_id"), "start_battle.enemy_id")
                self._record_battle_checkpoint(state)
                emitted.append(BattleRequestedEvent(enemy_id=enemy_id))
                halt_flow = True
            elif effect_type == "add_party_member":
                member_id = self._require_str(effect.data.get("member_id"), "add_party_member.member_id")
                if member_id not in state.party_members:
                    state.party_members.append(member_id)
                    try:
                        member_def = self._party_members_repo.get(member_id)
                        self._inventory_service.initialize_party_member_loadout(state, member_id, member_def)
                        state.member_levels[member_id] = member_def.starting_level
                        state.member_exp[member_id] = 0
                    except KeyError:
                        pass
                emitted.append(PartyMemberJoinedEvent(member_id=member_id))
            elif effect_type == "give_gold":
                amount = self._require_int(effect.data.get("amount"), "give_gold.amount")
                state.gold += amount
                emitted.append(GoldGainedEvent(amount=amount, total_gold=state.gold))
            elif effect_type == "give_exp":
                amount = self._require_int(effect.data.get("amount"), "give_exp.amount")
                state.exp += amount
                emitted.append(ExpGainedEvent(amount=amount, total_exp=state.exp))
            elif effect_type == "enter_game_menu":
                message = self._require_optional_str(effect.data.get("message"), "enter_game_menu.message") or ""
                state.mode = "camp_menu"
                state.camp_message = message
                emitted.append(GameMenuEnteredEvent(message=message))
                halt_flow = True
            elif effect_type == "set_flag":
                flag_id = self._require_str(effect.data.get("flag_id"), "set_flag.flag_id")
                value = effect.data.get("value", True)
                if not isinstance(value, bool):
                    raise ValueError("set_flag.value must be a boolean.")
                state.flags[flag_id] = value
            else:
                # Unknown effects are ignored for now to keep the interpreter forward compatible.
                continue
        return emitted, halt_flow

    def clear_checkpoint(self, state: GameState, thread_id: str = "main_story") -> None:
        """Clear any stored story checkpoint after a successful battle."""
        if state.story_checkpoint_thread_id and state.story_checkpoint_thread_id != thread_id:
            return
        state.story_checkpoint_node_id = None
        state.story_checkpoint_location_id = None
        state.story_checkpoint_thread_id = None

    def rewind_to_checkpoint(self, state: GameState, thread_id: str = "main_story") -> bool:
        """Prepare the state to resume from the last checkpoint after defeat."""
        if not state.story_checkpoint_node_id:
            return False
        if state.story_checkpoint_thread_id and state.story_checkpoint_thread_id != thread_id:
            return False
        state.pending_story_node_id = state.story_checkpoint_node_id
        state.pending_narration = []
        state.current_node_id = state.story_checkpoint_node_id
        return True

    def _record_battle_checkpoint(self, state: GameState, thread_id: str = "main_story") -> None:
        state.story_checkpoint_node_id = state.current_node_id
        state.story_checkpoint_location_id = state.current_location_id
        state.story_checkpoint_thread_id = thread_id

    @staticmethod
    def _require_str(value: object, context: str) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{context} must be a string.")
        return value

    @staticmethod
    def _require_int(value: object, context: str) -> int:
        if not isinstance(value, int):
            raise ValueError(f"{context} must be an integer.")
        return value

    @staticmethod
    def _require_optional_str(value: object, context: str) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(f"{context} must be a string if provided.")
        return value


