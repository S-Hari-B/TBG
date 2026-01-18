"""Quest progress state data structures."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(slots=True)
class QuestObjectiveProgress:
    """Tracks progress for a single quest objective."""

    current: int = 0
    completed: bool = False


@dataclass(slots=True)
class QuestProgress:
    """Tracks progress for an active quest."""

    quest_id: str
    objectives: List[QuestObjectiveProgress] = field(default_factory=list)
