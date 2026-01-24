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

    state.flags["flag_protoquest_declined"] = True
    view_v2 = v2.get_current_location_view(state)
    assert "shoreline_ruins" not in {conn.destination_id for conn in view_v2.connections}


def test_area_service_v2_open_plains_includes_northern_ridge() -> None:
    state = _make_state()
    state.current_location_id = "open_plains"

    floors_repo = FloorsRepository()
    locations_repo = LocationsRepository(floors_repo=floors_repo)
    v2 = AreaServiceV2(floors_repo=floors_repo, locations_repo=locations_repo)

    view_v2 = v2.get_current_location_view(state)
    destinations = {conn.destination_id for conn in view_v2.connections}
    assert "northern_ridge" in destinations


def test_area_service_v2_northern_ridge_path_gated_by_cerel_flag() -> None:
    state = _make_state()
    state.current_location_id = "northern_ridge"

    floors_repo = FloorsRepository()
    locations_repo = LocationsRepository(floors_repo=floors_repo)
    v2 = AreaServiceV2(floors_repo=floors_repo, locations_repo=locations_repo)

    view_v2 = v2.get_current_location_view(state)
    assert "northern_ridge_path" not in {conn.destination_id for conn in view_v2.connections}

    state.flags["flag_cerel_returned_to_inn"] = True
    view_v2 = v2.get_current_location_view(state)
    assert "northern_ridge_path" in {conn.destination_id for conn in view_v2.connections}


def test_area_service_v2_repeatable_entry_story_allows_ridge_path_revisit() -> None:
    state = _make_state()
    state.current_location_id = "northern_ridge"
    state.flags["flag_cerel_returned_to_inn"] = True
    state.location_entry_seen["northern_ridge_path"] = True

    floors_repo = FloorsRepository()
    locations_repo = LocationsRepository(floors_repo=floors_repo)
    v2 = AreaServiceV2(floors_repo=floors_repo, locations_repo=locations_repo)

    result = v2.travel_to(state, "northern_ridge_path")
    assert result.entry_story_node_id == "northern_ridge_path_router"


def test_area_service_v2_entry_seen_for_entry_nodes() -> None:
    state = _make_state()
    state.current_location_id = "shoreline_ruins"

    floors_repo = FloorsRepository()
    locations_repo = LocationsRepository(floors_repo=floors_repo)
    v2 = AreaServiceV2(floors_repo=floors_repo, locations_repo=locations_repo)

    view_v2 = v2.get_current_location_view(state)
    assert view_v2.entry_story_node_id == "protoquest_ruins_entry"
    assert view_v2.entry_seen is False
