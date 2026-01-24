from tbg.core.rng import RNG
from tbg.data.repositories import ArmourRepository, ClassesRepository, SummonsRepository, WeaponsRepository
from tbg.domain.entities import Attributes
from tbg.domain.state import GameState
from tbg.services.factories import create_player_from_class_id
from tbg.services.summon_loadout_service import SummonLoadoutService


def _make_state_with_class(class_id: str) -> GameState:
    rng = RNG(123)
    state = GameState(seed=123, rng=rng, mode="camp_menu", current_node_id="class_select")
    weapons_repo = WeaponsRepository()
    armour_repo = ArmourRepository()
    classes_repo = ClassesRepository(
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        summons_repo=SummonsRepository(),
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
    owned: dict[str, int] = {}
    for summon_id in class_def.default_equipped_summons:
        owned[summon_id] = owned.get(summon_id, 0) + 1
    for summon_id in class_def.known_summons:
        owned[summon_id] = max(owned.get(summon_id, 0), 1)
    state.owned_summons = owned
    return state


def test_equip_and_unequip_summon() -> None:
    state = _make_state_with_class("beastmaster")
    service = SummonLoadoutService(
        classes_repo=ClassesRepository(
            weapons_repo=WeaponsRepository(),
            armour_repo=ArmourRepository(),
            summons_repo=SummonsRepository(),
        ),
        summons_repo=SummonsRepository(),
    )

    service.equip_summon(state, state.player.id, "micro_raptor")
    assert service.get_equipped_summons(state, state.player.id) == ["micro_raptor"]

    service.unequip_summon(state, state.player.id, 0)
    assert service.get_equipped_summons(state, state.player.id) == []


def test_beastmaster_owned_counts_and_duplicate_block() -> None:
    state = _make_state_with_class("beastmaster")
    state.player.attributes.BOND = 50
    service = SummonLoadoutService(
        classes_repo=ClassesRepository(
            weapons_repo=WeaponsRepository(),
            armour_repo=ArmourRepository(),
            summons_repo=SummonsRepository(),
        ),
        summons_repo=SummonsRepository(),
    )

    assert state.owned_summons.get("micro_raptor") == 2
    assert state.owned_summons.get("black_hawk") == 1

    service.equip_summon(state, state.player.id, "micro_raptor")
    service.equip_summon(state, state.player.id, "micro_raptor")
    try:
        service.equip_summon(state, state.player.id, "micro_raptor")
    except ValueError as exc:
        assert "own another" in str(exc)
    else:
        raise AssertionError("Expected ValueError when equipping beyond owned count.")


def test_party_loadouts_share_owned_pool() -> None:
    state = _make_state_with_class("beastmaster")
    state.party_members = ["emma"]
    state.party_member_attributes["emma"] = Attributes(STR=2, DEX=4, INT=10, VIT=4, BOND=5)
    state.owned_summons = {"micro_raptor": 2}
    service = SummonLoadoutService(
        classes_repo=ClassesRepository(
            weapons_repo=WeaponsRepository(),
            armour_repo=ArmourRepository(),
            summons_repo=SummonsRepository(),
        ),
        summons_repo=SummonsRepository(),
    )

    service.equip_summon(state, state.player.id, "micro_raptor")
    service.equip_summon(state, state.player.id, "micro_raptor")
    try:
        service.equip_summon(state, "emma", "micro_raptor")
    except ValueError as exc:
        assert "own another" in str(exc)
    else:
        raise AssertionError("Expected shared ownership rejection.")


def test_party_member_bond_capacity_enforced() -> None:
    state = _make_state_with_class("beastmaster")
    state.party_members = ["emma"]
    state.party_member_attributes["emma"] = Attributes(STR=2, DEX=4, INT=10, VIT=4, BOND=4)
    state.owned_summons = {"micro_raptor": 1}
    service = SummonLoadoutService(
        classes_repo=ClassesRepository(
            weapons_repo=WeaponsRepository(),
            armour_repo=ArmourRepository(),
            summons_repo=SummonsRepository(),
        ),
        summons_repo=SummonsRepository(),
    )

    try:
        service.equip_summon(state, "emma", "micro_raptor")
    except ValueError as exc:
        assert "capacity" in str(exc)
    else:
        raise AssertionError("Expected bond capacity rejection.")


def test_equip_rejects_unknown_summon() -> None:
    state = _make_state_with_class("beastmaster")
    service = SummonLoadoutService(
        classes_repo=ClassesRepository(
            weapons_repo=WeaponsRepository(),
            armour_repo=ArmourRepository(),
            summons_repo=SummonsRepository(),
        ),
        summons_repo=SummonsRepository(),
    )

    try:
        service.equip_summon(state, state.player.id, "unknown_summon")
    except ValueError as exc:
        assert "not known" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown summon.")


def test_no_slot_cap_when_owned_and_bond_allow() -> None:
    state = _make_state_with_class("beastmaster")
    state.player.attributes.BOND = 50
    state.owned_summons["micro_raptor"] = 10
    service = SummonLoadoutService(
        classes_repo=ClassesRepository(
            weapons_repo=WeaponsRepository(),
            armour_repo=ArmourRepository(),
            summons_repo=SummonsRepository(),
        ),
        summons_repo=SummonsRepository(),
    )

    for _ in range(6):
        service.equip_summon(state, state.player.id, "micro_raptor")

    assert service.get_equipped_summons(state, state.player.id) == ["micro_raptor"] * 6


def test_bond_capacity_enforced() -> None:
    state = _make_state_with_class("beastmaster")
    state.player.attributes.BOND = 10
    state.owned_summons["micro_raptor"] = 3
    service = SummonLoadoutService(
        classes_repo=ClassesRepository(
            weapons_repo=WeaponsRepository(),
            armour_repo=ArmourRepository(),
            summons_repo=SummonsRepository(),
        ),
        summons_repo=SummonsRepository(),
    )

    service.equip_summon(state, state.player.id, "micro_raptor")
    service.equip_summon(state, state.player.id, "micro_raptor")
    assert service.get_equipped_summons(state, state.player.id) == ["micro_raptor", "micro_raptor"]

    try:
        service.equip_summon(state, state.player.id, "micro_raptor")
    except ValueError as exc:
        assert "capacity" in str(exc)
    else:
        raise AssertionError("Expected capacity ValueError.")


def test_bond_capacity_hawk_blocks_after_raptors() -> None:
    state = _make_state_with_class("beastmaster")
    state.player.attributes.BOND = 10
    state.owned_summons["micro_raptor"] = 2
    state.owned_summons["black_hawk"] = 1
    service = SummonLoadoutService(
        classes_repo=ClassesRepository(
            weapons_repo=WeaponsRepository(),
            armour_repo=ArmourRepository(),
            summons_repo=SummonsRepository(),
        ),
        summons_repo=SummonsRepository(),
    )

    service.equip_summon(state, state.player.id, "micro_raptor")
    service.equip_summon(state, state.player.id, "micro_raptor")
    try:
        service.equip_summon(state, state.player.id, "black_hawk")
    except ValueError as exc:
        assert "capacity" in str(exc)
    else:
        raise AssertionError("Expected capacity ValueError.")


def test_reorder_summons() -> None:
    state = _make_state_with_class("beastmaster")
    state.player.attributes.BOND = 20
    state.owned_summons["micro_raptor"] = 1
    state.owned_summons["black_hawk"] = 1
    service = SummonLoadoutService(
        classes_repo=ClassesRepository(
            weapons_repo=WeaponsRepository(),
            armour_repo=ArmourRepository(),
            summons_repo=SummonsRepository(),
        ),
        summons_repo=SummonsRepository(),
    )

    service.equip_summon(state, state.player.id, "micro_raptor")
    service.equip_summon(state, state.player.id, "black_hawk")
    service.move_equipped_summon(state, state.player.id, 0, 1)

    assert service.get_equipped_summons(state, state.player.id) == ["black_hawk", "micro_raptor"]
