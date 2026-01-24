from __future__ import annotations

from tbg.core.rng import RNG
from tbg.data.repositories import ArmourRepository, ClassesRepository, WeaponsRepository
from tbg.domain.state import GameState
from tbg.services.attribute_allocation_service import (
    AttributeAllocationService,
    POINTS_PER_LEVEL,
)
from tbg.services.factories import create_player_from_class_id


def _make_state_and_service(
    *,
    class_id: str = "warrior",
    current_level: int | None = None,
    spent: int = 0,
):
    rng = RNG(7)
    state = GameState(seed=7, rng=rng, mode="camp_menu", current_node_id="class_select")
    weapons_repo = WeaponsRepository()
    armour_repo = ArmourRepository()
    classes_repo = ClassesRepository(weapons_repo=weapons_repo, armour_repo=armour_repo)
    player = create_player_from_class_id(
        class_id=class_id,
        name="Tester",
        classes_repo=classes_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        rng=rng,
    )
    state.player = player
    starting_level = classes_repo.get_starting_level(class_id)
    state.member_levels[player.id] = current_level if current_level is not None else starting_level
    state.player_attribute_points_spent = spent
    service = AttributeAllocationService(classes_repo=classes_repo)
    return state, service, starting_level


def test_points_derived_from_level() -> None:
    state, service, starting_level = _make_state_and_service()
    summary = service.get_player_attribute_points_summary(state)
    assert summary.earned == 0
    assert summary.available == 0

    state.member_levels[state.player.id] = starting_level + 1
    summary = service.get_player_attribute_points_summary(state)
    assert summary.earned == POINTS_PER_LEVEL
    assert summary.available == POINTS_PER_LEVEL


def test_points_respect_spent_and_lower_level_guard() -> None:
    state, service, starting_level = _make_state_and_service(spent=POINTS_PER_LEVEL)
    state.member_levels[state.player.id] = starting_level + 1
    summary = service.get_player_attribute_points_summary(state)
    assert summary.available == 0

    state.member_levels[state.player.id] = starting_level - 1
    summary = service.get_player_attribute_points_summary(state)
    assert summary.available == 0


def test_spend_rejects_when_no_points() -> None:
    state, service, _ = _make_state_and_service()
    before = state.player.attributes.STR
    result = service.spend_player_attribute_point(state, "STR")
    assert result.success is False
    assert state.player.attributes.STR == before
    assert state.player_attribute_points_spent == 0


def test_spend_rejects_invalid_attribute() -> None:
    state, service, starting_level = _make_state_and_service()
    state.member_levels[state.player.id] = starting_level + 1
    before = state.player.attributes.STR
    result = service.spend_player_attribute_point(state, "INVALID")
    assert result.success is False
    assert state.player.attributes.STR == before
    assert state.player_attribute_points_spent == 0


def test_spend_mutates_attribute_and_spent_points() -> None:
    state, service, starting_level = _make_state_and_service()
    state.member_levels[state.player.id] = starting_level + 1
    before = state.player.attributes.STR
    result = service.spend_player_attribute_point(state, "STR")
    assert result.success is True
    assert state.player.attributes.STR == before + 1
    assert state.player_attribute_points_spent == 1
    assert result.summary.available == 0


def test_spend_updates_scaled_stats() -> None:
    state, service, starting_level = _make_state_and_service()
    state.member_levels[state.player.id] = starting_level + 1
    before_attack = state.player.stats.attack
    result = service.spend_player_attribute_point(state, "STR")
    assert result.success is True
    assert state.player.stats.attack == before_attack + 1


def test_debug_bonus_affects_available_and_spend_order() -> None:
    state, service, starting_level = _make_state_and_service()
    state.player_attribute_points_debug_bonus = 2
    summary = service.get_player_attribute_points_summary(state)
    assert summary.available == 2
    assert summary.spent == 0

    result = service.spend_player_attribute_point(state, "STR")
    assert result.success is True
    assert state.player_attribute_points_spent == 0
    assert state.player_attribute_points_debug_bonus == 1

    state.member_levels[state.player.id] = starting_level + 1
    result = service.spend_player_attribute_point(state, "STR")
    assert result.success is True
    assert state.player_attribute_points_spent == 1
    assert state.player_attribute_points_debug_bonus == 1

    result = service.spend_player_attribute_point(state, "STR")
    assert result.success is True
    assert state.player_attribute_points_spent == 1
    assert state.player_attribute_points_debug_bonus == 0


def test_grant_debug_points_increases_available() -> None:
    state, service, _ = _make_state_and_service()
    result = service.grant_debug_attribute_points(state, 3)
    assert result.success is True
    assert result.summary.available == 3
    assert state.player_attribute_points_debug_bonus == 3
