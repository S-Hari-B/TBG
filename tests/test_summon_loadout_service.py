from tbg.core.rng import RNG
from tbg.data.repositories import ArmourRepository, ClassesRepository, SummonsRepository, WeaponsRepository
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

    service.equip_summon(state, "micro_raptor")
    assert service.get_equipped_summons(state) == ["micro_raptor"]

    service.unequip_summon(state, 0)
    assert service.get_equipped_summons(state) == []


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
        service.equip_summon(state, "unknown_summon")
    except ValueError as exc:
        assert "not known" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown summon.")


def test_max_equipped_enforced() -> None:
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

    for _ in range(service.MAX_EQUIPPED):
        service.equip_summon(state, "micro_raptor")

    try:
        service.equip_summon(state, "micro_raptor")
    except ValueError as exc:
        assert "loadout is full" in str(exc)
    else:
        raise AssertionError("Expected ValueError when loadout is full.")


def test_bond_capacity_enforced() -> None:
    state = _make_state_with_class("beastmaster")
    state.player.attributes.BOND = 10
    service = SummonLoadoutService(
        classes_repo=ClassesRepository(
            weapons_repo=WeaponsRepository(),
            armour_repo=ArmourRepository(),
            summons_repo=SummonsRepository(),
        ),
        summons_repo=SummonsRepository(),
    )

    service.equip_summon(state, "micro_raptor")
    service.equip_summon(state, "micro_raptor")
    assert service.get_equipped_summons(state) == ["micro_raptor", "micro_raptor"]

    try:
        service.equip_summon(state, "micro_raptor")
    except ValueError as exc:
        assert "capacity" in str(exc)
    else:
        raise AssertionError("Expected capacity ValueError.")


def test_bond_capacity_hawk_blocks_after_raptors() -> None:
    state = _make_state_with_class("beastmaster")
    state.player.attributes.BOND = 10
    service = SummonLoadoutService(
        classes_repo=ClassesRepository(
            weapons_repo=WeaponsRepository(),
            armour_repo=ArmourRepository(),
            summons_repo=SummonsRepository(),
        ),
        summons_repo=SummonsRepository(),
    )

    service.equip_summon(state, "micro_raptor")
    service.equip_summon(state, "micro_raptor")
    try:
        service.equip_summon(state, "black_hawk")
    except ValueError as exc:
        assert "capacity" in str(exc)
    else:
        raise AssertionError("Expected capacity ValueError.")


def test_reorder_summons() -> None:
    state = _make_state_with_class("beastmaster")
    state.player.attributes.BOND = 20
    service = SummonLoadoutService(
        classes_repo=ClassesRepository(
            weapons_repo=WeaponsRepository(),
            armour_repo=ArmourRepository(),
            summons_repo=SummonsRepository(),
        ),
        summons_repo=SummonsRepository(),
    )

    service.equip_summon(state, "micro_raptor")
    service.equip_summon(state, "black_hawk")
    service.move_equipped_summon(state, 0, 1)

    assert service.get_equipped_summons(state) == ["black_hawk", "micro_raptor"]
