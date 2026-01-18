from tbg.core.rng import RNG
from tbg.domain.state import GameState
from tbg.presentation.cli import app
from tbg.presentation.cli.app import (
    _MENU_RESELECT,
    _build_camp_menu_entries,
    _build_town_menu_entries,
    _main_menu_options,
    _play_node_with_auto_resume,
    _warp_to_checkpoint_location,
)
from tbg.services.area_service import AreaService
from tbg.data.repositories import AreasRepository
from tbg.services.story_service import GameMenuEnteredEvent


def _camp_state() -> GameState:
    return GameState(seed=1, rng=RNG(1), mode="camp_menu", current_node_id="class_select")


def test_camp_menu_includes_save_option() -> None:
    state = _camp_state()
    entries = _build_camp_menu_entries(state)
    labels = [label for label, _ in entries]
    assert "Save Game" in labels
    assert "Travel" in labels
    assert all(label != "Load Game" for label in labels)


def test_town_menu_includes_converse_and_quests() -> None:
    state = _camp_state()
    entries = _build_town_menu_entries(state)
    labels = [label for label, _ in entries]
    assert "Converse" in labels
    assert "Quests" in labels
    assert "Shops (Coming Soon)" in labels


def test_main_menu_includes_load_but_not_save() -> None:
    options = _main_menu_options()
    labels = [label for label, _ in options]
    assert "Load Game" in labels
    assert "Save Game" not in labels


def test_camp_menu_debug_option_hidden_without_flag(monkeypatch) -> None:
    monkeypatch.delenv("TBG_DEBUG", raising=False)
    state = _camp_state()
    entries = _build_camp_menu_entries(state)
    labels = [label for label, _ in entries]
    assert all("Location Debug" not in label for label in labels)


def test_town_menu_debug_option_hidden_without_flag(monkeypatch) -> None:
    monkeypatch.delenv("TBG_DEBUG", raising=False)
    state = _camp_state()
    entries = _build_town_menu_entries(state)
    labels = [label for label, _ in entries]
    assert all("Location Debug" not in label for label in labels)


def test_camp_menu_debug_option_visible_with_flag(monkeypatch) -> None:
    monkeypatch.setenv("TBG_DEBUG", "1")
    state = _camp_state()
    entries = _build_camp_menu_entries(state)
    labels = [label for label, _ in entries]
    assert any("Location Debug" in label for label in labels)


def test_town_menu_debug_option_visible_with_flag(monkeypatch) -> None:
    monkeypatch.setenv("TBG_DEBUG", "1")
    state = _camp_state()
    entries = _build_town_menu_entries(state)
    labels = [label for label, _ in entries]
    assert any("Location Debug" in label for label in labels)


def test_interlude_reselects_menu_after_travel(monkeypatch) -> None:
    state = _camp_state()

    class _StubAreaService:
        def __init__(self):
            self._calls = 0

        def get_current_location_view(self, _state):
            self._calls += 1
            tags = ("town",) if self._calls == 1 else ("plains",)
            return type("LocationViewStub", (), {"tags": tags})()

    area_service = _StubAreaService()

    def fake_town_menu(*args, **kwargs):
        return _MENU_RESELECT

    def fake_camp_menu(*args, **kwargs):
        return []

    monkeypatch.setattr(app, "_run_town_menu", fake_town_menu)
    monkeypatch.setattr(app, "_run_camp_menu", fake_camp_menu)

    follow_up = app._run_post_battle_interlude(
        message="",
        story_service=object(),
        inventory_service=object(),
        quest_service=object(),
        state=state,
        save_service=object(),
        slot_store=object(),
        battle_service=object(),
        area_service=area_service,
    )

    assert follow_up == []


def test_handle_story_events_recursion_receives_area_service(monkeypatch) -> None:
    state = _camp_state()
    area_service = AreaService(AreasRepository())
    area_service.initialize_state(state)
    quest_service = object()

    captured: dict[str, object] = {}

    def fake_post_battle_interlude(
        message,
        story_service,
        inventory_service,
        quest_service_arg,
        state_arg,
        save_service,
        slot_store,
        battle_service,
        area_service_arg,
    ):
        captured["area_service"] = area_service_arg
        captured["quest_service"] = quest_service_arg
        return [object()]

    monkeypatch.setattr(app, "_run_post_battle_interlude", fake_post_battle_interlude)
    monkeypatch.setattr(app, "_render_story_if_needed", lambda *args, **kwargs: False)
    events = [GameMenuEnteredEvent(message="Rest up")]

    result = app._handle_story_events(
        events,
        battle_service=object(),
        story_service=object(),
        inventory_service=object(),
        quest_service=quest_service,
        state=state,
        save_service=object(),
        slot_store=object(),
        area_service=area_service,
        print_header=True,
    )

    assert result is True
    assert captured["area_service"] is area_service
    assert captured["quest_service"] is quest_service


def test_warp_to_checkpoint_location_emits_message(monkeypatch, capsys) -> None:
    monkeypatch.setenv("TBG_DEBUG", "1")
    area_service = AreaService(AreasRepository())
    state = _camp_state()
    area_service.initialize_state(state)
    area_service.force_set_location(state, "village")
    state.story_checkpoint_location_id = "village_outskirts"

    did_warp = _warp_to_checkpoint_location(area_service, state)

    assert did_warp is True
    assert state.current_location_id == "village_outskirts"
    out = capsys.readouterr().out
    assert "checkpoint rewind" in out
    assert "DEBUG: checkpoint warp from=village to=village_outskirts" in out


def test_warp_to_checkpoint_skips_when_already_at_location(capsys) -> None:
    area_service = AreaService(AreasRepository())
    state = _camp_state()
    area_service.initialize_state(state)
    state.story_checkpoint_location_id = state.current_location_id

    assert _warp_to_checkpoint_location(area_service, state) is False
    assert capsys.readouterr().out == ""


def test_converse_auto_resume_does_not_end_demo() -> None:
    from tbg.data.repositories import (
        ArmourRepository,
        ClassesRepository,
        PartyMembersRepository,
        StoryRepository,
        WeaponsRepository,
    )
    from tbg.services.inventory_service import InventoryService
    from tbg.services.story_service import StoryService

    weapons_repo = WeaponsRepository()
    armour_repo = ArmourRepository()
    party_repo = PartyMembersRepository()
    inventory_service = InventoryService(
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        party_members_repo=party_repo,
    )
    story_service = StoryService(
        story_repo=StoryRepository(),
        classes_repo=ClassesRepository(weapons_repo=weapons_repo, armour_repo=armour_repo),
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        party_members_repo=party_repo,
        inventory_service=inventory_service,
        quest_service=None,
    )
    state = story_service.start_new_game(seed=12, player_name="Hero")
    story_service.play_node(state, "threshold_inn_hub_router")
    follow_up = _play_node_with_auto_resume(story_service, state, "dana_turn_in_check")
    assert follow_up is not None
    assert story_service.get_current_node_view(state).choices


def test_filter_turn_ins_by_location_npcs() -> None:
    from tbg.presentation.cli.app import _filter_turn_ins_for_location
    from tbg.services.quest_service import QuestTurnInView

    location_view = type(
        "LocationViewStub",
        (),
        {"npcs_present": [type("Npc", (), {"npc_id": "dana"})()]},
    )()
    turn_ins = [
        QuestTurnInView(quest_id="q1", name="Dana Quest", npc_id="dana", node_id="node1"),
        QuestTurnInView(quest_id="q2", name="Cerel Quest", npc_id="cerel", node_id="node2"),
        QuestTurnInView(quest_id="q3", name="Unknown", npc_id=None, node_id="node3"),
    ]
    filtered = _filter_turn_ins_for_location(turn_ins, location_view)
    assert [entry.quest_id for entry in filtered] == ["q1"]


def test_turn_in_check_nodes_do_not_end_demo(monkeypatch, capsys) -> None:
    (
        story_service,
        battle_service,
        inventory_service,
        save_service,
        area_service,
        quest_service,
    ) = app._build_services()
    for node_id in ("dana_turn_in_check", "dana_protoquest_turn_in_check", "cerel_turn_in_check"):
        state = story_service.start_new_game(seed=101, player_name="Hero")
        area_service.initialize_state(state)
        story_service.play_node(state, node_id)

        called = {"prompted": False}

        def fake_prompt(_count: int) -> int:
            called["prompted"] = True
            raise RuntimeError("stop")

        monkeypatch.setattr(app, "_prompt_choice", fake_prompt)
        monkeypatch.setattr(app, "_render_node_view", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(app, "_run_post_battle_interlude", lambda *args, **kwargs: None)
        try:
            result = app._run_story_loop(
                story_service,
                battle_service,
                inventory_service,
                quest_service,
                state,
                save_service,
                app.SaveSlotStore(),
                area_service,
                from_load=False,
            )
        except RuntimeError:
            result = None

        out = capsys.readouterr().out
        assert "End of demo slice" not in out
        assert result in (None, False)
