from __future__ import annotations

from tbg.core.rng import RNG
from tbg.data.repositories import FloorsRepository, LocationsRepository
from tbg.domain.quest_state import QuestObjectiveProgress, QuestProgress
from tbg.domain.state import GameState
from tbg.services.area_service_v2 import AreaServiceV2


def _make_state() -> GameState:
    return GameState(seed=1, rng=RNG(1), mode="camp_menu", current_node_id="start")



def test_area_service_v2_connection_gating() -> None:
    state = _make_state()
    state.current_location_id = "threshold_inn"

    floors_repo = FloorsRepository()
    locations_repo = LocationsRepository(floors_repo=floors_repo)
    v2 = AreaServiceV2(floors_repo=floors_repo, locations_repo=locations_repo)

    view_v2 = v2.get_current_location_view(state)
    assert "shoreline_ruins" not in {conn.destination_id for conn in view_v2.connections}

    state.quests_active["dana_shoreline_rumor"] = QuestProgress(
        quest_id="dana_shoreline_rumor",
        objectives=[QuestObjectiveProgress(current=0, completed=False)],
    )
    view_v2 = v2.get_current_location_view(state)
    assert "shoreline_ruins" in {conn.destination_id for conn in view_v2.connections}


def test_area_service_v2_entry_seen_for_entry_nodes() -> None:
    state = _make_state()
    state.current_location_id = "shoreline_ruins"

    floors_repo = FloorsRepository()
    locations_repo = LocationsRepository(floors_repo=floors_repo)
    v2 = AreaServiceV2(floors_repo=floors_repo, locations_repo=locations_repo)

    view_v2 = v2.get_current_location_view(state)
    assert view_v2.entry_story_node_id == "protoquest_ruins_entry"
    assert view_v2.entry_seen is False
