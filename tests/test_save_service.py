from __future__ import annotations

import pytest

from tbg.domain.inventory import MemberEquipment
from tbg.domain.quest_state import QuestObjectiveProgress, QuestProgress
from tbg.services.battle_service import BattleService
from tbg.services.inventory_service import InventoryService
from tbg.services.save_service import SaveService
from tbg.services.story_service import StoryService
from tbg.services.errors import SaveLoadError
from tbg.services.area_service_v2 import AreaServiceV2
from tbg.services.errors import TravelBlockedError
from tbg.data.repositories import (
    ArmourRepository,
    AreasRepository,
    ClassesRepository,
    EnemiesRepository,
    FloorsRepository,
    ItemsRepository,
    KnowledgeRepository,
    LocationsRepository,
    LootTablesRepository,
    PartyMembersRepository,
    QuestsRepository,
    SkillsRepository,
    StoryRepository,
    WeaponsRepository,
)
from tbg.services.quest_service import QuestService


def _build_test_services() -> tuple[StoryService, BattleService, InventoryService, SaveService, AreaServiceV2, dict]:
    weapons_repo = WeaponsRepository()
    armour_repo = ArmourRepository()
    story_repo = StoryRepository()
    classes_repo = ClassesRepository(weapons_repo=weapons_repo, armour_repo=armour_repo)
    party_repo = PartyMembersRepository()
    inventory_service = InventoryService(
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        party_members_repo=party_repo,
    )
    items_repo = ItemsRepository()
    areas_repo = AreasRepository()
    floors_repo = FloorsRepository()
    locations_repo = LocationsRepository(floors_repo=floors_repo)
    quests_repo = QuestsRepository(
        items_repo=items_repo,
        locations_repo=locations_repo,
        story_repo=story_repo,
    )
    quest_service = QuestService(
        quests_repo=quests_repo,
        items_repo=items_repo,
        areas_repo=locations_repo,
        party_members_repo=party_repo,
    )
    story_service = StoryService(
        story_repo=story_repo,
        classes_repo=classes_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        party_members_repo=party_repo,
        inventory_service=inventory_service,
        quest_service=quest_service,
    )
    enemies_repo = EnemiesRepository()
    knowledge_repo = KnowledgeRepository()
    skills_repo = SkillsRepository()
    loot_repo = LootTablesRepository()
    battle_service = BattleService(
        enemies_repo=enemies_repo,
        party_members_repo=party_repo,
        knowledge_repo=knowledge_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        skills_repo=skills_repo,
        items_repo=items_repo,
        loot_tables_repo=loot_repo,
    )
    area_service = AreaServiceV2(
        floors_repo=floors_repo, locations_repo=locations_repo, quest_service=quest_service
    )
    save_service = SaveService(
        story_repo=story_repo,
        classes_repo=classes_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        items_repo=items_repo,
        party_members_repo=party_repo,
        locations_repo=locations_repo,
        quests_repo=quests_repo,
    )
    repos = {
        "weapons": weapons_repo,
        "armour": armour_repo,
        "items": items_repo,
        "party": party_repo,
    }
    return story_service, battle_service, inventory_service, save_service, area_service, repos


def test_save_round_trip_preserves_state() -> None:
    (
        story_service,
        battle_service,
        inventory_service,
        save_service,
        area_service,
        repos,
    ) = _build_test_services()
    state = story_service.start_new_game(seed=123, player_name="Tester")
    area_service.initialize_state(state)
    area_service.initialize_state(state)
    story_service.choose(state, 0)  # select first class
    state.gold = 77
    state.exp = 42
    state.flags["tutorial_complete"] = True
    state.pending_story_node_id = "trial_setup"
    state.pending_narration = [("arrival_beach_wake", "Intro text")]
    weapon_id = repos["weapons"].all()[0].id
    armour_id = repos["armour"].all()[0].id
    item_id = repos["items"].all()[0].id
    state.inventory.weapons[weapon_id] = 1
    state.inventory.armour[armour_id] = 2
    state.inventory.items[item_id] = 3
    state.party_members.append(repos["party"].all()[0].id)
    state.member_levels[state.player.id] = 2
    state.member_exp[state.player.id] = 150
    state.member_levels[state.party_members[0]] = 3
    state.member_exp[state.party_members[0]] = 90
    member_equipment = MemberEquipment()
    member_equipment.weapon_slots = [weapon_id, None]
    member_equipment.armour_slots["body"] = armour_id
    state.equipment[state.player.id] = member_equipment
    state.camp_message = "Rest up."
    state.mode = "camp_menu"
    state.story_checkpoint_node_id = "battle_trial_1v1"
    state.story_checkpoint_location_id = "threshold_inn"
    state.story_checkpoint_thread_id = "main_story"
    state.location_visits = {"threshold_inn": 2, "open_plains": 1}
    state.shop_stock_remaining = {
        "threshold_inn": {"threshold_inn_item_shop": {"potion_hp_small": 3}}
    }
    state.shop_stock_visit_index = {"threshold_inn": {"threshold_inn_item_shop": 2}}
    state.quests_active["cerel_kill_hunt"] = QuestProgress(
        quest_id="cerel_kill_hunt",
        objectives=[
            QuestObjectiveProgress(current=4, completed=False),
            QuestObjectiveProgress(current=2, completed=False),
        ],
    )
    state.quests_completed.append("cerel_kill_hunt")

    payload = save_service.serialize(state)
    restored = save_service.deserialize(payload)

    assert restored.seed == state.seed
    assert restored.mode == state.mode
    assert restored.current_node_id == state.current_node_id
    assert restored.player == state.player
    assert restored.inventory.weapons == state.inventory.weapons
    assert restored.inventory.armour == state.inventory.armour
    assert restored.inventory.items == state.inventory.items
    assert restored.equipment[state.player.id].weapon_slots == [weapon_id, None]
    assert restored.pending_narration == state.pending_narration
    assert restored.pending_story_node_id == state.pending_story_node_id
    assert restored.camp_message == state.camp_message
    assert restored.current_location_id == state.current_location_id
    assert restored.visited_locations == state.visited_locations
    assert restored.location_entry_seen == state.location_entry_seen
    assert restored.location_visits == state.location_visits
    assert restored.shop_stock_remaining == state.shop_stock_remaining
    assert restored.shop_stock_visit_index == state.shop_stock_visit_index
    assert restored.story_checkpoint_node_id == state.story_checkpoint_node_id
    assert restored.story_checkpoint_location_id == state.story_checkpoint_location_id
    assert restored.story_checkpoint_thread_id == state.story_checkpoint_thread_id
    assert "cerel_kill_hunt" in restored.quests_active
    assert restored.quests_completed == state.quests_completed


def test_rng_determinism_survives_save_round_trip() -> None:
    (
        story_service,
        battle_service,
        inventory_service,
        save_service,
        area_service,
        _,
    ) = _build_test_services()
    state = story_service.start_new_game(seed=999, player_name="Hero")
    area_service.initialize_state(state)
    area_service.initialize_state(state)
    story_service.choose(state, 0)
    state.rng.randint(1, 100)  # advance RNG before saving
    payload = save_service.serialize(state)

    battle_state_post_save, battle_events_post_save = battle_service.start_battle("goblin_pack_3", state)
    enemy_ids_post_save = [enemy.instance_id for enemy in battle_state_post_save.enemies]
    battle_id_post_save = battle_state_post_save.battle_id

    restored_state = save_service.deserialize(payload)
    battle_state_after_load, battle_events_after_load = battle_service.start_battle(
        "goblin_pack_3", restored_state
    )
    enemy_ids_after_load = [enemy.instance_id for enemy in battle_state_after_load.enemies]

    assert battle_state_after_load.battle_id == battle_id_post_save
    assert enemy_ids_after_load == enemy_ids_post_save
    # Battle events lists include BattleStartedEvent first with enemy names.
    assert isinstance(battle_events_post_save[0].enemy_names, list)
    assert [
        event.enemy_names for event in battle_events_after_load if hasattr(event, "enemy_names")
    ] == [
        event.enemy_names for event in battle_events_post_save if hasattr(event, "enemy_names")
    ]


def test_deserialize_rejects_unsupported_version() -> None:
    story_service, _, _, save_service, area_service, _ = _build_test_services()
    state = story_service.start_new_game(seed=1, player_name="Hero")
    area_service.initialize_state(state)
    area_service.initialize_state(state)
    payload = save_service.serialize(state)
    payload["save_version"] = 99
    with pytest.raises(SaveLoadError):
        save_service.deserialize(payload)


def test_deserialize_rejects_legacy_payload() -> None:
    story_service, _, _, save_service, area_service, _ = _build_test_services()
    state = story_service.start_new_game(seed=1, player_name="Hero")
    area_service.initialize_state(state)
    payload = save_service.serialize(state)
    payload.pop("save_version", None)
    with pytest.raises(SaveLoadError, match="Save format changed"):
        save_service.deserialize(payload)


def test_deserialize_rejects_unknown_location() -> None:
    story_service, _, _, save_service, area_service, _ = _build_test_services()
    state = story_service.start_new_game(seed=1, player_name="Hero")
    area_service.initialize_state(state)
    payload = save_service.serialize(state)
    payload["state"]["current_location_id"] = "missing_location"
    payload["save_version"] = 2
    with pytest.raises(SaveLoadError, match="unknown location"):
        save_service.deserialize(payload)


def test_deserialize_rejects_missing_required_fields() -> None:
    story_service, _, _, save_service, area_service, _ = _build_test_services()
    state = story_service.start_new_game(seed=1, player_name="Hero")
    area_service.initialize_state(state)
    area_service.initialize_state(state)
    payload = save_service.serialize(state)
    payload["state"].pop("current_node_id")
    with pytest.raises(SaveLoadError):
        save_service.deserialize(payload)


def test_deserialize_rejects_unknown_ids() -> None:
    story_service, _, _, save_service, area_service, _ = _build_test_services()
    state = story_service.start_new_game(seed=1, player_name="Hero")
    area_service.initialize_state(state)
    area_service.initialize_state(state)
    payload = save_service.serialize(state)
    payload["state"]["inventory"]["weapons"]["unknown_weapon"] = 1
    with pytest.raises(SaveLoadError):
        save_service.deserialize(payload)


def test_checkpoint_blocks_story_progress_travel_after_load() -> None:
    (
        story_service,
        _,
        _,
        save_service,
        area_service,
        _,
    ) = _build_test_services()
    state = story_service.start_new_game(seed=555, player_name="Hero")
    area_service.initialize_state(state)
    state.story_checkpoint_node_id = "battle_party_pack"
    state.story_checkpoint_location_id = "threshold_inn"
    state.story_checkpoint_thread_id = "main_story"

    payload = save_service.serialize(state)
    restored = save_service.deserialize(payload)

    with pytest.raises(TravelBlockedError):
        area_service.travel_to(restored, "floor_one_gate")

    restored.story_checkpoint_node_id = None
    restored.story_checkpoint_location_id = None
    restored.story_checkpoint_thread_id = None
    area_service.travel_to(restored, "floor_one_gate")


def test_missing_quest_fields_default_empty() -> None:
    (
        story_service,
        _battle_service,
        _inventory_service,
        save_service,
        area_service,
        _repos,
    ) = _build_test_services()
    state = story_service.start_new_game(seed=2024, player_name="Tester")
    area_service.initialize_state(state)
    payload = save_service.serialize(state)
    payload_state = payload.get("state", {})
    if isinstance(payload_state, dict):
        payload_state.pop("quests_active", None)
        payload_state.pop("quests_completed", None)
        payload_state.pop("quests_turned_in", None)
    restored = save_service.deserialize(payload)
    assert restored.quests_active == {}
    assert restored.quests_completed == []
    assert restored.quests_turned_in == []

