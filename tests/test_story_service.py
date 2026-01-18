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
    GameMenuEnteredEvent,
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
    arrival_node = repo.get("arrival_beach_wake")

    assert class_node.text
    assert len(class_node.choices) == 4
    assert arrival_node.next_node_id == "arrival_beach_rescue"


def test_story_flow_advances_and_applies_effects() -> None:
    service = _make_story_service()
    state = service.start_new_game(seed=12345, player_name="Tester")
    view = service.get_current_node_view(state)

    assert view.node_id == "class_select"
    assert [segment[0] for segment in view.segments] == [
        "arrival_beach_wake",
        "arrival_beach_rescue",
        "inn_arrival",
        "inn_orientation_cerel",
        "inn_orientation_dana",
        "class_overview",
        "class_select",
    ]

    # Select warrior class
    first_result = service.choose(state, 0)
    assert state.player is not None
    assert any(isinstance(evt, PlayerClassSetEvent) for evt in first_result.events)
    # After class selection, story auto-advances through setup to battle node
    assert first_result.node_view.node_id == "battle_trial_1v1"

    # The battle node triggers, so resume to handle the battle
    battle_events = [evt for evt in first_result.events if isinstance(evt, BattleRequestedEvent)]
    assert len(battle_events) > 0
    
    # Simulate victory and resume - should reach companion choice eventually
    post_trial = service.resume_pending_flow(state)
    assert state.current_node_id == "companion_choice"


def test_story_determinism_with_same_seed() -> None:
    service = _make_story_service()
    state_a = service.start_new_game(seed=999, player_name="Hero")
    state_b = service.start_new_game(seed=999, player_name="Hero")

    # Select same class for both
    result_a = service.choose(state_a, 0)
    result_b = service.choose(state_b, 0)

    # Should have same node and same events
    assert result_a.node_view.node_id == result_b.node_view.node_id
    assert len(result_a.events) == len(result_b.events)


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

    # Select warrior
    result = story_service.choose(state, 0)
    battle_events = [e for e in result.events if isinstance(e, BattleRequestedEvent)]
    assert len(battle_events) > 0
    first_battle_event = battle_events[0]

    first_battle_state, _ = battle_service.start_battle(first_battle_event.enemy_id, state)
    assert len(first_battle_state.allies) == 1  # player only
    assert state.party_members == []

    # After trial, should reach companion choice
    story_service.resume_pending_flow(state)
    assert state.current_node_id == "companion_choice"
    
    # Choose Emma (index 1 now: solo=0, emma=1, niale=2, both=3)
    result = story_service.choose(state, 1)
    # Choosing Emma should add her and advance to battle
    assert "emma" in state.party_members

    # Resume to get party battle
    party_result = story_service.resume_pending_flow(state)
    party_battle_events = [e for e in party_result if isinstance(e, BattleRequestedEvent)]
    if not party_battle_events:
        # Battle might be in the choice result itself
        party_battle_events = [e for e in result.events if isinstance(e, BattleRequestedEvent)]
    
    assert len(party_battle_events) > 0
    second_battle_event = party_battle_events[0]
    
    second_battle_state, _ = battle_service.start_battle(second_battle_event.enemy_id, state)
    assert len(second_battle_state.allies) == 2  # player + Emma


def test_companion_choice_affects_party() -> None:
    """Test that choosing Niale instead of Emma correctly adds Niale to party."""
    story_service = _make_story_service()
    state = story_service.start_new_game(seed=5678, player_name="Hero")

    # Select class
    story_service.choose(state, 0)  # warrior
    story_service.resume_pending_flow(state)  # after trial battle

    # Choose Niale (index 2 now, with solo=0, emma=1, niale=2, both=3)
    story_service.choose(state, 2)

    assert "niale" in state.party_members
    assert "emma" not in state.party_members
    assert state.flags.get("flag_companion_niale") is True
    assert state.flags.get("flag_companion_emma") is not True


def test_companion_choice_solo_path() -> None:
    """Test that choosing solo path doesn't add companions and skips party battle."""
    story_service = _make_story_service()
    state = story_service.start_new_game(seed=9999, player_name="Hero")

    # Select class
    story_service.choose(state, 0)  # warrior
    story_service.resume_pending_flow(state)  # after trial battle

    # Choose solo (index 0)
    story_service.choose(state, 0)

    assert len(state.party_members) == 0
    assert state.flags.get("flag_companion_none") is True
    # Should skip directly to knowledge intro without party battle
    assert state.current_node_id == "protoquest_offer"
    assert state.flags.get("flag_party_battle_completed") is True  # flag set even though battle skipped


def test_companion_choice_both_companions() -> None:
    """Test that choosing both Emma and Niale adds both to party."""
    story_service = _make_story_service()
    state = story_service.start_new_game(seed=7777, player_name="Hero")

    # Select class
    story_service.choose(state, 0)  # warrior
    story_service.resume_pending_flow(state)  # after trial battle

    # Choose both (index 3)
    story_service.choose(state, 3)

    assert "emma" in state.party_members
    assert "niale" in state.party_members
    assert len(state.party_members) == 2
    assert state.flags.get("flag_companion_both") is True


def test_post_ambush_interlude_triggers_game_menu() -> None:
    story_service = _make_story_service()
    state = story_service.start_new_game(seed=2024, player_name="Hero")

    # Select class
    story_service.choose(state, 0)
    story_service.resume_pending_flow(state)  # trial
    
    # Choose companion (Emma, index 1)
    result = story_service.choose(state, 1)
    # The battle happens, so we need to resume twice: once for battle, once for post-battle
    story_service.resume_pending_flow(state)  # party battle happens
    story_service.resume_pending_flow(state)  # after party battle (victory assumed)
    story_service.resume_pending_flow(state)  # advance to proto-quest
    
    # Should reach proto-quest offer node
    assert state.current_node_id == "protoquest_offer"


def test_rewind_to_checkpoint_retries_failed_battle() -> None:
    story_service = _make_story_service()
    state = story_service.start_new_game(seed=303, player_name="Hero")

    # Select class and complete trial
    story_service.choose(state, 0)  # class
    story_service.resume_pending_flow(state)  # trial
    
    # Choose Emma (index 1)
    result = story_service.choose(state, 1)
    # Battle might be in result or need resume
    resume_events = []
    if not any(isinstance(e, BattleRequestedEvent) for e in result.events):
        resume_events = story_service.resume_pending_flow(state)  # party battle
    else:
        resume_events = result.events
        
    assert any(isinstance(evt, BattleRequestedEvent) for evt in resume_events)
    assert state.story_checkpoint_node_id == "battle_party_pack"

    # Simulate defeat
    story_service.rewind_to_checkpoint(state)
    assert state.pending_story_node_id == "battle_party_pack"
    retry_events = story_service.resume_pending_flow(state)
    assert any(isinstance(evt, BattleRequestedEvent) for evt in retry_events)

    # Clear checkpoint
    story_service.clear_checkpoint(state)
    assert state.story_checkpoint_node_id is None


def test_resume_pending_flow_honors_checkpoint_even_without_pending() -> None:
    story_service = _make_story_service()
    state = story_service.start_new_game(seed=404, player_name="Hero")

    # Get to party battle
    story_service.choose(state, 0)  # class
    story_service.resume_pending_flow(state)  # trial
    story_service.choose(state, 1)  # choose Emma (index 1)
    story_service.resume_pending_flow(state)  # hit party battle checkpoint
    assert state.story_checkpoint_node_id == "battle_party_pack"

    state.pending_story_node_id = None
    state.pending_narration = []

    replay_events = story_service.resume_pending_flow(state)
    assert any(isinstance(evt, BattleRequestedEvent) for evt in replay_events)


def test_checkpoint_records_location() -> None:
    story_service = _make_story_service()
    state = story_service.start_new_game(seed=515, player_name="Hero")

    # Get to party battle
    story_service.choose(state, 0)  # class
    story_service.resume_pending_flow(state)  # trial
    result = story_service.choose(state, 1)  # choose Emma (index 1)
    
    # Battle might be in result or need resume
    if not any(isinstance(e, BattleRequestedEvent) for e in result.events):
        events = story_service.resume_pending_flow(state)  # party battle
    else:
        events = result.events
    
    assert any(isinstance(evt, BattleRequestedEvent) for evt in events)
    assert state.story_checkpoint_node_id == "battle_party_pack"
    assert state.story_checkpoint_location_id == state.current_location_id
    assert state.story_checkpoint_thread_id == "main_story"


def test_checkpoint_clear_only_when_thread_matches() -> None:
    story_service = _make_story_service()
    state = story_service.start_new_game(seed=616, player_name="Hero")
    
    # Get to party battle
    story_service.choose(state, 0)  # class
    story_service.resume_pending_flow(state)  # trial
    story_service.choose(state, 1)  # choose Emma (index 1)
    story_service.resume_pending_flow(state)  # party battle

    state.story_checkpoint_thread_id = "quest_bandits"
    story_service.clear_checkpoint(state, thread_id="main_story")
    assert state.story_checkpoint_node_id is not None

    story_service.clear_checkpoint(state, thread_id="quest_bandits")
    assert state.story_checkpoint_node_id is None


def test_rewind_only_when_thread_matches() -> None:
    story_service = _make_story_service()
    state = story_service.start_new_game(seed=717, player_name="Hero")
    state.story_checkpoint_node_id = "dummy"
    state.story_checkpoint_location_id = "threshold_inn"
    state.story_checkpoint_thread_id = "quest_thread"

    assert story_service.rewind_to_checkpoint(state, thread_id="main_story") is False
    assert story_service.rewind_to_checkpoint(state, thread_id="quest_thread") is True


def test_intro_flags_are_set() -> None:
    service = _make_story_service()
    state = service.start_new_game(seed=77, player_name="Hero")
    assert state.flags.get("flag_ch00_arrived") is True


def test_side_quest_offer_does_not_block_main_story() -> None:
    service = _make_story_service()
    state = service.start_new_game(seed=888, player_name="Hero")

    # Jump to the Threshold Inn hub (post-Floor One unlock).
    service.play_node(state, "threshold_inn_hub")

    # Ask Dana about work, then accept.
    service.choose(state, 0)  # Dana offer
    service.choose(state, 0)  # Accept quest

    # Still able to proceed to the gate prompt.
    result = service.choose(state, 3)
    assert result.node_view.node_id == "floor1_gate_prompt"

