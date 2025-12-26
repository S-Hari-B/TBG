from tbg.services.battle_service import BattleCombatantView
from tbg.presentation.cli.app import _format_enemy_hp_display


def test_format_enemy_hp_display_no_debug() -> None:
    enemy_view = BattleCombatantView(
        instance_id="enemy_1",
        name="Goblin",
        hp_display="???",
        side="enemies",
        is_alive=True,
        current_hp=10,
        max_hp=20,
    )
    assert _format_enemy_hp_display(enemy_view, debug_enabled=False) == "???"


def test_format_enemy_hp_display_debug_enabled() -> None:
    enemy_view = BattleCombatantView(
        instance_id="enemy_1",
        name="Goblin",
        hp_display="???",
        side="enemies",
        is_alive=True,
        current_hp=10,
        max_hp=20,
    )
    assert _format_enemy_hp_display(enemy_view, debug_enabled=True) == "??? (DEBUG 10/20)"


def test_format_enemy_hp_display_dead() -> None:
    enemy_view = BattleCombatantView(
        instance_id="enemy_1",
        name="Goblin",
        hp_display="???",
        side="enemies",
        is_alive=False,
        current_hp=0,
        max_hp=20,
    )
    assert _format_enemy_hp_display(enemy_view, debug_enabled=True) == "DOWN"

