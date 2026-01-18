from tbg.services.battle_service import AttackResolvedEvent, BattleCombatantView
from tbg.presentation.cli.app import _format_enemy_hp_display, _render_battle_events
from tbg.presentation.cli.render import render_story


def test_format_enemy_hp_display_no_debug() -> None:
    enemy_view = BattleCombatantView(
        instance_id="enemy_1",
        name="Goblin",
        hp_display="???",
        side="enemies",
        is_alive=True,
        current_hp=10,
        max_hp=20,
        defense=2,
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
        defense=2,
    )
    assert _format_enemy_hp_display(enemy_view, debug_enabled=True) == "???[10/20|D2]"


def test_format_enemy_hp_display_dead() -> None:
    enemy_view = BattleCombatantView(
        instance_id="enemy_1",
        name="Goblin",
        hp_display="???",
        side="enemies",
        is_alive=False,
        current_hp=0,
        max_hp=20,
        defense=2,
    )
    assert _format_enemy_hp_display(enemy_view, debug_enabled=True) == "DOWN"


def test_render_battle_events_hides_hp_reference(capsys) -> None:
    event = AttackResolvedEvent(
        attacker_id="hero",
        attacker_name="Hero",
        target_id="enemy_1",
        target_name="Goblin Grunt (1)",
        damage=5,
        target_hp=12,
    )
    _render_battle_events([event])
    captured = capsys.readouterr()
    assert "HP now" not in captured.out


def test_render_story_hides_node_ids_without_debug(monkeypatch, capsys) -> None:
    monkeypatch.delenv("TBG_DEBUG", raising=False)
    render_story([("intro_decree", "The decree arrives.")])
    out = capsys.readouterr().out
    assert "[intro_decree]" not in out
    assert "The decree arrives." in out


def test_render_story_shows_node_ids_with_debug(monkeypatch, capsys) -> None:
    monkeypatch.setenv("TBG_DEBUG", "1")
    render_story([("intro_decree", "The decree arrives.")])
    out = capsys.readouterr().out
    assert "[intro_decree]" in out


def test_render_story_suppresses_blank_blocks(capsys) -> None:
    render_story([("router_node", "   ")])
    out = capsys.readouterr().out
    assert "=== Story ===" not in out

