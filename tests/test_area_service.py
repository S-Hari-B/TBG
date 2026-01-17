import pytest

from tbg.core.rng import RNG
from tbg.data.repositories import AreasRepository
from tbg.domain.state import GameState
from tbg.services.area_service import AreaService, TravelPerformedEvent
from tbg.services.errors import TravelBlockedError


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


def test_story_progress_travel_blocked_when_checkpoint_active() -> None:
    service = AreaService(AreasRepository())
    state = _make_state()
    service.initialize_state(state)
    state.story_checkpoint_node_id = "forest_ambush"
    state.story_checkpoint_thread_id = "main_story"

    with pytest.raises(TravelBlockedError):
        service.travel_to(state, "forest_deeper")

    # Backtracking remains allowed
    service.travel_to(state, "village")
    service.travel_to(state, "village_outskirts")

    state.story_checkpoint_node_id = None
    state.story_checkpoint_thread_id = None
    result = service.travel_to(state, "forest_deeper")
    assert result.location_view.id == "forest_deeper"


def test_entry_story_suppressed_when_checkpoint_active() -> None:
    service = AreaService(AreasRepository())
    state = _make_state()
    service.initialize_state(state)
    state.story_checkpoint_node_id = "forest_ambush"
    state.story_checkpoint_thread_id = "main_story"

    visit = service.travel_to(state, "village")
    assert visit.entry_story_node_id is None
    assert state.location_entry_seen.get("village") is None

    # After clearing checkpoint the entry story should fire on first undisrupted visit
    service.travel_to(state, "village_outskirts")
    state.story_checkpoint_node_id = None
    state.story_checkpoint_thread_id = None
    second_visit = service.travel_to(state, "village")
    assert second_visit.entry_story_node_id == "village_return_entry"


def test_non_story_checkpoint_does_not_block_progress() -> None:
    service = AreaService(AreasRepository())
    state = _make_state()
    service.initialize_state(state)
    state.story_checkpoint_node_id = "quest_node"
    state.story_checkpoint_thread_id = "quest_thread"

    # Should not block forward travel
    result = service.travel_to(state, "forest_deeper")
    assert result.location_view.id == "forest_deeper"
