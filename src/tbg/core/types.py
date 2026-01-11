"""Shared type aliases for the core and domain layers."""
from typing import Literal

GameMode = Literal["main_menu", "story", "camp_menu", "battle"]

__all__ = ["GameMode"]

