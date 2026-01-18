"""Area definition data structures."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(slots=True)
class AreaConnectionDef:
    """Represents a directional travel connection to another area."""

    to_id: str
    label: str
    progresses_story: bool = False
    requires_quest_active: str | None = None
    hide_if_quest_completed: str | None = None
    hide_if_quest_turned_in: str | None = None
    show_if_flag_true: str | None = None
    hide_if_flag_true: str | None = None


@dataclass(slots=True)
class AreaDef:
    """Describes a traversable area on the overworld map."""

    id: str
    name: str
    description: str
    tags: Tuple[str, ...]
    connections: Tuple[AreaConnectionDef, ...]
    entry_story_node_id: str | None
    npcs_present: Tuple["NpcPresenceDef", ...] = ()


@dataclass(slots=True)
class NpcPresenceDef:
    """NPC metadata available for hub interactions."""

    npc_id: str
    talk_node_id: str
    quest_hub_node_id: str | None = None

