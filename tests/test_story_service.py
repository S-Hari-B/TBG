import pytest

from tbg.data.repositories import (
    ArmourRepository,
    ClassesRepository,
    EnemiesRepository,
    ItemsRepository,
    KnowledgeRepository,
    LootTablesRepository,
    PartyMembersRepository,
    SkillsRepository,
    StoryRepository,
    WeaponsRepository,
)
from tbg.services.story_service import (
    BattleRequestedEvent,
    ExpGainedEvent,
    GameMenuEnteredEvent,
    GoldGainedEvent,
    PartyMemberJoinedEvent,
    PlayerClassSetEvent,
    StoryService,
)
from tbg.services.battle_service import BattleService
from tbg.services.inventory_service import InventoryService


def _make_story_service() -> StoryService:
    weapons_repo = WeaponsRepository()
    armour_repo = ArmourRepository()
    party_repo = PartyMembersRepository()
    inventory_service = InventoryService(
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        party_members_repo=party_repo,
    )
    return StoryService(
        story_repo=StoryRepository(),
        classes_repo=ClassesRepository(weapons_repo=weapons_repo, armour_repo=armour_repo),
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        party_members_repo=party_repo,
        inventory_service=inventory_service,
    )


def _make_battle_service() -> BattleService:
    return BattleService(
        enemies_repo=EnemiesRepository(),
        party_members_repo=PartyMembersRepository(),
        knowledge_repo=KnowledgeRepository(),
        weapons_repo=WeaponsRepository(),
        armour_repo=ArmourRepository(),
        skills_repo=SkillsRepository(),
        items_repo=ItemsRepository(),
        loot_tables_repo=LootTablesRepository(),
    )


def test_story_repository_loads_nodes() -> None:
    repo = StoryRepository()
    class_node = repo.get("class_select")
    intro_node = repo.get("intro_decree")

    assert class_node.text
    assert len(class_node.choices) == 4
    assert intro_node.next_node_id == "intro_departure"


def test_story_flow_advances_and_applies_effects() -> None:
    service = _make_story_service()
    state = service.start_new_game(seed=12345, player_name="Tester")
    view = service.get_current_node_view(state)

    assert view.node_id == "class_select"
    assert [segment[0] for segment in view.segments] == [
        "intro_decree",
        "intro_departure",
        "class_select",
    ]

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
    assert PartyMemberJoinedEvent not in event_types
    post_battle_events = service.resume_pending_flow(state)
    assert any(isinstance(evt, PartyMemberJoinedEvent) for evt in post_battle_events)
    assert "emma" in state.party_members


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


def test_first_and_second_battles_have_expected_party() -> None:
    story_service = _make_story_service()
    battle_service = _make_battle_service()
    state = story_service.start_new_game(seed=1234, player_name="Hero")

    story_service.choose(state, 0)  # select class
    result = story_service.choose(state, 0)  # investigate scream
    first_battle_event = next(event for event in result.events if isinstance(event, BattleRequestedEvent))

    first_battle_state, _ = battle_service.start_battle(first_battle_event.enemy_id, state)
    assert len(first_battle_state.allies) == 1  # player only
    assert state.party_members == []

    # Simulate battle victory and resume story (Emma joins after battle).
    post_battle_events = story_service.resume_pending_flow(state)
    assert any(isinstance(event, PartyMemberJoinedEvent) for event in post_battle_events)
    assert "emma" in state.party_members

    second_battle_event = next(event for event in post_battle_events if isinstance(event, BattleRequestedEvent))
    second_battle_state, _ = battle_service.start_battle(second_battle_event.enemy_id, state)
    assert len(second_battle_state.allies) == 2  # player + Emma


def test_post_ambush_interlude_triggers_game_menu() -> None:
    story_service = _make_story_service()
    state = story_service.start_new_game(seed=2024, player_name="Hero")

    story_service.choose(state, 0)  # class selection
    story_service.choose(state, 0)  # investigate scream, triggers first battle
    story_service.resume_pending_flow(state)  # simulate victory

    # Second battle completes
    interlude_events = story_service.resume_pending_flow(state)
    assert any(isinstance(evt, GameMenuEnteredEvent) for evt in interlude_events)
    assert state.current_node_id == "post_ambush_menu"
    assert state.pending_story_node_id == "forest_aftermath"

    # Continue story after menu interlude
    post_menu_events = story_service.resume_pending_flow(state)
    assert any(isinstance(evt, GoldGainedEvent) for evt in post_menu_events)
    assert state.current_node_id == "forest_aftermath"


def test_intro_flags_are_set() -> None:
    service = _make_story_service()
    state = service.start_new_game(seed=77, player_name="Hero")
    assert state.flags.get("flag_decree_received") is True
    assert state.flags.get("flag_left_village") is True
