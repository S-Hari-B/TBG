"""Quest system orchestration and progress tracking."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

from tbg.data.repositories import AreasRepository, ItemsRepository, PartyMembersRepository, QuestsRepository
from tbg.domain.defs import QuestDef, QuestObjectiveDef, QuestRewardItemDef
from tbg.domain.quest_state import QuestObjectiveProgress, QuestProgress
from tbg.domain.state import GameState


@dataclass(slots=True)
class QuestUpdate:
    quest_id: str
    quest_name: str
    accepted: bool = False
    completed: bool = False
    turned_in: bool = False


@dataclass(slots=True)
class QuestObjectiveView:
    label: str
    current: int
    target: int
    completed: bool


@dataclass(slots=True)
class QuestStatusView:
    quest_id: str
    name: str
    objectives: List[QuestObjectiveView]
    is_completed: bool


@dataclass(slots=True)
class QuestTurnInView:
    quest_id: str
    name: str
    npc_id: str | None
    node_id: str


@dataclass(slots=True)
class QuestJournalView:
    active: List[QuestStatusView]
    completed: List[QuestStatusView]
    turned_in: List[str]
    turn_ins: List[QuestTurnInView]


@dataclass(slots=True)
class QuestPrereqView:
    quest_id: str
    quest_name: str
    ready: bool
    missing_required: List[str]
    blocked_by: List[str]


@dataclass(slots=True)
class QuestDebugView:
    total_definitions: int
    active_ids: List[str]
    completed_ids: List[str]
    turned_in_ids: List[str]
    prereqs: List[QuestPrereqView]


class QuestService:
    """Centralized quest logic (accept, progress, turn-in)."""

    def __init__(
        self,
        *,
        quests_repo: QuestsRepository,
        items_repo: ItemsRepository,
        areas_repo: AreasRepository,
        party_members_repo: PartyMembersRepository,
    ) -> None:
        self._quests_repo = quests_repo
        self._items_repo = items_repo
        self._areas_repo = areas_repo
        self._party_members_repo = party_members_repo

    def accept_quest(self, state: GameState, quest_id: str) -> QuestUpdate | None:
        quest = self._quests_repo.get(quest_id)
        if quest_id in state.quests_turned_in or quest_id in state.quests_active:
            return None
        prereq_ready, _, _ = self._evaluate_prereqs(state, quest)
        if not prereq_ready:
            raise ValueError(f"Quest '{quest_id}' prerequisites are not met.")
        progress = QuestProgress(
            quest_id=quest_id,
            objectives=[QuestObjectiveProgress() for _ in quest.objectives],
        )
        state.quests_active[quest_id] = progress
        for flag_id in quest.accept_flags:
            state.flags[flag_id] = True
        self._refresh_collect_objectives(state, quest, progress)
        self._refresh_visit_objectives(state, quest, progress, state.current_location_id)
        completed = self._mark_completed_if_ready(state, quest, progress)
        return QuestUpdate(
            quest_id=quest.quest_id,
            quest_name=quest.name,
            accepted=True,
            completed=completed,
        )

    def record_battle_victory(self, state: GameState, defeated_tags: Sequence[Sequence[str]]) -> None:
        if not state.quests_active:
            return
        for quest_id, progress in list(state.quests_active.items()):
            quest = self._quests_repo.get(quest_id)
            updated = False
            for index, objective in enumerate(quest.objectives):
                if objective.objective_type != "kill_tag":
                    continue
                count = sum(1 for tags in defeated_tags if objective.tag in tags)
                if count <= 0:
                    continue
                updated |= self._increment_progress(progress, index, objective, count)
            if updated:
                self._mark_completed_if_ready(state, quest, progress)

    def record_area_visit(self, state: GameState, area_id: str) -> None:
        if not state.quests_active:
            return
        for quest_id, progress in list(state.quests_active.items()):
            quest = self._quests_repo.get(quest_id)
            if self._refresh_visit_objectives(state, quest, progress, area_id):
                self._mark_completed_if_ready(state, quest, progress)

    def refresh_collect_objectives(self, state: GameState) -> None:
        if not state.quests_active:
            return
        for quest_id, progress in list(state.quests_active.items()):
            quest = self._quests_repo.get(quest_id)
            if self._refresh_collect_objectives(state, quest, progress):
                self._mark_completed_if_ready(state, quest, progress)

    def turn_in_quest(self, state: GameState, quest_id: str) -> QuestUpdate | None:
        if quest_id in state.quests_turned_in:
            return None
        quest = self._quests_repo.get(quest_id)
        if quest_id not in state.quests_active or quest_id not in state.quests_completed:
            raise ValueError(f"Quest '{quest_id}' is not ready to turn in.")
        self._consume_collect_objectives(state, quest)
        self._apply_rewards(state, quest)
        state.quests_turned_in.append(quest_id)
        state.quests_active.pop(quest_id, None)
        return QuestUpdate(
            quest_id=quest.quest_id,
            quest_name=quest.name,
            turned_in=True,
        )

    def build_journal_view(self, state: GameState) -> QuestJournalView:
        active_views = [
            self._build_status_view(state, quest_id) for quest_id in sorted(state.quests_active.keys())
        ]
        completed_views = [
            self._build_status_view(state, quest_id)
            for quest_id in sorted(state.quests_completed)
            if quest_id in state.quests_active
        ]
        turned_in_names = [self._quests_repo.get(qid).name for qid in sorted(state.quests_turned_in)]
        turn_ins = self._build_turn_in_views(state)
        return QuestJournalView(
            active=active_views,
            completed=completed_views,
            turned_in=turned_in_names,
            turn_ins=turn_ins,
        )

    def build_debug_view(self, state: GameState) -> QuestDebugView:
        prereqs: List[QuestPrereqView] = []
        for quest in self._quests_repo.all():
            ready, missing, blocked = self._evaluate_prereqs(state, quest)
            prereqs.append(
                QuestPrereqView(
                    quest_id=quest.quest_id,
                    quest_name=quest.name,
                    ready=ready,
                    missing_required=missing,
                    blocked_by=blocked,
                )
            )
        return QuestDebugView(
            total_definitions=len(self._quests_repo.all()),
            active_ids=sorted(state.quests_active.keys()),
            completed_ids=sorted(state.quests_completed),
            turned_in_ids=sorted(state.quests_turned_in),
            prereqs=prereqs,
        )

    def get_definition_summary(self) -> str:
        return f"Quests loaded: {len(self._quests_repo.all())}"

    def _build_turn_in_views(self, state: GameState) -> List[QuestTurnInView]:
        options: List[QuestTurnInView] = []
        for quest_id in state.quests_active.keys():
            if quest_id not in state.quests_completed or quest_id in state.quests_turned_in:
                continue
            quest = self._quests_repo.get(quest_id)
            if not quest.turn_in:
                continue
            options.append(
                QuestTurnInView(
                    quest_id=quest_id,
                    name=quest.name,
                    npc_id=quest.turn_in.npc_id,
                    node_id=quest.turn_in.node_id,
                )
            )
        return options

    def _build_status_view(self, state: GameState, quest_id: str) -> QuestStatusView:
        quest = self._quests_repo.get(quest_id)
        progress = state.quests_active.get(quest_id)
        objectives: List[QuestObjectiveView] = []
        for index, objective in enumerate(quest.objectives):
            progress_item = progress.objectives[index] if progress and index < len(progress.objectives) else None
            current = progress_item.current if progress_item else 0
            completed = progress_item.completed if progress_item else False
            objectives.append(
                QuestObjectiveView(
                    label=objective.label,
                    current=current,
                    target=objective.quantity,
                    completed=completed,
                )
            )
        is_completed = quest_id in state.quests_completed
        return QuestStatusView(
            quest_id=quest.quest_id,
            name=quest.name,
            objectives=objectives,
            is_completed=is_completed,
        )

    def _increment_progress(
        self,
        progress: QuestProgress,
        index: int,
        objective: QuestObjectiveDef,
        amount: int,
    ) -> bool:
        if index >= len(progress.objectives):
            return False
        entry = progress.objectives[index]
        if entry.completed:
            return False
        entry.current += amount
        if entry.current >= objective.quantity:
            entry.completed = True
        return True

    def _refresh_collect_objectives(self, state: GameState, quest: QuestDef, progress: QuestProgress) -> bool:
        updated = False
        for index, objective in enumerate(quest.objectives):
            if objective.objective_type != "collect_item" or not objective.item_id:
                continue
            current_count = state.inventory.items.get(objective.item_id, 0)
            if index >= len(progress.objectives):
                continue
            entry = progress.objectives[index]
            if current_count > entry.current:
                entry.current = current_count
            if entry.current >= objective.quantity and not entry.completed:
                entry.completed = True
            updated = True
        return updated

    def _refresh_visit_objectives(
        self, state: GameState, quest: QuestDef, progress: QuestProgress, area_id: str
    ) -> bool:
        updated = False
        for index, objective in enumerate(quest.objectives):
            if objective.objective_type != "visit_area" or not objective.area_id:
                continue
            if objective.area_id != area_id:
                continue
            if index >= len(progress.objectives):
                continue
            entry = progress.objectives[index]
            if not entry.completed:
                entry.current = max(entry.current, 1)
                entry.completed = True
                updated = True
        return updated

    def _mark_completed_if_ready(self, state: GameState, quest: QuestDef, progress: QuestProgress) -> bool:
        if quest.quest_id in state.quests_completed:
            return False
        if all(entry.completed for entry in progress.objectives):
            state.quests_completed.append(quest.quest_id)
            for flag_id in quest.complete_flags:
                state.flags[flag_id] = True
            return True
        return False

    def _apply_rewards(self, state: GameState, quest: QuestDef) -> None:
        reward = quest.rewards
        state.gold += reward.gold
        self._grant_party_exp(state, reward.party_exp)
        for item in reward.items:
            self._add_item(state, item)
        for flag_id, value in reward.set_flags:
            state.flags[flag_id] = value

    def _consume_collect_objectives(self, state: GameState, quest: QuestDef) -> None:
        for objective in quest.objectives:
            if objective.objective_type != "collect_item" or not objective.item_id:
                continue
            current = state.inventory.items.get(objective.item_id, 0)
            if current < objective.quantity:
                raise ValueError(f"Quest '{quest.quest_id}' is missing required items.")
            remaining = current - objective.quantity
            if remaining > 0:
                state.inventory.items[objective.item_id] = remaining
            else:
                state.inventory.items.pop(objective.item_id, None)

    def _grant_party_exp(self, state: GameState, amount: int) -> None:
        if amount <= 0:
            return
        member_ids = self._active_party_ids(state)
        if not member_ids:
            return
        base = amount // len(member_ids)
        remainder = amount % len(member_ids)
        for member_id in member_ids:
            share = base + (remainder if state.player and member_id == state.player.id else 0)
            if share <= 0:
                continue
            self._apply_member_exp(state, member_id, share)

    def _apply_member_exp(self, state: GameState, member_id: str, amount: int) -> None:
        level = state.member_levels.get(member_id, 1)
        exp = state.member_exp.get(member_id, 0) + amount
        threshold = self._xp_to_next_level(level)
        while exp >= threshold:
            exp -= threshold
            level += 1
            threshold = self._xp_to_next_level(level)
            self._restore_member_resources(state, member_id)
        state.member_levels[member_id] = level
        state.member_exp[member_id] = exp

    def _restore_member_resources(self, state: GameState, member_id: str) -> None:
        if state.player and member_id == state.player.id:
            state.player.stats.hp = state.player.stats.max_hp
            state.player.stats.mp = state.player.stats.max_mp

    def _add_item(self, state: GameState, reward_item: QuestRewardItemDef) -> None:
        if reward_item.quantity <= 0:
            return
        self._items_repo.get(reward_item.item_id)
        state.inventory.items[reward_item.item_id] = (
            state.inventory.items.get(reward_item.item_id, 0) + reward_item.quantity
        )

    def _evaluate_prereqs(self, state: GameState, quest: QuestDef) -> tuple[bool, List[str], List[str]]:
        missing: List[str] = []
        blocked: List[str] = []
        for flag_id in quest.prereqs.required_flags:
            if not state.flags.get(flag_id, False):
                missing.append(flag_id)
        for flag_id in quest.prereqs.forbidden_flags:
            if state.flags.get(flag_id, False):
                blocked.append(flag_id)
        return not missing and not blocked, missing, blocked

    def _active_party_ids(self, state: GameState) -> List[str]:
        ids: List[str] = []
        if state.player:
            ids.append(state.player.id)
        ids.extend(state.party_members)
        return ids

    @staticmethod
    def _xp_to_next_level(level: int) -> int:
        return 10 + (level - 1) * 5
