"""Domain-level state tracking."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from tbg.core.rng import RNG
from tbg.core.types import GameMode
from tbg.domain.entities import Player
from tbg.domain.inventory import MemberEquipment, PartyInventory


@dataclass
class GameState:
    """Minimal game state storage."""

    seed: int
    rng: RNG
    mode: GameMode
    current_node_id: str
    player: Player | None = None
    party_members: List[str] = field(default_factory=list)
    player_name: str = "Hero"
    gold: int = 0
    exp: int = 0
    flags: Dict[str, bool] = field(default_factory=dict)
    pending_narration: List[Tuple[str, str]] = field(default_factory=list)
    pending_story_node_id: str | None = None
    inventory: PartyInventory = field(default_factory=PartyInventory)
    equipment: Dict[str, MemberEquipment] = field(default_factory=dict)
    member_levels: Dict[str, int] = field(default_factory=dict)
    member_exp: Dict[str, int] = field(default_factory=dict)
    camp_message: str | None = None


