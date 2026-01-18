"""Quest definition data structures."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Tuple

QuestObjectiveType = Literal["kill_tag", "collect_item", "visit_area"]


@dataclass(slots=True)
class QuestPrereqDef:
    required_flags: Tuple[str, ...]
    forbidden_flags: Tuple[str, ...]


@dataclass(slots=True)
class QuestObjectiveDef:
    objective_type: QuestObjectiveType
    label: str
    tag: str | None = None
    item_id: str | None = None
    area_id: str | None = None
    quantity: int = 1


@dataclass(slots=True)
class QuestTurnInDef:
    node_id: str
    npc_id: str | None = None


@dataclass(slots=True)
class QuestRewardItemDef:
    item_id: str
    quantity: int


@dataclass(slots=True)
class QuestRewardDef:
    gold: int
    party_exp: int
    items: Tuple[QuestRewardItemDef, ...]
    set_flags: Tuple[Tuple[str, bool], ...]


@dataclass(slots=True)
class QuestDef:
    quest_id: str
    name: str
    prereqs: QuestPrereqDef
    objectives: Tuple[QuestObjectiveDef, ...]
    turn_in: QuestTurnInDef | None
    rewards: QuestRewardDef
    accept_flags: Tuple[str, ...]
    complete_flags: Tuple[str, ...]
