"""Console-driven UI loops for TBG."""
from __future__ import annotations

import secrets
from typing import Literal

from tbg.core.rng import RNG
from tbg.domain.state import GameState

MenuAction = Literal["new_game", "quit"]
GameMenuAction = Literal["main_menu", "quit"]
_MAX_RANDOM_SEED = 2**31 - 1


def main() -> None:
    """Start the interactive CLI session."""
    print("=== Text Based Game (To be renamed) ===")
    running = True
    while running:
        action = _main_menu_loop()
        if action == "quit":
            running = False
            continue
        game_state = _start_new_game()
        post_game_action = _game_menu_loop(game_state)
        if post_game_action == "quit":
            running = False
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


def _start_new_game() -> GameState:
    seed = _prompt_seed()
    state = GameState(seed=seed, rng=RNG(seed), mode="game_menu")
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


def _game_menu_loop(game_state: GameState) -> GameMenuAction:
    """Game menu loop placeholder until deeper features exist."""
    _ = game_state  # prevent unused argument warnings until used
    while True:
        print()
        print("Game Menu")
        print("1. Return to Main Menu")
        print("2. Quit")
        choice = input("Select an option: ").strip()
        if choice == "1":
            return "main_menu"
        if choice == "2":
            return "quit"
        print("Invalid selection. Please enter 1 or 2.")


