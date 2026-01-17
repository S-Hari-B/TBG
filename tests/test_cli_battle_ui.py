from __future__ import annotations

from typing import Iterator, List, Tuple

from tbg.core.rng import RNG
from tbg.domain.battle_models import BattleState, Combatant
from tbg.domain.entities.player import Player
from tbg.domain.entities.stats import Stats
from tbg.domain.state import GameState
from tbg.presentation.cli import app
from tbg.services.battle_service import (
    AttackResolvedEvent,
    BattleCombatantView,
    BattleResolvedEvent,
    BattleView,
    CombatantDefeatedEvent,
)


class _FakeBattleService:
    """Deterministic battle stub for CLI rendering tests."""

    def __init__(self, *, player_damage: int = 6, enemy_damage: int = 3) -> None:
        self._player_damage = player_damage
        self._enemy_damage = enemy_damage

    def get_battle_view(self, battle_state: BattleState) -> BattleView:
        allies = [
            BattleCombatantView(
                instance_id=ally.instance_id,
                name=ally.display_name,
                hp_display=f"{ally.stats.hp}/{ally.stats.max_hp}",
                side="allies",
                is_alive=ally.is_alive,
                current_hp=ally.stats.hp,
                max_hp=ally.stats.max_hp,
            )
            for ally in battle_state.allies
        ]
        enemies = [
            BattleCombatantView(
                instance_id=enemy.instance_id,
                name=enemy.display_name,
                hp_display="???" if enemy.is_alive else "DOWN",
                side="enemies",
                is_alive=enemy.is_alive,
                current_hp=enemy.stats.hp,
                max_hp=enemy.stats.max_hp,
            )
            for enemy in battle_state.enemies
        ]
        return BattleView(
            battle_id=battle_state.battle_id,
            allies=allies,
            enemies=enemies,
            current_actor_id=battle_state.current_actor_id,
        )

    def get_available_skills(self, battle_state: BattleState, actor_id: str) -> List:
        del battle_state, actor_id
        return []

    def basic_attack(self, battle_state: BattleState, attacker_id: str, target_id: str):
        del attacker_id, target_id
        enemy = battle_state.enemies[0]
        damage = self._player_damage
        enemy.stats.hp = max(0, enemy.stats.hp - damage)
        events = [
            AttackResolvedEvent(
                attacker_id=battle_state.allies[0].instance_id,
                attacker_name=battle_state.allies[0].display_name,
                target_id=enemy.instance_id,
                target_name=enemy.display_name,
                damage=damage,
                target_hp=enemy.stats.hp,
            )
        ]
        if enemy.stats.hp == 0:
            events.append(CombatantDefeatedEvent(combatant_id=enemy.instance_id, combatant_name=enemy.display_name))
            events.append(BattleResolvedEvent(victor="allies"))
            battle_state.is_over = True
            battle_state.victor = "allies"
            battle_state.current_actor_id = None
        else:
            battle_state.current_actor_id = enemy.instance_id
        return events

    def run_enemy_turn(self, battle_state: BattleState, rng) -> List[AttackResolvedEvent]:
        del rng
        hero = battle_state.allies[0]
        enemy = battle_state.enemies[0]
        damage = self._enemy_damage
        hero.stats.hp = max(0, hero.stats.hp - damage)
        events = [
            AttackResolvedEvent(
                attacker_id=enemy.instance_id,
                attacker_name=enemy.display_name,
                target_id=hero.instance_id,
                target_name=hero.display_name,
                damage=damage,
                target_hp=hero.stats.hp,
            ),
            BattleResolvedEvent(victor="enemies"),
        ]
        battle_state.is_over = True
        battle_state.victor = "enemies"
        battle_state.current_actor_id = None
        return events

    def run_ally_ai_turn(self, battle_state: BattleState, actor_id: str, rng):
        del battle_state, actor_id, rng
        return []

    def party_talk(self, battle_state: BattleState, speaker_id: str, rng):
        del battle_state, speaker_id, rng
        return []

    def apply_victory_rewards(self, battle_state: BattleState, state: GameState):
        del battle_state, state
        return []


def _build_state_and_battle(enemy_hp: int) -> Tuple[GameState, BattleState]:
    rng = RNG(1)
    player_stats = Stats(max_hp=40, hp=40, max_mp=5, mp=5, attack=6, defense=2, speed=10)
    player = Player(id="hero", name="Hero", class_id="warrior", stats=player_stats)
    state = GameState(seed=1, rng=rng, mode="battle", current_node_id="tutorial", player=player)
    state.party_members = []
    enemy_stats = Stats(max_hp=enemy_hp, hp=enemy_hp, max_mp=0, mp=0, attack=4, defense=1, speed=5)
    hero_combatant = Combatant(
        instance_id=player.id,
        display_name=player.name,
        side="allies",
        stats=player_stats,
    )
    enemy_combatant = Combatant(
        instance_id="enemy_1",
        display_name="Goblin Grunt (1)",
        side="enemies",
        stats=enemy_stats,
    )
    battle_state = BattleState(
        battle_id="battle_test",
        allies=[hero_combatant],
        enemies=[enemy_combatant],
        current_actor_id=player.id,
        player_id=player.id,
    )
    return state, battle_state


def _set_inputs(monkeypatch, values: List[str]) -> None:
    iterator: Iterator[str] = iter(values)
    monkeypatch.setattr("builtins.input", lambda *_args, **_kwargs: next(iterator))


def test_state_panel_printed_once_per_player_turn(monkeypatch, capsys) -> None:
    state, battle_state = _build_state_and_battle(enemy_hp=6)
    service = _FakeBattleService()
    _set_inputs(monkeypatch, ["x", "1", "1"])

    assert app._run_battle_loop(service, battle_state, state) is True
    out = capsys.readouterr().out
    assert out.count("| ALLIES") == 1


def test_results_panel_once_per_actor_turn(monkeypatch, capsys) -> None:
    state, battle_state = _build_state_and_battle(enemy_hp=10)
    service = _FakeBattleService()
    _set_inputs(monkeypatch, ["1", "1"])

    assert app._run_battle_loop(service, battle_state, state) is False
    out = capsys.readouterr().out
    assert out.count("| RESULTS") == 2
    assert out.count("| ACTIONS") == 1


def _build_panel_view() -> Tuple[BattleView, BattleState]:
    hero_stats = Stats(max_hp=30, hp=20, max_mp=5, mp=3, attack=4, defense=1, speed=8)
    ally_stats = Stats(max_hp=26, hp=12, max_mp=6, mp=2, attack=3, defense=1, speed=6)
    enemy_a_stats = Stats(max_hp=15, hp=15, max_mp=0, mp=0, attack=2, defense=1, speed=4)
    enemy_b_stats = Stats(max_hp=15, hp=0, max_mp=0, mp=0, attack=2, defense=1, speed=4)

    battle_state = BattleState(
        battle_id="panel",
        allies=[
            Combatant(instance_id="hero", display_name="Hero", side="allies", stats=hero_stats),
            Combatant(instance_id="ally_emma", display_name="Emma", side="allies", stats=ally_stats),
        ],
        enemies=[
            Combatant(instance_id="enemy_1", display_name="Goblin Grunt (1)", side="enemies", stats=enemy_a_stats),
            Combatant(instance_id="enemy_2", display_name="Goblin Grunt (2)", side="enemies", stats=enemy_b_stats),
        ],
        current_actor_id="hero",
        player_id="hero",
    )
    view = BattleView(
        battle_id="panel",
        allies=[
            BattleCombatantView(
                instance_id="hero",
                name="Hero",
                hp_display="20/30",
                side="allies",
                is_alive=True,
                current_hp=20,
                max_hp=30,
            ),
            BattleCombatantView(
                instance_id="ally_emma",
                name="Emma",
                hp_display="12/26",
                side="allies",
                is_alive=True,
                current_hp=12,
                max_hp=26,
            ),
        ],
        enemies=[
            BattleCombatantView(
                instance_id="enemy_1",
                name="Goblin Grunt (1)",
                hp_display="???",
                side="enemies",
                is_alive=True,
                current_hp=15,
                max_hp=15,
            ),
            BattleCombatantView(
                instance_id="enemy_2",
                name="Goblin Grunt (2)",
                hp_display="???",
                side="enemies",
                is_alive=False,
                current_hp=0,
                max_hp=15,
            ),
        ],
        current_actor_id="hero",
    )
    return view, battle_state


def test_enemy_numbering_and_down_status(capsys) -> None:
    view, battle_state = _build_panel_view()
    app._render_battle_state_panel(view, battle_state, active_id="hero")
    out = capsys.readouterr().out
    assert "Goblin Grunt (1)" in out
    assert "Goblin Grunt (2)" in out
    assert "DOWN" in out


def test_state_panel_hides_enemy_hp_without_debug(monkeypatch, capsys) -> None:
    view, battle_state = _build_panel_view()
    monkeypatch.delenv("TBG_DEBUG", raising=False)
    app._render_battle_state_panel(view, battle_state, active_id="hero")
    out = capsys.readouterr().out
    assert "[15/15]" not in out


def test_state_panel_hides_enemy_hp_when_debug_zero(monkeypatch, capsys) -> None:
    view, battle_state = _build_panel_view()
    monkeypatch.setenv("TBG_DEBUG", "0")
    app._render_battle_state_panel(view, battle_state, active_id="hero")
    out = capsys.readouterr().out
    assert "[15/15]" not in out


def test_state_panel_shows_enemy_hp_with_debug(monkeypatch, capsys) -> None:
    view, battle_state = _build_panel_view()
    monkeypatch.setenv("TBG_DEBUG", "1")
    assert app._debug_enabled() is True
    app._render_battle_state_panel(view, battle_state, active_id="hero")
    out = capsys.readouterr().out
    assert "[15/15]" in out


def _extract_state_panel_block(output: str) -> List[str]:
    lines = output.splitlines()
    border_indexes = [
        idx for idx, line in enumerate(lines) if line.startswith("+") and line.endswith("+") and line.count("+") >= 3
    ]
    if len(border_indexes) < 2:
        return []
    start = border_indexes[0]
    end = border_indexes[-1]
    return lines[start : end + 1]


def test_state_panel_lines_match_frame_width(capsys) -> None:
    view, battle_state = _build_panel_view()
    app._render_battle_state_panel(view, battle_state, active_id="hero")
    out = capsys.readouterr().out
    block = _extract_state_panel_block(out)
    assert block, "Failed to capture battle state panel output."
    expected_width = app._BATTLE_UI_WIDTH
    assert all(len(line) == expected_width for line in block)
    assert all(line.endswith(("+", "|")) for line in block)
