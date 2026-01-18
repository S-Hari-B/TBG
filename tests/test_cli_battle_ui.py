from __future__ import annotations

from typing import Iterator, List, Tuple

from tbg.core.rng import RNG
from tbg.domain.battle_models import BattleState, Combatant
from tbg.domain.entities.player import Player
from tbg.domain.defs import SkillDef
from tbg.domain.entities.stats import Stats
from tbg.domain.state import GameState
from tbg.presentation.cli import app
from tbg.services.battle_service import (
    AttackResolvedEvent,
    BattleCombatantView,
    BattleExpRewardEvent,
    BattleGoldRewardEvent,
    BattleLevelUpEvent,
    BattleRewardsHeaderEvent,
    BattleResolvedEvent,
    BattleView,
    CombatantDefeatedEvent,
    LootAcquiredEvent,
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
                defense=ally.stats.defense,
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
                defense=enemy.stats.defense,
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

    def estimate_damage_for_ids(self, battle_state, attacker_id, target_id, *, bonus_power=0, minimum=1) -> int:
        del battle_state, attacker_id, target_id, bonus_power, minimum
        return self._player_damage

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

    def party_has_knowledge(self, state: GameState, enemy_tags: tuple[str, ...]) -> bool:
        del state, enemy_tags
        return False  # Default: no knowledge for tests


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


def test_battle_id_header_hidden_without_debug(monkeypatch, capsys) -> None:
    monkeypatch.setenv("TBG_DEBUG", "0")
    state, battle_state = _build_state_and_battle(enemy_hp=6)
    battle_state.battle_id = "battle_test"
    service = _FakeBattleService()
    _set_inputs(monkeypatch, ["1", "1"])

    assert app._run_battle_loop(service, battle_state, state) is True
    out = capsys.readouterr().out
    assert "=== Battle battle_test ===" not in out


def test_battle_id_header_visible_with_debug(monkeypatch, capsys) -> None:
    monkeypatch.setenv("TBG_DEBUG", "1")
    state, battle_state = _build_state_and_battle(enemy_hp=6)
    battle_state.battle_id = "battle_test"
    service = _FakeBattleService()
    _set_inputs(monkeypatch, ["1", "1"])

    assert app._run_battle_loop(service, battle_state, state) is True
    out = capsys.readouterr().out
    assert "=== Battle battle_test ===" in out


def test_turn_header_not_duplicated_on_invalid_input(monkeypatch, capsys) -> None:
    """Verify that turn header and state panel don't reprint when invalid action is entered."""
    state, battle_state = _build_state_and_battle(enemy_hp=6)
    service = _FakeBattleService()
    _set_inputs(monkeypatch, ["x", "y", "1", "1"])

    assert app._run_battle_loop(service, battle_state, state) is True
    out = capsys.readouterr().out
    # Only one state panel despite two invalid inputs
    assert out.count("| ALLIES") == 1
    # Only one turn header for the player
    assert out.count("| TURN") == 1
    # Action menu appears multiple times due to retries
    assert out.count("| ACTIONS") >= 2


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

    enemy_one = Combatant(
        instance_id="enemy_1",
        display_name="Goblin Grunt (1)",
        side="enemies",
        stats=enemy_a_stats,
    )
    enemy_two = Combatant(
        instance_id="enemy_2",
        display_name="Goblin Grunt (2)",
        side="enemies",
        stats=enemy_b_stats,
    )
    battle_state = BattleState(
        battle_id="panel",
        allies=[
            Combatant(instance_id="hero", display_name="Hero", side="allies", stats=hero_stats),
            Combatant(instance_id="ally_emma", display_name="Emma", side="allies", stats=ally_stats),
        ],
        enemies=[enemy_one, enemy_two],
        current_actor_id="hero",
        player_id="hero",
    )
    battle_state.turn_queue = ["hero", "ally_emma", "enemy_1", "enemy_2"]
    enemy_view_one = BattleCombatantView(
        instance_id="enemy_1",
        name="Goblin Grunt (1)",
        hp_display="???",
        side="enemies",
        is_alive=True,
        current_hp=15,
        max_hp=15,
        defense=1,
    )
    enemy_view_two = BattleCombatantView(
        instance_id="enemy_2",
        name="Goblin Grunt (2)",
        hp_display="???",
        side="enemies",
        is_alive=False,
        current_hp=0,
        max_hp=15,
        defense=1,
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
                defense=1,
            ),
            BattleCombatantView(
                instance_id="ally_emma",
                name="Emma",
                hp_display="12/26",
                side="allies",
                is_alive=True,
                current_hp=12,
                max_hp=26,
                defense=1,
            ),
        ],
        enemies=[enemy_view_one, enemy_view_two],
        current_actor_id="hero",
    )
    return view, battle_state


def test_enemy_numbering_and_down_status(monkeypatch, capsys) -> None:
    view, battle_state = _build_panel_view()
    monkeypatch.setenv("TBG_DEBUG", "0")
    assert view.enemies[0] is not view.enemies[1]
    assert battle_state.enemies[0] is not battle_state.enemies[1]
    app._render_battle_state_panel(view, battle_state, active_id="hero")
    out = capsys.readouterr().out
    assert "Goblin Grunt (1)" in out
    assert "Goblin Grunt (2)" in out
    assert "DOWN" in out


def test_enemy_numbering_and_down_status_debug(monkeypatch, capsys) -> None:
    view, battle_state = _build_panel_view()
    monkeypatch.setenv("TBG_DEBUG", "1")
    assert view.enemies[0] is not view.enemies[1]
    assert battle_state.enemies[0] is not battle_state.enemies[1]
    app._render_battle_state_panel(view, battle_state, active_id="hero")
    out = capsys.readouterr().out
    # First enemy name is truncated due to debug HP info, but (1) numbering should be visible
    assert "(1)" in out
    # Second enemy is DOWN so has room for full name
    assert "Goblin Grunt (2)" in out
    assert "DOWN" in out


def test_state_panel_hides_enemy_hp_without_debug(monkeypatch, capsys) -> None:
    view, battle_state = _build_panel_view()
    monkeypatch.delenv("TBG_DEBUG", raising=False)
    app._render_battle_state_panel(view, battle_state, active_id="hero")
    out = capsys.readouterr().out
    assert "[15/15]" not in out
    assert ">  1" not in out


def test_state_panel_hides_enemy_hp_when_debug_zero(monkeypatch, capsys) -> None:
    view, battle_state = _build_panel_view()
    monkeypatch.setenv("TBG_DEBUG", "0")
    app._render_battle_state_panel(view, battle_state, active_id="hero")
    out = capsys.readouterr().out
    assert "[15/15]" not in out
    assert ">  1" not in out


def test_state_panel_shows_enemy_hp_with_debug(monkeypatch, capsys) -> None:
    view, battle_state = _build_panel_view()
    monkeypatch.setenv("TBG_DEBUG", "1")
    assert app._debug_enabled() is True
    app._render_battle_state_panel(view, battle_state, active_id="hero")
    out = capsys.readouterr().out
    # Debug mode now shows [15/15|D1] format including defense
    assert "[15/15|D1]" in out
    assert ">  1" in out
    assert "  2 Emma" in out
    assert "  3" in out


def _build_preview_state() -> BattleState:
    hero_stats = Stats(max_hp=30, hp=30, max_mp=5, mp=5, attack=6, defense=1, speed=8)
    enemy_stats = Stats(max_hp=12, hp=12, max_mp=0, mp=0, attack=3, defense=2, speed=4)
    hero = Combatant(instance_id="hero", display_name="Hero", side="allies", stats=hero_stats)
    enemy = Combatant(
        instance_id="enemy_1", display_name="Goblin Grunt (1)", side="enemies", stats=enemy_stats
    )
    return BattleState(
        battle_id="preview",
        allies=[hero],
        enemies=[enemy],
        current_actor_id="hero",
        player_id="hero",
    )


def test_basic_attack_preview_in_target_panel(monkeypatch, capsys) -> None:
    battle_state = _build_preview_state()
    monkeypatch.setenv("TBG_DEBUG", "1")
    _set_inputs(monkeypatch, ["1"])
    estimator = lambda enemy: 6
    target = app._prompt_battle_target(battle_state, damage_estimator=estimator)
    out = capsys.readouterr().out
    assert target.instance_id == "enemy_1"
    assert "Projected: 6" in out


def test_basic_attack_preview_non_debug_no_knowledge(monkeypatch, capsys) -> None:
    """Non-debug mode without knowledge should not show projected damage."""
    battle_state = _build_preview_state()
    monkeypatch.delenv("TBG_DEBUG", raising=False)
    _set_inputs(monkeypatch, ["1"])
    estimator = lambda enemy: 6
    # No state/controller means no knowledge check
    _ = app._prompt_battle_target(battle_state, damage_estimator=estimator, state=None, controller=None)
    out = capsys.readouterr().out
    assert "Baseline damage" not in out  # Old behavior removed
    assert "Projected:" not in out  # Should not leak defense-based projection
    # For basic attacks without knowledge, we just don't show preview at all


def test_skill_target_preview_in_target_panel(monkeypatch, capsys) -> None:
    battle_state = _build_preview_state()
    monkeypatch.setenv("TBG_DEBUG", "1")
    _set_inputs(monkeypatch, ["1"])
    skill = SkillDef(
        id="power_slash",
        name="Power Slash",
        description="",
        tags=(),
        required_weapon_tags=(),
        target_mode="single_enemy",
        max_targets=1,
        mp_cost=3,
        base_power=2,
        effect_type="damage",
        gold_value=0,
    )
    estimator = lambda enemy: 8
    target_ids = app._prompt_skill_targets(skill, battle_state, damage_estimator=estimator)
    out = capsys.readouterr().out
    assert target_ids == ["enemy_1"]
    assert "Projected: 8" in out


def test_skill_target_preview_non_debug_no_knowledge(monkeypatch, capsys) -> None:
    """Non-debug without knowledge should not show projected in target list."""
    battle_state = _build_preview_state()
    monkeypatch.delenv("TBG_DEBUG", raising=False)
    _set_inputs(monkeypatch, ["1"])
    skill = SkillDef(
        id="power_slash",
        name="Power Slash",
        description="",
        tags=(),
        required_weapon_tags=(),
        target_mode="single_enemy",
        max_targets=1,
        mp_cost=3,
        base_power=2,
        effect_type="damage",
        gold_value=0,
    )
    estimator = lambda enemy: 8
    _ = app._prompt_skill_targets(skill, battle_state, damage_estimator=estimator, state=None, controller=None)
    out = capsys.readouterr().out
    assert "Baseline damage" not in out
    assert "Projected:" not in out  # Should not leak projection without knowledge


def test_skill_list_preview_for_multi_target_when_uniform(monkeypatch, capsys) -> None:
    hero_stats = Stats(max_hp=30, hp=30, max_mp=5, mp=5, attack=6, defense=1, speed=8)
    enemy_stats = Stats(max_hp=12, hp=12, max_mp=0, mp=0, attack=3, defense=2, speed=4)
    battle_state = BattleState(
        battle_id="preview",
        allies=[Combatant(instance_id="hero", display_name="Hero", side="allies", stats=hero_stats)],
        enemies=[
            Combatant(instance_id="enemy_1", display_name="Goblin Grunt (1)", side="enemies", stats=enemy_stats),
            Combatant(instance_id="enemy_2", display_name="Goblin Grunt (2)", side="enemies", stats=enemy_stats),
        ],
        current_actor_id="hero",
        player_id="hero",
    )

    class _PreviewController:
        def estimate_damage(self, *_args, **_kwargs) -> int:
            return 5

    skill = SkillDef(
        id="ember_wave",
        name="Ember Wave",
        description="",
        tags=(),
        required_weapon_tags=(),
        target_mode="multi_enemy",
        max_targets=2,
        mp_cost=4,
        base_power=2,
        effect_type="damage",
        gold_value=0,
    )
    monkeypatch.setenv("TBG_DEBUG", "1")
    _set_inputs(monkeypatch, ["1"])
    from tbg.domain.state import GameState
    from tbg.core.rng import RNG
    state = GameState(seed=1, rng=RNG(1), mode="play", current_node_id="test")
    _ = app._prompt_skill_choice([skill], battle_state, _PreviewController(), "hero", state)
    out = capsys.readouterr().out
    assert "Projected: 5" in out
    assert "each" in out


def test_skill_descriptions_render_under_skill(monkeypatch, capsys) -> None:
    hero_stats = Stats(max_hp=30, hp=30, max_mp=5, mp=5, attack=6, defense=1, speed=8)
    enemy_stats = Stats(max_hp=12, hp=12, max_mp=0, mp=0, attack=3, defense=2, speed=4)
    battle_state = BattleState(
        battle_id="preview",
        allies=[Combatant(instance_id="hero", display_name="Hero", side="allies", stats=hero_stats)],
        enemies=[Combatant(instance_id="enemy_1", display_name="Goblin Grunt (1)", side="enemies", stats=enemy_stats)],
        current_actor_id="hero",
        player_id="hero",
    )

    class _PreviewController:
        def estimate_damage(self, *_args, **_kwargs) -> int:
            return 5

        def has_knowledge_of_enemy(self, state, tags) -> bool:
            return False

    skill = SkillDef(
        id="power_slash",
        name="Power Slash",
        description="A heavy downward strike that trades speed for force.",
        tags=(),
        required_weapon_tags=(),
        target_mode="single_enemy",
        max_targets=1,
        mp_cost=3,
        base_power=4,
        effect_type="damage",
        gold_value=0,
    )
    from tbg.domain.state import GameState
    from tbg.core.rng import RNG

    state = GameState(seed=1, rng=RNG(1), mode="play", current_node_id="test")
    monkeypatch.delenv("TBG_DEBUG", raising=False)
    _set_inputs(monkeypatch, ["1"])
    _ = app._prompt_skill_choice([skill], battle_state, _PreviewController(), "hero", state)
    out = capsys.readouterr().out
    assert "A heavy downward strike" in out
    assert out.count("downward strike") == 1


def test_skill_list_preview_non_debug_no_knowledge_shows_power(monkeypatch, capsys) -> None:
    """Non-debug without knowledge should show Power: base_power in skill list."""
    hero_stats = Stats(max_hp=30, hp=30, max_mp=5, mp=5, attack=6, defense=1, speed=8)
    enemy_stats = Stats(max_hp=12, hp=12, max_mp=0, mp=0, attack=3, defense=2, speed=4)
    battle_state = BattleState(
        battle_id="preview",
        allies=[Combatant(instance_id="hero", display_name="Hero", side="allies", stats=hero_stats)],
        enemies=[
            Combatant(instance_id="enemy_1", display_name="Goblin Grunt (1)", side="enemies", stats=enemy_stats, tags=("goblin",)),
            Combatant(instance_id="enemy_2", display_name="Goblin Grunt (2)", side="enemies", stats=enemy_stats, tags=("goblin",)),
        ],
        current_actor_id="hero",
        player_id="hero",
    )

    class _PreviewController:
        def estimate_damage(self, *_args, **_kwargs) -> int:
            return 5
        
        def has_knowledge_of_enemy(self, state, tags) -> bool:
            return False  # No knowledge

    skill = SkillDef(
        id="ember_wave",
        name="Ember Wave",
        description="",
        tags=(),
        required_weapon_tags=(),
        target_mode="multi_enemy",
        max_targets=2,
        mp_cost=4,
        base_power=2,
        effect_type="damage",
        gold_value=0,
    )
    from tbg.domain.state import GameState
    from tbg.core.rng import RNG
    state = GameState(seed=1, rng=RNG(1), mode="play", current_node_id="test")
    monkeypatch.delenv("TBG_DEBUG", raising=False)
    _set_inputs(monkeypatch, ["1"])
    _ = app._prompt_skill_choice([skill], battle_state, _PreviewController(), "hero", state)
    out = capsys.readouterr().out
    assert "Power: 2" in out  # Should show base power, not projected
    assert "Projected:" not in out


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


def test_rewards_render_in_boxed_panels(capsys) -> None:
    events = [
        BattleRewardsHeaderEvent(),
        BattleGoldRewardEvent(amount=5, total_gold=10),
        BattleExpRewardEvent(member_id="hero", member_name="Hero", amount=8, new_level=2),
        BattleLevelUpEvent(member_id="hero", member_name="Hero", new_level=2),
        LootAcquiredEvent(item_id="goblin_horn", item_name="Goblin Horn", quantity=1),
        LootAcquiredEvent(item_id="goblin_horn", item_name="Goblin Horn", quantity=2),
    ]
    app._render_battle_events(events)
    out = capsys.readouterr().out
    assert "| REWARDS" in out
    assert "| LEVEL UPS" in out
    assert "| LOOT" in out
    assert "Loot: Goblin Horn x3" in out


def test_loot_lines_aggregate() -> None:
    from tbg.services.battle_service import LootAcquiredEvent
    from tbg.presentation.cli.app import _format_battle_event_lines

    events = [
        LootAcquiredEvent(item_id="goblin_horn", item_name="Goblin Horn", quantity=1),
        LootAcquiredEvent(item_id="goblin_horn", item_name="Goblin Horn", quantity=2),
    ]
    lines = _format_battle_event_lines(events)
    assert lines == ["- Loot: Goblin Horn x3"]


def test_skill_preview_with_knowledge_shows_projected(monkeypatch, capsys) -> None:
    """Non-debug mode WITH knowledge should show projected damage."""
    hero_stats = Stats(max_hp=30, hp=30, max_mp=5, mp=5, attack=6, defense=1, speed=8)
    enemy_stats = Stats(max_hp=12, hp=12, max_mp=0, mp=0, attack=3, defense=2, speed=4)
    battle_state = BattleState(
        battle_id="preview",
        allies=[Combatant(instance_id="hero", display_name="Hero", side="allies", stats=hero_stats)],
        enemies=[
            Combatant(instance_id="enemy_1", display_name="Goblin Grunt (1)", side="enemies", stats=enemy_stats, tags=("goblin",)),
        ],
        current_actor_id="hero",
        player_id="hero",
    )

    class _KnowledgeController:
        def estimate_damage(self, *_args, **_kwargs) -> int:
            return 7
        
        def has_knowledge_of_enemy(self, state, tags) -> bool:
            return True  # Party has knowledge

    skill = SkillDef(
        id="power_slash",
        name="Power Slash",
        description="",
        tags=(),
        required_weapon_tags=(),
        target_mode="single_enemy",
        max_targets=1,
        mp_cost=3,
        base_power=4,
        effect_type="damage",
        gold_value=0,
    )
    from tbg.domain.state import GameState
    from tbg.core.rng import RNG
    state = GameState(seed=1, rng=RNG(1), mode="play", current_node_id="test")
    monkeypatch.delenv("TBG_DEBUG", raising=False)
    _set_inputs(monkeypatch, ["1"])
    _ = app._prompt_skill_choice([skill], battle_state, _KnowledgeController(), "hero", state)
    out = capsys.readouterr().out
    assert "Projected: 7" in out  # Should show projected because of knowledge
    assert "Power:" not in out  # Should not fall back to base power


def test_debug_enemy_display_includes_defense(monkeypatch, capsys) -> None:
    """Debug mode should show enemy defense alongside HP."""
    view, battle_state = _build_panel_view()
    monkeypatch.setenv("TBG_DEBUG", "1")
    app._render_battle_state_panel(view, battle_state, active_id="hero")
    out = capsys.readouterr().out
    assert "|D1]" in out  # Should show defense in ultra-compact format (|D1])
    assert "[15/15" in out  # Should show HP bracket


def test_party_talk_prints_once(monkeypatch, capsys) -> None:
    """Party Talk should produce exactly one RESULTS panel with no duplicates."""
    from tbg.services.battle_service import PartyTalkEvent
    from tbg.presentation.cli.app import _format_battle_event_lines, _render_results_panel
    
    events = [
        PartyTalkEvent(
            speaker_id="party_emma",
            speaker_name="Emma",
            text="Emma: Goblins typically have 18-26 HP."
        )
    ]
    lines = _format_battle_event_lines(events)
    _render_results_panel(lines)
    out = capsys.readouterr().out
    
    # Should contain exactly one RESULTS panel
    assert out.count("| RESULTS") == 1
    # Should contain the talk line exactly once
    assert out.count("Emma: Goblins typically have 18-26 HP.") == 1


def test_battle_id_heading_only_in_debug(monkeypatch, capsys) -> None:
    """Battle ID heading should only appear in debug mode."""
    state, battle_state = _build_state_and_battle(enemy_hp=10)
    service = _FakeBattleService()
    _set_inputs(monkeypatch, ["1", "1"])
    
    # Non-debug mode
    monkeypatch.delenv("TBG_DEBUG", raising=False)
    app._run_battle_loop(service, battle_state, state)
    out = capsys.readouterr().out
    assert "=== Battle battle_" not in out
    
    # Debug mode
    monkeypatch.setenv("TBG_DEBUG", "1")
    battle_state.is_over = False  # Reset for second run
    battle_state.victor = None
    _set_inputs(monkeypatch, ["1", "1"])
    app._run_battle_loop(service, battle_state, state)
    out = capsys.readouterr().out
    assert "=== Battle battle_" in out