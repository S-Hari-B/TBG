from tbg.core.rng import RNG
from tbg.data.repositories import (
    ArmourRepository,
    ClassesRepository,
    EnemiesRepository,
    FloorsRepository,
    ItemsRepository,
    KnowledgeRepository,
    LocationsRepository,
    LootTablesRepository,
    PartyMembersRepository,
    SkillsRepository,
    StoryRepository,
    WeaponsRepository,
    QuestsRepository,
)
from tbg.services.battle_service import BattleService
from tbg.services.area_service_v2 import AreaServiceV2
from tbg.services.inventory_service import InventoryService
from tbg.services.story_service import BattleRequestedEvent, StoryService
from tbg.services.quest_service import QuestService


def _build_services() -> tuple[StoryService, BattleService, QuestService]:
    weapons_repo = WeaponsRepository()
    armour_repo = ArmourRepository()
    party_repo = PartyMembersRepository()
    inventory_service = InventoryService(
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        party_members_repo=party_repo,
    )
    items_repo = ItemsRepository()
    floors_repo = FloorsRepository()
    locations_repo = LocationsRepository(floors_repo=floors_repo)
    story_repo = StoryRepository()
    quests_repo = QuestsRepository(
        items_repo=items_repo,
        locations_repo=locations_repo,
        story_repo=story_repo,
    )
    quest_service = QuestService(
        quests_repo=quests_repo,
        items_repo=items_repo,
        locations_repo=locations_repo,
        party_members_repo=party_repo,
    )
    story_service = StoryService(
        story_repo=story_repo,
        classes_repo=ClassesRepository(weapons_repo=weapons_repo, armour_repo=armour_repo),
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        party_members_repo=party_repo,
        inventory_service=inventory_service,
        quest_service=quest_service,
    )
    battle_service = BattleService(
        enemies_repo=EnemiesRepository(),
        party_members_repo=party_repo,
        knowledge_repo=KnowledgeRepository(),
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        skills_repo=SkillsRepository(),
        items_repo=items_repo,
        loot_tables_repo=LootTablesRepository(),
        floors_repo=floors_repo,
        locations_repo=locations_repo,
        quest_service=quest_service,
    )
    return story_service, battle_service, quest_service


def _make_state_with_player(story_service: StoryService):
    state = story_service.start_new_game(seed=111, player_name="Hero")
    view = story_service.get_current_node_view(state)
    if view.node_id == "inn_orientation_choice":
        story_service.choose(state, 1)  # Continue
    story_service.choose(state, 0)  # warrior
    state.story_checkpoint_node_id = None
    state.story_checkpoint_location_id = None
    state.story_checkpoint_thread_id = None
    state.pending_story_node_id = None
    state.current_node_id = "threshold_inn_hub_router"
    return state


def _defeat_enemies(battle_state) -> None:
    for enemy in battle_state.enemies:
        enemy.stats.hp = 0


def test_dana_side_quest_turn_in_flow() -> None:
    story_service, battle_service, quest_service = _build_services()
    state = _make_state_with_player(story_service)

    state.flags["flag_sq_dana_offered"] = True
    story_service.play_node(state, "dana_sidequest_accept")
    story_service.resume_pending_flow(state)
    starting_gold = state.gold

    # Turn-in before ready should fail.
    story_service.play_node(state, "dana_turn_in_check")
    story_service.resume_pending_flow(state)
    story_service.resume_pending_flow(state)
    assert state.flags.get("flag_sq_dana_completed") is not True

    # Earn teeth and trigger readiness via quest refresh.
    state.inventory.items["wolf_tooth"] = 3
    quest_service.refresh_collect_objectives(state)
    assert state.flags.get("flag_sq_dana_ready") is True

    # Turn-in success should remove items and grant rewards once.
    story_service.play_node(state, "dana_turn_in_check")
    story_service.resume_pending_flow(state)
    story_service.resume_pending_flow(state)
    assert state.flags.get("flag_sq_dana_completed") is True
    assert state.flags.get("flag_sq_dana_ready") is False
    assert state.inventory.items.get("wolf_tooth", 0) == 0
    assert state.gold > starting_gold

    gold_after = state.gold
    story_service.play_node(state, "dana_turn_in_check")
    story_service.resume_pending_flow(state)
    story_service.resume_pending_flow(state)
    assert state.gold == gold_after


def test_cerel_kill_quest_turn_in_flow() -> None:
    story_service, battle_service, _quest_service = _build_services()
    state = _make_state_with_player(story_service)

    state.flags["flag_sq_cerel_offered"] = True
    story_service.play_node(state, "cerel_kill_quest_accept")
    story_service.resume_pending_flow(state)
    starting_gold = state.gold

    # Turn-in before ready should fail.
    story_service.play_node(state, "cerel_turn_in_check")
    story_service.resume_pending_flow(state)
    story_service.resume_pending_flow(state)
    assert state.flags.get("flag_sq_cerel_completed") is not True

    # 5 patrol battles = 10 goblin grunts
    for _ in range(5):
        battle_state, _ = battle_service.start_battle("goblin_camp_patrol", state)
        _defeat_enemies(battle_state)
        battle_service.apply_victory_rewards(battle_state, state)

    # 3 enforcer battles = 6 half-orcs (completes requirement)
    for _ in range(3):
        battle_state, _ = battle_service.start_battle("half_orc_pair", state)
        _defeat_enemies(battle_state)
        battle_service.apply_victory_rewards(battle_state, state)

    assert state.flags.get("flag_kill_goblin_grunt_10") is True
    assert state.flags.get("flag_kill_half_orc_5") is True
    assert state.flags.get("flag_sq_cerel_ready") is True

    # Turn-in success grants reward once.
    story_service.play_node(state, "cerel_turn_in_check")
    story_service.resume_pending_flow(state)
    story_service.resume_pending_flow(state)
    assert state.flags.get("flag_sq_cerel_completed") is True
    assert state.flags.get("flag_sq_cerel_ready") is False
    assert state.gold > starting_gold

    gold_after = state.gold
    story_service.play_node(state, "cerel_turn_in_check")
    story_service.resume_pending_flow(state)
    story_service.resume_pending_flow(state)
    assert state.gold == gold_after


def test_protoquest_turn_in_rewards_once() -> None:
    story_service, _battle_service, quest_service = _build_services()
    state = _make_state_with_player(story_service)

    starting_gold = state.gold

    # Completing ruins should only set ready flag, no gold.
    story_service.play_node(state, "protoquest_offer")
    story_service.play_node(state, "protoquest_accept")
    assert state.flags.get("flag_protoquest_accepted") is True
    story_service.resume_pending_flow(state)

    floors_repo = FloorsRepository()
    locations_repo = LocationsRepository(floors_repo=floors_repo)
    area_service = AreaServiceV2(
        floors_repo=floors_repo,
        locations_repo=locations_repo,
        quest_service=quest_service,
    )
    state.current_location_id = "threshold_inn"
    area_service.travel_to(state, "shoreline_ruins")

    assert state.flags.get("flag_protoquest_ready") is True
    assert state.flags.get("flag_protoquest_completed") is not True
    gold_after_battle = state.gold
    potions_before_turn_in = state.inventory.items.get("potion_hp_small", 0)

    # Turn in to Dana for reward.
    story_service.play_node(state, "dana_protoquest_turn_in_check")
    story_service.resume_pending_flow(state)
    story_service.resume_pending_flow(state)
    assert state.flags.get("flag_protoquest_completed") is True
    assert state.flags.get("flag_protoquest_ready") is False
    assert state.gold > gold_after_battle
    assert state.inventory.items.get("potion_hp_small", 0) > potions_before_turn_in
    potions_after_turn_in = state.inventory.items.get("potion_hp_small", 0)

    # Turn in again should not grant more gold.
    gold_after = state.gold
    story_service.play_node(state, "dana_protoquest_turn_in_check")
    story_service.resume_pending_flow(state)
    story_service.resume_pending_flow(state)
    assert state.gold == gold_after
    assert state.inventory.items.get("potion_hp_small", 0) == potions_after_turn_in


def test_protoquest_not_ready_from_tide_cave_but_ready_after_ruins() -> None:
    story_service, battle_service, quest_service = _build_services()
    state = _make_state_with_player(story_service)

    story_service.play_node(state, "protoquest_offer")
    story_service.play_node(state, "protoquest_accept")
    story_service.resume_pending_flow(state)

    story_service.play_node(state, "tide_cave_router")
    battle_state, _ = battle_service.start_battle("cave_sentry_pair", state)
    _defeat_enemies(battle_state)
    battle_service.apply_victory_rewards(battle_state, state)

    assert state.flags.get("flag_protoquest_ready") is not True

    story_service.play_node(state, "threshold_inn_hub_router")
    while state.pending_story_node_id:
        story_service.resume_pending_flow(state)
    assert "Turn in: Dana's rumor reward" not in story_service.get_current_node_view(state).choices

    floors_repo = FloorsRepository()
    locations_repo = LocationsRepository(floors_repo=floors_repo)
    area_service = AreaServiceV2(
        floors_repo=floors_repo,
        locations_repo=locations_repo,
        quest_service=quest_service,
    )
    state.current_location_id = "threshold_inn"
    area_service.travel_to(state, "shoreline_ruins")
    assert state.flags.get("flag_protoquest_ready") is True

    story_service.play_node(state, "threshold_inn_hub_router")
    while state.pending_story_node_id:
        story_service.resume_pending_flow(state)
    assert "Turn in: Dana's rumor reward" in story_service.get_current_node_view(state).choices


def test_tide_cave_reward_grants_debuff_items_once() -> None:
    story_service, battle_service, _quest_service = _build_services()
    state = _make_state_with_player(story_service)

    story_service.play_node(state, "tide_cave_router")
    events: list[object] = []
    while state.pending_story_node_id:
        events.extend(story_service.resume_pending_flow(state))
        if any(isinstance(evt, BattleRequestedEvent) for evt in events):
            break
    battle_state, _ = battle_service.start_battle("cave_sentry_pair", state)
    _defeat_enemies(battle_state)
    battle_service.apply_victory_rewards(battle_state, state)

    vials_before_turn_in = state.inventory.items.get("weakening_vial", 0)
    powder_before_turn_in = state.inventory.items.get("armor_sunder_powder", 0)

    story_service.play_node(state, "tide_cave_report_solo")
    story_service.resume_pending_flow(state)

    assert state.inventory.items.get("weakening_vial", 0) > vials_before_turn_in
    assert state.inventory.items.get("armor_sunder_powder", 0) > powder_before_turn_in
    vials_after_turn_in = state.inventory.items.get("weakening_vial", 0)
    powder_after_turn_in = state.inventory.items.get("armor_sunder_powder", 0)

    story_service.play_node(state, "tide_cave_report_solo")
    story_service.resume_pending_flow(state)

    assert state.inventory.items.get("weakening_vial", 0) == vials_after_turn_in
    assert state.inventory.items.get("armor_sunder_powder", 0) == powder_after_turn_in


def test_tide_cave_router_blocks_after_completion() -> None:
    story_service, _battle_service, _quest_service = _build_services()
    state = _make_state_with_player(story_service)
    state.flags["flag_tide_cave_completed"] = True

    events = story_service.play_node(state, "tide_cave_router")
    events.extend(story_service.resume_pending_flow(state))
    assert "tide_cave_cache" not in state.quests_active
    assert not any(isinstance(evt, BattleRequestedEvent) for evt in events)
    assert state.current_node_id == "tide_cave_already_cleared"


def test_tide_cave_router_happy_path_starts_battle() -> None:
    story_service, _battle_service, _quest_service = _build_services()
    state = _make_state_with_player(story_service)

    events = story_service.play_node(state, "tide_cave_router")
    while state.pending_story_node_id:
        events.extend(story_service.resume_pending_flow(state))
        if any(isinstance(evt, BattleRequestedEvent) for evt in events):
            break
    assert "tide_cave_cache" in state.quests_active
    assert any(isinstance(evt, BattleRequestedEvent) for evt in events)


def test_rampager_quest_reward_grants_bundle_once() -> None:
    story_service, battle_service, _quest_service = _build_services()
    state = _make_state_with_player(story_service)

    state.flags["flag_sq_cerel_rampager_offered"] = True
    story_service.play_node(state, "cerel_rampager_quest_accept")
    story_service.resume_pending_flow(state)

    battle_state, _ = battle_service.start_battle("goblin_rampager", state)
    _defeat_enemies(battle_state)
    battle_service.apply_victory_rewards(battle_state, state)

    gold_before_turn_in = state.gold
    hp_before_turn_in = state.inventory.items.get("potion_hp_small", 0)
    energy_before_turn_in = state.inventory.items.get("potion_energy_small", 0)

    assert state.flags.get("flag_sq_cerel_rampager_ready") is True

    story_service.play_node(state, "cerel_rampager_turn_in_check")
    while state.pending_story_node_id:
        story_service.resume_pending_flow(state)

    assert state.gold > gold_before_turn_in
    assert state.inventory.items.get("potion_hp_small", 0) > hp_before_turn_in
    assert state.inventory.items.get("potion_energy_small", 0) > energy_before_turn_in
    hp_after_turn_in = state.inventory.items.get("potion_hp_small", 0)
    energy_after_turn_in = state.inventory.items.get("potion_energy_small", 0)

    gold_after = state.gold
    story_service.play_node(state, "cerel_rampager_turn_in_check")
    while state.pending_story_node_id:
        story_service.resume_pending_flow(state)

    assert state.gold == gold_after
    assert state.inventory.items.get("potion_hp_small", 0) == hp_after_turn_in
    assert state.inventory.items.get("potion_energy_small", 0) == energy_after_turn_in
