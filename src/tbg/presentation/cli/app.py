"""Console-driven UI loops for TBG."""
from __future__ import annotations

import secrets
from typing import Literal

from tbg.data.repositories import ArmourRepository, ClassesRepository, StoryRepository, WeaponsRepository
from tbg.domain.state import GameState
from tbg.services import (
    BattleRequestedEvent,
    ChoiceResult,
    ExpGainedEvent,
    GoldGainedEvent,
    PartyMemberJoinedEvent,
    PlayerClassSetEvent,
    StoryNodeView,
    StoryService,
)

MenuAction = Literal["new_game", "quit"]
_MAX_RANDOM_SEED = 2**31 - 1


def main() -> None:
    """Start the interactive CLI session."""
    story_service = _build_story_service()
    print("=== Text Based Game (To be renamed) ===")
    running = True
    while running:
        action = _main_menu_loop()
        if action == "quit":
            running = False
            continue
        game_state = _start_new_game(story_service)
        _run_story_loop(story_service, game_state)
    print("Goodbye!")


def _main_menu_loop() -> MenuAction:
    while True:
        print()
        print("Main Menu")
        print("1. New Game")
        print("2. Quit")
        choice = input("Select an option: ").strip()
        if choice == "1":
            return "new_game"
        if choice == "2":
            return "quit"
        print("Invalid selection. Please enter 1 or 2.")


def _build_story_service() -> StoryService:
    """Construct the StoryService with concrete repositories."""
    story_repo = StoryRepository()
    classes_repo = ClassesRepository()
    weapons_repo = WeaponsRepository()
    armour_repo = ArmourRepository()
    return StoryService(
        story_repo=story_repo,
        classes_repo=classes_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
    )


def _start_new_game(story_service: StoryService) -> GameState:
    seed = _prompt_seed()
    player_name = _prompt_player_name()
    state = story_service.start_new_game(seed=seed, player_name=player_name)
    print(f"Game started with seed: {seed}")
    return state


def _prompt_seed() -> int:
    while True:
        raw_value = input("Enter seed (blank for random): ").strip()
        if not raw_value:
            return secrets.randbelow(_MAX_RANDOM_SEED)
        try:
            return int(raw_value)
        except ValueError:
            print("Invalid seed. Please enter a valid integer.")


def _prompt_player_name() -> str:
    while True:
        name = input("Enter hero name (default Hero): ").strip()
        if not name:
            return "Hero"
        return name


def _run_story_loop(story_service: StoryService, state: GameState) -> None:
    """Run the minimal story loop for the tutorial slice."""
    print("\nBeginning tutorial slice...\n")
    while True:
        node_view = story_service.get_current_node_view(state)
        _render_node_view(node_view)
        if not node_view.choices:
            print("End of demo slice. Returning to main menu.\n")
            return
        choice_index = _prompt_choice(len(node_view.choices))
        result = story_service.choose(state, choice_index)
        _render_events(result)


def _render_node_view(node_view: StoryNodeView) -> None:
    for idx, (node_id, text) in enumerate(node_view.segments):
        if idx > 0:
            print()
        print(f"[{node_id}]")
        print(text)
    if node_view.choices:
        print("Choices:")
        for idx, label in enumerate(node_view.choices, start=1):
            print(f"  {idx}. {label}")


def _prompt_choice(choice_count: int) -> int:
    while True:
        raw = input("Select an option: ").strip()
        try:
            index = int(raw) - 1
        except ValueError:
            print("Please enter a number.")
            continue
        if 0 <= index < choice_count:
            return index
        print(f"Please enter a value between 1 and {choice_count}.")


def _render_events(result: ChoiceResult) -> None:
    if not result.events:
        print()
        return
    print("\nEvents:")
    for event in result.events:
        if isinstance(event, PlayerClassSetEvent):
            print(f"- You assume the role of a {event.class_id}. (Player ID: {event.player_id})")
        elif isinstance(event, BattleRequestedEvent):
            print(f"- Battle initiated against '{event.enemy_id}'.")
        elif isinstance(event, PartyMemberJoinedEvent):
            print(f"- {event.member_id.title()} joins the party.")
        elif isinstance(event, GoldGainedEvent):
            print(f"- Gained {event.amount} gold (Total: {event.total_gold}).")
        elif isinstance(event, ExpGainedEvent):
            print(f"- Gained {event.amount} experience (Total: {event.total_exp}).")
        else:
            print(f"- {event}")
    print()



