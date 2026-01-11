from __future__ import annotations

import pytest

from tbg.domain.inventory import MemberEquipment
from tbg.services.battle_service import BattleService
from tbg.services.inventory_service import InventoryService
from tbg.services.save_service import SaveService
from tbg.services.story_service import StoryService
from tbg.services.errors import SaveLoadError
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


def _build_test_services() -> tuple[StoryService, BattleService, InventoryService, SaveService, dict]:
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
    story_service = StoryService(
        story_repo=story_repo,
        classes_repo=classes_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        party_members_repo=party_repo,
        inventory_service=inventory_service,
    )
    enemies_repo = EnemiesRepository()
    knowledge_repo = KnowledgeRepository()
    skills_repo = SkillsRepository()
    items_repo = ItemsRepository()
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
    save_service = SaveService(
        story_repo=story_repo,
        classes_repo=classes_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        items_repo=items_repo,
        party_members_repo=party_repo,
    )
    repos = {
        "weapons": weapons_repo,
        "armour": armour_repo,
        "items": items_repo,
        "party": party_repo,
    }
    return story_service, battle_service, inventory_service, save_service, repos


def test_save_round_trip_preserves_state() -> None:
    story_service, battle_service, inventory_service, save_service, repos = _build_test_services()
    state = story_service.start_new_game(seed=123, player_name="Tester")
    story_service.choose(state, 0)  # select first class
    state.gold = 77
    state.exp = 42
    state.flags["tutorial_complete"] = True
    state.pending_story_node_id = "forest_scream"
    state.pending_narration = [("forest_intro", "Intro text")]
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


def test_rng_determinism_survives_save_round_trip() -> None:
    story_service, battle_service, inventory_service, save_service, _ = _build_test_services()
    state = story_service.start_new_game(seed=999, player_name="Hero")
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
    story_service, battle_service, inventory_service, save_service, _ = _build_test_services()
    state = story_service.start_new_game(seed=1, player_name="Hero")
    payload = save_service.serialize(state)
    payload["save_version"] = 99
    with pytest.raises(SaveLoadError):
        save_service.deserialize(payload)


def test_deserialize_rejects_missing_required_fields() -> None:
    story_service, battle_service, inventory_service, save_service, _ = _build_test_services()
    state = story_service.start_new_game(seed=1, player_name="Hero")
    payload = save_service.serialize(state)
    payload["state"].pop("current_node_id")
    with pytest.raises(SaveLoadError):
        save_service.deserialize(payload)


def test_deserialize_rejects_unknown_ids() -> None:
    story_service, battle_service, inventory_service, save_service, _ = _build_test_services()
    state = story_service.start_new_game(seed=1, player_name="Hero")
    payload = save_service.serialize(state)
    payload["state"]["inventory"]["weapons"]["unknown_weapon"] = 1
    with pytest.raises(SaveLoadError):
        save_service.deserialize(payload)

