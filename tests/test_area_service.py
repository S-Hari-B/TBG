from tbg.core.rng import RNG
from tbg.data.repositories import AreasRepository
from tbg.domain.state import GameState
from tbg.services.area_service import AreaService, TravelPerformedEvent


def _make_state() -> GameState:
    return GameState(seed=1, rng=RNG(1), mode="camp_menu", current_node_id="class_select")


def test_travel_updates_location_and_emits_events() -> None:
    service = AreaService(AreasRepository())
    state = _make_state()
    service.initialize_state(state)

    result = service.travel_to(state, "forest_deeper")

    assert state.current_location_id == "forest_deeper"
    assert any(isinstance(evt, TravelPerformedEvent) for evt in result.events)
    assert result.entry_story_node_id == "forest_deeper_entry"


def test_entry_story_triggers_once_per_location() -> None:
    service = AreaService(AreasRepository())
    state = _make_state()
    service.initialize_state(state)

    first_visit = service.travel_to(state, "village")
    assert first_visit.entry_story_node_id == "village_return_entry"
    assert state.location_entry_seen["village"] is True

    # Travel away and back; entry story should not trigger again.
    service.travel_to(state, "village_outskirts")
    second_visit = service.travel_to(state, "village")
    assert second_visit.entry_story_node_id is None
