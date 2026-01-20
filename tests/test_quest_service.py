from __future__ import annotations

from tbg.core.rng import RNG
from tbg.data.repositories import (
    ArmourRepository,
    ClassesRepository,
    FloorsRepository,
    ItemsRepository,
    LocationsRepository,
    PartyMembersRepository,
    QuestsRepository,
    StoryRepository,
    WeaponsRepository,
)
from tbg.domain.state import GameState
from tbg.services.factories import create_player_from_class_id
from tbg.services.quest_service import QuestService


def _build_quest_service() -> QuestService:
    items_repo = ItemsRepository()
    floors_repo = FloorsRepository()
    locations_repo = LocationsRepository(floors_repo=floors_repo)
    story_repo = StoryRepository()
    quests_repo = QuestsRepository(
        items_repo=items_repo,
        locations_repo=locations_repo,
        story_repo=story_repo,
    )
    party_repo = PartyMembersRepository()
    return QuestService(
        quests_repo=quests_repo,
        items_repo=items_repo,
        locations_repo=locations_repo,
        party_members_repo=party_repo,
    )


def _make_state() -> GameState:
    rng = RNG(101)
    weapons_repo = WeaponsRepository()
    armour_repo = ArmourRepository()
    classes_repo = ClassesRepository(weapons_repo=weapons_repo, armour_repo=armour_repo)
    state = GameState(seed=101, rng=rng, mode="story", current_node_id="threshold_inn_hub_router")
    state.player = create_player_from_class_id(
        "warrior",
        name="Hero",
        classes_repo=classes_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        rng=rng,
    )
    state.member_levels[state.player.id] = 1
    state.member_exp[state.player.id] = 0
    state.current_location_id = "goblin_cave_entrance"
    return state


def test_accept_progress_turn_in_kill_quest() -> None:
    quest_service = _build_quest_service()
    state = _make_state()
    state.flags["flag_sq_cerel_offered"] = True

    update = quest_service.accept_quest(state, "cerel_kill_hunt")
    assert update is not None and update.accepted is True
    assert "cerel_kill_hunt" in state.quests_active
    assert state.flags.get("flag_sq_cerel_accepted") is True

    defeated_tags = [["goblin"]] * 10 + [["orc"]] * 5
    quest_service.record_battle_victory(state, defeated_tags)
    assert "cerel_kill_hunt" in state.quests_completed
    assert state.flags.get("flag_sq_cerel_ready") is True

    gold_before = state.gold
    update = quest_service.turn_in_quest(state, "cerel_kill_hunt")
    assert update is not None and update.turned_in is True
    assert state.gold == gold_before + 30
    assert "cerel_kill_hunt" in state.quests_turned_in
    assert "cerel_kill_hunt" not in state.quests_active
    assert state.flags.get("flag_sq_cerel_completed") is True
    assert state.flags.get("flag_sq_cerel_ready") is False


def test_kill_progress_is_deterministic() -> None:
    quest_service = _build_quest_service()
    state = _make_state()
    state.flags["flag_sq_cerel_offered"] = True
    quest_service.accept_quest(state, "cerel_kill_hunt")
    quest_service.record_battle_victory(state, [["goblin"], ["orc"], ["goblin"]])

    progress = state.quests_active["cerel_kill_hunt"]
    assert progress.objectives[0].current == 2
    assert progress.objectives[1].current == 1


def test_dana_shoreline_rumor_quest_flow() -> None:
    quest_service = _build_quest_service()
    state = _make_state()
    state.flags["flag_protoquest_offered"] = True

    update = quest_service.accept_quest(state, "dana_shoreline_rumor")
    assert update is not None and update.accepted is True
    assert "dana_shoreline_rumor" in state.quests_active

    quest_service.record_battle_victory(state, [["goblin"]])
    assert "dana_shoreline_rumor" in state.quests_completed
    assert state.flags.get("flag_protoquest_ready") is True

    update = quest_service.turn_in_quest(state, "dana_shoreline_rumor")
    assert update is not None and update.turned_in is True
    assert "dana_shoreline_rumor" in state.quests_turned_in
    assert state.flags.get("flag_protoquest_completed") is True
    assert state.flags.get("flag_protoquest_ready") is False


def test_dana_wolf_teeth_quest_flow() -> None:
    quest_service = _build_quest_service()
    state = _make_state()
    state.flags["flag_sq_dana_offered"] = True

    update = quest_service.accept_quest(state, "dana_wolf_teeth")
    assert update is not None and update.accepted is True
    assert "dana_wolf_teeth" in state.quests_active

    state.inventory.items["wolf_tooth"] = 3
    quest_service.refresh_collect_objectives(state)
    assert "dana_wolf_teeth" in state.quests_completed
    assert state.flags.get("flag_sq_dana_ready") is True

    update = quest_service.turn_in_quest(state, "dana_wolf_teeth")
    assert update is not None and update.turned_in is True
    assert state.inventory.items.get("wolf_tooth", 0) == 0
    assert state.flags.get("flag_sq_dana_completed") is True
    assert state.flags.get("flag_sq_dana_ready") is False
