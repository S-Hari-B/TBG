from __future__ import annotations

from tbg.core.rng import RNG
from tbg.data.repositories import FloorsRepository, LocationsRepository
from tbg.domain.quest_state import QuestObjectiveProgress, QuestProgress
from tbg.domain.state import GameState
from tbg.services.area_service import TRAVEL_BLOCKED_MESSAGE
from tbg.services.area_service_v2 import AreaServiceV2


def test_area_service_v2_blocks_progress_when_checkpoint_active() -> None:
    floors_repo = FloorsRepository()
    locations_repo = LocationsRepository(floors_repo=floors_repo)
    service = AreaServiceV2(floors_repo=floors_repo, locations_repo=locations_repo)
    state = GameState(seed=1, rng=RNG(1), mode="camp_menu", current_node_id="start")
    state.current_location_id = "threshold_inn"
    state.story_checkpoint_node_id = "battle_trial_1v1"
    state.story_checkpoint_thread_id = "main_story"
    state.quests_active["dana_shoreline_rumor"] = QuestProgress(
        quest_id="dana_shoreline_rumor",
        objectives=[QuestObjectiveProgress(current=0, completed=False)],
    )

    blocked = service.can_travel_to(state, "floor_one_gate")
    assert blocked.allowed is False
    assert blocked.reason == TRAVEL_BLOCKED_MESSAGE

    allowed = service.can_travel_to(state, "shoreline_ruins")
    assert allowed.allowed is True
