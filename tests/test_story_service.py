import pytest

from tbg.data.repositories import ArmourRepository, ClassesRepository, StoryRepository, WeaponsRepository
from tbg.services.story_service import (
    BattleRequestedEvent,
    ExpGainedEvent,
    GoldGainedEvent,
    PartyMemberJoinedEvent,
    PlayerClassSetEvent,
    StoryService,
)


def _make_story_service() -> StoryService:
    return StoryService(
        story_repo=StoryRepository(),
        classes_repo=ClassesRepository(),
        weapons_repo=WeaponsRepository(),
        armour_repo=ArmourRepository(),
    )


def test_story_repository_loads_nodes() -> None:
    repo = StoryRepository()
    node = repo.get("class_select")

    assert node.text
    assert len(node.choices) == 4


def test_story_flow_advances_and_applies_effects() -> None:
    service = _make_story_service()
    state = service.start_new_game(seed=12345, player_name="Tester")
    view = service.get_current_node_view(state)

    assert view.node_id == "class_select"

    first_result = service.choose(state, 0)
    assert state.player is not None
    assert any(isinstance(evt, PlayerClassSetEvent) for evt in first_result.events)
    assert first_result.node_view.node_id == "forest_scream"
    assert [segment[0] for segment in first_result.node_view.segments] == [
        "forest_intro",
        "forest_scream",
    ]

    second_result = service.choose(state, 0)
    event_types = {type(evt) for evt in second_result.events}

    assert BattleRequestedEvent in event_types
    assert PartyMemberJoinedEvent in event_types
    assert GoldGainedEvent in event_types
    assert ExpGainedEvent in event_types
    assert "emma" in state.party_members
    assert state.gold == 5
    assert state.exp == 10
    assert second_result.node_view.node_id == "forest_aftermath"
    assert not second_result.node_view.choices


def test_story_determinism_with_same_seed() -> None:
    service = _make_story_service()
    state_a = service.start_new_game(seed=999, player_name="Hero")
    state_b = service.start_new_game(seed=999, player_name="Hero")

    sequence_a = _play_choices_capture(service, state_a, [0, 0])
    sequence_b = _play_choices_capture(service, state_b, [0, 0])

    assert sequence_a == sequence_b


def _play_choices_capture(service: StoryService, state, choices):
    node_history = [service.get_current_node_view(state).node_id]
    event_history = []
    for choice in choices:
        result = service.choose(state, choice)
        node_history.append(result.node_view.node_id)
        event_history.append(tuple(result.events))
    return node_history, tuple(event_history)


