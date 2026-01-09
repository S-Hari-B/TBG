from tbg.core.rng import RNG
from tbg.data.repositories import ArmourRepository, ClassesRepository, PartyMembersRepository, WeaponsRepository
from tbg.domain.state import GameState
from tbg.services.factories import create_player_from_class_id
from tbg.services.inventory_service import (
    EquipFailedEvent,
    InventoryService,
    ItemEquippedEvent,
    ItemUnequippedEvent,
)


def _make_state_and_service(class_id: str = "warrior", with_party: bool = True):
    rng = RNG(42)
    state = GameState(seed=42, rng=rng, mode="game_menu", current_node_id="class_select")
    weapons_repo = WeaponsRepository()
    armour_repo = ArmourRepository()
    party_repo = PartyMembersRepository()
    classes_repo = ClassesRepository(weapons_repo=weapons_repo, armour_repo=armour_repo)
    inventory_service = InventoryService(
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        party_members_repo=party_repo,
    )
    player = create_player_from_class_id(
        class_id=class_id,
        name="Tester",
        classes_repo=classes_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        rng=rng,
    )
    state.player = player
    class_def = classes_repo.get(class_id)
    inventory_service.initialize_player_loadout(state, player.id, class_def)
    if with_party:
        state.party_members = ["emma"]
        member_def = party_repo.get("emma")
        inventory_service.initialize_party_member_loadout(state, "emma", member_def)
    return state, inventory_service, weapons_repo, armour_repo, party_repo


def test_equip_weapon_consumes_inventory_and_updates_slots() -> None:
    state, inventory_service, *_ = _make_state_and_service(class_id="warrior", with_party=False)
    player_id = state.player.id
    equipment = state.equipment[player_id]
    equipment.weapon_slots = [None, None]
    state.inventory.weapons.clear()
    state.inventory.add_weapon("iron_dagger")

    events = inventory_service.equip_weapon(
        state, player_id, "iron_dagger", slot_index=0, allow_replace=False
    )

    assert not state.inventory.weapons
    assert equipment.weapon_slots[0] == "iron_dagger"
    assert any(isinstance(event, ItemEquippedEvent) for event in events)


def test_equip_two_handed_weapon_replaces_existing_slots() -> None:
    state, inventory_service, *_ = _make_state_and_service(class_id="warrior", with_party=False)
    player_id = state.player.id
    state.inventory.add_weapon("fire_staff")

    events = inventory_service.equip_weapon(
        state, player_id, "fire_staff", slot_index=None, allow_replace=True
    )

    equipment = state.equipment[player_id]
    assert equipment.weapon_slots == ["fire_staff", "fire_staff"]
    assert state.inventory.weapons.get("fire_staff") is None
    assert state.inventory.weapons.get("iron_sword") == 1
    assert any(isinstance(event, ItemEquippedEvent) for event in events)


def test_shared_inventory_prevents_double_equip() -> None:
    state, inventory_service, *_ = _make_state_and_service(class_id="warrior", with_party=True)
    player_id = state.player.id
    equipment_player = state.equipment[player_id]
    equipment_player.weapon_slots = [None, None]
    equipment_emma = state.equipment["emma"]
    equipment_emma.weapon_slots = [None, None]
    state.inventory.weapons.clear()
    state.inventory.add_weapon("iron_dagger", 1)

    inventory_service.equip_weapon(state, player_id, "iron_dagger", slot_index=0, allow_replace=False)
    events = inventory_service.equip_weapon(
        state, "emma", "iron_dagger", slot_index=0, allow_replace=False
    )

    assert any(
        isinstance(event, EquipFailedEvent) and event.reason == "not_in_inventory" for event in events
    )


def test_equip_armour_returns_replaced_piece_to_inventory() -> None:
    state, inventory_service, *_ = _make_state_and_service(class_id="warrior", with_party=False)
    player_id = state.player.id
    equipment = state.equipment[player_id]
    assert equipment.armour_slots["hands"] is not None
    state.inventory.add_armour("leather_gloves")

    events = inventory_service.equip_armour(
        state, player_id, "leather_gloves", allow_replace=True
    )

    assert equipment.armour_slots["hands"] == "leather_gloves"
    assert state.inventory.armour.get("iron_gauntlets")
    assert any(isinstance(event, ItemEquippedEvent) for event in events)


def test_unequip_weapon_returns_to_inventory() -> None:
    state, inventory_service, *_ = _make_state_and_service(class_id="warrior", with_party=False)
    player_id = state.player.id
    equipment = state.equipment[player_id]
    assert equipment.weapon_slots[0] is not None

    events = inventory_service.unequip_weapon_slot(state, player_id, 0)

    assert any(isinstance(event, ItemUnequippedEvent) for event in events)
    assert equipment.weapon_slots[0] is None
    assert state.inventory.weapons


