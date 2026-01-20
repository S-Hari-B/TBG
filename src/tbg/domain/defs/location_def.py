"""Location definition data structures for Area v2."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(slots=True)
class LocationConnectionDef:
    """Represents a directional travel connection to another location."""

    to_id: str
    label: str
    progresses_story: bool = False
    requires_quest_active: str | None = None
    hide_if_quest_completed: str | None = None
    hide_if_quest_turned_in: str | None = None
    show_if_flag_true: str | None = None
    hide_if_flag_true: str | None = None


@dataclass(slots=True)
class LocationNpcPresenceDef:
    """NPC metadata available for hub interactions."""

    npc_id: str
    talk_node_id: str | None
    quest_hub_node_id: str | None = None


@dataclass(slots=True)
class LocationDef:
    """Describes a traversable location on a floor."""

    id: str
    name: str
    description: str
    floor_id: str
    location_type: str
    area_level: int | None
    tags: Tuple[str, ...]
    connections: Tuple[LocationConnectionDef, ...]
    entry_story_node_id: str | None
    npcs_present: Tuple[LocationNpcPresenceDef, ...] = ()
