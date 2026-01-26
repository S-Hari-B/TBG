"""Domain-level state tracking."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from tbg.core.rng import RNG
from tbg.core.types import GameMode
from tbg.domain.entities import Attributes, Player
from tbg.domain.inventory import MemberEquipment, PartyInventory
from tbg.domain.quest_state import QuestProgress


@dataclass
class GameState:
    """Minimal game state storage."""

    seed: int
    rng: RNG
    mode: GameMode
    current_node_id: str
    player: Player | None = None
    party_members: List[str] = field(default_factory=list)
    party_member_attributes: Dict[str, Attributes] = field(default_factory=dict)
    player_name: str = "Hero"
    player_attribute_points_spent: int = 0
    player_attribute_points_debug_bonus: int = 0
    owned_summons: Dict[str, int] = field(default_factory=dict)
    party_member_summon_loadouts: Dict[str, List[str]] = field(default_factory=dict)
    gold: int = 0
    exp: int = 0
    flags: Dict[str, bool] = field(default_factory=dict)
    knowledge_kill_counts: Dict[str, int] = field(default_factory=dict)
    pending_narration: List[Tuple[str, str]] = field(default_factory=list)
    pending_story_node_id: str | None = None
    inventory: PartyInventory = field(default_factory=PartyInventory)
    equipment: Dict[str, MemberEquipment] = field(default_factory=dict)
    member_levels: Dict[str, int] = field(default_factory=dict)
    member_exp: Dict[str, int] = field(default_factory=dict)
    camp_message: str | None = None
    story_checkpoint_node_id: str | None = None
    story_checkpoint_location_id: str | None = None
    story_checkpoint_thread_id: str | None = None
    current_location_id: str = ""
    visited_locations: List[str] = field(default_factory=list)
    location_entry_seen: Dict[str, bool] = field(default_factory=dict)
    location_visits: Dict[str, int] = field(default_factory=dict)
    shop_stock_remaining: Dict[str, Dict[str, Dict[str, int]]] = field(default_factory=dict)
    shop_stock_visit_index: Dict[str, Dict[str, int]] = field(default_factory=dict)
    quests_active: Dict[str, QuestProgress] = field(default_factory=dict)
    quests_completed: List[str] = field(default_factory=list)
    quests_turned_in: List[str] = field(default_factory=list)


