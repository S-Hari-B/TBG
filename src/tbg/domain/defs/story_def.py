"""Story definition structures used by the runtime."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class StoryEffectDef:
    """Single effect entry attached to a node or choice."""

    type: str
    data: Dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class StoryChoiceDef:
    """Represents a selectable choice on a story node."""

    label: str
    next_node_id: str
    effects: List[StoryEffectDef] = field(default_factory=list)


@dataclass(slots=True)
class StoryNodeDef:
    """Fully parsed story node."""

    id: str
    text: str
    effects: List[StoryEffectDef] = field(default_factory=list)
    choices: List[StoryChoiceDef] = field(default_factory=list)
    next_node_id: str | None = None


