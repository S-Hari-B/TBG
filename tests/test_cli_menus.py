from tbg.core.rng import RNG
from tbg.domain.state import GameState
from tbg.presentation.cli.app import _build_camp_menu_entries, _main_menu_options


def _camp_state() -> GameState:
    return GameState(seed=1, rng=RNG(1), mode="camp_menu", current_node_id="class_select")


def test_camp_menu_includes_save_option() -> None:
    state = _camp_state()
    entries = _build_camp_menu_entries(state)
    labels = [label for label, _ in entries]
    assert "Save Game" in labels
    assert all(label != "Load Game" for label in labels)


def test_main_menu_includes_load_but_not_save() -> None:
    options = _main_menu_options()
    labels = [label for label, _ in options]
    assert "Load Game" in labels
    assert "Save Game" not in labels
