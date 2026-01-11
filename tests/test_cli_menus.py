from tbg.core.rng import RNG
from tbg.domain.state import GameState
from tbg.presentation.cli import app
from tbg.presentation.cli.app import _build_camp_menu_entries, _main_menu_options
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


def test_camp_menu_debug_option_visible_with_flag(monkeypatch) -> None:
    monkeypatch.setenv("TBG_DEBUG", "1")
    state = _camp_state()
    entries = _build_camp_menu_entries(state)
    labels = [label for label, _ in entries]
    assert any("Location Debug" in label for label in labels)


def test_handle_story_events_recursion_receives_area_service(monkeypatch) -> None:
    state = _camp_state()
    area_service = AreaService(AreasRepository())
    area_service.initialize_state(state)

    captured: dict[str, object] = {}

    def fake_post_battle_interlude(
        message,
        story_service,
        inventory_service,
        state_arg,
        save_service,
        slot_store,
        battle_service,
        area_service_arg,
    ):
        captured["area_service"] = area_service_arg
        return [object()]

    monkeypatch.setattr(app, "_run_post_battle_interlude", fake_post_battle_interlude)
    monkeypatch.setattr(app, "_render_story_if_needed", lambda *args, **kwargs: False)
    events = [GameMenuEnteredEvent(message="Rest up")]

    result = app._handle_story_events(
        events,
        battle_service=object(),
        story_service=object(),
        inventory_service=object(),
        state=state,
        save_service=object(),
        slot_store=object(),
        area_service=area_service,
        print_header=True,
    )

    assert result is True
    assert captured["area_service"] is area_service
