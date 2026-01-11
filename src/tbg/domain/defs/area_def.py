"""Area definition data structures."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(slots=True)
class AreaConnectionDef:
    """Represents a directional travel connection to another area."""

    to_id: str
    label: str


@dataclass(slots=True)
class AreaDef:
    """Describes a traversable area on the overworld map."""

    id: str
    name: str
    description: str
    tags: Tuple[str, ...]
    connections: Tuple[AreaConnectionDef, ...]
    entry_story_node_id: str | None

