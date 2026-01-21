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
from tbg.services.quest_service import QuestService, QuestUpdate


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
class PartyExpGrantedEvent(StoryEvent):
    member_id: str
    member_name: str
    amount: int
    new_level: int


@dataclass(slots=True)
class PartyLevelUpEvent(StoryEvent):
    member_id: str
    member_name: str
    new_level: int


@dataclass(slots=True)
class QuestAcceptedEvent(StoryEvent):
    quest_id: str
    quest_name: str


@dataclass(slots=True)
class QuestCompletedEvent(StoryEvent):
    quest_id: str
    quest_name: str


@dataclass(slots=True)
class QuestTurnedInEvent(StoryEvent):
    quest_id: str
    quest_name: str


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
        quest_service: QuestService | None = None,
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
        self._quest_service = quest_service
        self._default_player_name = default_player_name

    def start_new_game(self, seed: int, player_name: str | None = None) -> GameState:
        """Create a fresh game state and position the story at the intro node."""
        rng = RNG(seed)
        state = GameState(
            seed=seed,
            rng=rng,
            mode="story",
            current_node_id="arrival_beach_wake",
        )
        state.player_name = player_name or self._default_player_name
        self._enter_node(state, "arrival_beach_wake", [])
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
                if state.pending_story_node_id is None:
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

    def has_node(self, node_id: str) -> bool:
        """Return True if the node exists in the story repository."""
        try:
            self._story_repo.get(node_id)
        except KeyError:
            return False
        return True

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
                        state.party_member_attributes[member_id] = member_def.starting_attributes
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
            elif effect_type == "give_party_exp":
                amount = self._require_int(effect.data.get("amount"), "give_party_exp.amount")
                emitted.extend(self._grant_party_exp(state, amount))
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
            elif effect_type == "remove_item":
                item_id = self._require_str(effect.data.get("item_id"), "remove_item.item_id")
                quantity = self._require_int(effect.data.get("quantity", 1), "remove_item.quantity")
                if quantity <= 0:
                    continue
                if not state.inventory.remove_item(item_id, quantity):
                    raise ValueError(f"remove_item could not remove {quantity} of '{item_id}'.")
                if self._quest_service:
                    self._quest_service.refresh_collect_objectives(state)
            elif effect_type == "branch_on_flag":
                flag_id = self._require_str(effect.data.get("flag_id"), "branch_on_flag.flag_id")
                expected = effect.data.get("expected", True)
                if not isinstance(expected, bool):
                    raise ValueError("branch_on_flag.expected must be a boolean.")
                next_on_true = self._require_str(effect.data.get("next_on_true"), "branch_on_flag.next_on_true")
                next_on_false = self._require_str(effect.data.get("next_on_false"), "branch_on_flag.next_on_false")
                flag_value = state.flags.get(flag_id, False)
                state.pending_story_node_id = next_on_true if flag_value == expected else next_on_false
                halt_flow = True
            elif effect_type == "quest":
                if not self._quest_service:
                    raise ValueError("quest effect requires QuestService.")
                action = self._require_str(effect.data.get("action"), "quest.action")
                quest_id = self._require_str(effect.data.get("quest_id"), "quest.quest_id")
                updates = self._apply_quest_action(action, quest_id, state)
                emitted.extend(self._quest_updates_to_events(updates))
            else:
                # Unknown effects are ignored for now to keep the interpreter forward compatible.
                continue
        return emitted, halt_flow

    def _apply_quest_action(self, action: str, quest_id: str, state: GameState) -> List[QuestUpdate]:
        updates: List[QuestUpdate] = []
        if action == "accept":
            result = self._quest_service.accept_quest(state, quest_id)
            if result:
                updates.append(result)
        elif action == "turn_in":
            result = self._quest_service.turn_in_quest(state, quest_id)
            if result:
                updates.append(result)
        else:
            raise ValueError("quest.action must be 'accept' or 'turn_in'.")
        return updates

    @staticmethod
    def _quest_updates_to_events(updates: Sequence[QuestUpdate]) -> List[StoryEvent]:
        events: List[StoryEvent] = []
        for update in updates:
            if update.accepted:
                events.append(
                    QuestAcceptedEvent(quest_id=update.quest_id, quest_name=update.quest_name)
                )
            if update.completed:
                events.append(
                    QuestCompletedEvent(quest_id=update.quest_id, quest_name=update.quest_name)
                )
            if update.turned_in:
                events.append(
                    QuestTurnedInEvent(quest_id=update.quest_id, quest_name=update.quest_name)
                )
        return events

    def _grant_party_exp(self, state: GameState, amount: int) -> List[StoryEvent]:
        if amount <= 0:
            return []
        participants = self._active_party_ids(state)
        if not participants:
            return []
        base = amount // len(participants)
        remainder = amount % len(participants)
        events: List[StoryEvent] = []
        for member_id in participants:
            share = base
            if state.player and member_id == state.player.id:
                share += remainder
            if share > 0:
                events.extend(self._award_party_exp(state, member_id, share))
        return events

    def _award_party_exp(self, state: GameState, member_id: str, amount: int) -> List[StoryEvent]:
        if amount <= 0:
            return []
        events: List[StoryEvent] = []
        current_level = state.member_levels.get(member_id, 1)
        current_exp = state.member_exp.get(member_id, 0)
        current_exp += amount
        leveled: List[int] = []
        threshold = self._xp_to_next_level(current_level)
        while current_exp >= threshold:
            current_exp -= threshold
            current_level += 1
            leveled.append(current_level)
            threshold = self._xp_to_next_level(current_level)
        state.member_levels[member_id] = current_level
        state.member_exp[member_id] = current_exp
        member_name = self._resolve_member_name(state, member_id)
        events.append(
            PartyExpGrantedEvent(
                member_id=member_id,
                member_name=member_name,
                amount=amount,
                new_level=current_level,
            )
        )
        for level in leveled:
            events.append(
                PartyLevelUpEvent(
                    member_id=member_id,
                    member_name=member_name,
                    new_level=level,
                )
            )
            self._restore_member_resources(state, member_id, restore_hp=True, restore_mp=True)
        return events

    def _resolve_member_name(self, state: GameState, member_id: str) -> str:
        if state.player and member_id == state.player.id:
            return state.player.name
        try:
            member = self._party_members_repo.get(member_id)
            return member.name
        except KeyError:
            return member_id

    @staticmethod
    def _xp_to_next_level(level: int) -> int:
        return 10 + (level - 1) * 5

    def _active_party_ids(self, state: GameState) -> List[str]:
        ids: List[str] = []
        if state.player:
            ids.append(state.player.id)
        ids.extend(state.party_members)
        return ids

    def _restore_member_resources(
        self,
        state: GameState,
        member_id: str,
        *,
        restore_hp: bool,
        restore_mp: bool,
    ) -> None:
        if state.player and member_id == state.player.id:
            if restore_hp:
                state.player.stats.hp = state.player.stats.max_hp
            if restore_mp:
                state.player.stats.mp = state.player.stats.max_mp

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


