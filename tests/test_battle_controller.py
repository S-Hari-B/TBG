"""Test battle controller is UI-agnostic and doesn't depend on presentation layer."""
from __future__ import annotations

from tbg.core.rng import RNG
from tbg.domain.battle_models import BattleState, Combatant
from tbg.domain.entities import Stats, Player
from tbg.domain.state import GameState
from tbg.services import BattleController, BattleAction
from tbg.services.battle_service import (
    AttackResolvedEvent,
    BattleResolvedEvent,
    BattleService,
    ItemUsedEvent,
)
from tbg.data.repositories import (
    ArmourRepository,
    EnemiesRepository,
    ItemsRepository,
    KnowledgeRepository,
    LootTablesRepository,
    PartyMembersRepository,
    SkillsRepository,
    WeaponsRepository,
)


def _build_battle_controller() -> tuple[BattleController, GameState, BattleState]:
    """Build minimal controller setup."""
    weapons_repo = WeaponsRepository()
    armour_repo = ArmourRepository()
    enemies_repo = EnemiesRepository()
    party_repo = PartyMembersRepository()
    knowledge_repo = KnowledgeRepository()
    skills_repo = SkillsRepository()
    items_repo = ItemsRepository()
    loot_repo = LootTablesRepository()

    battle_service = BattleService(
        enemies_repo=enemies_repo,
        party_members_repo=party_repo,
        knowledge_repo=knowledge_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        skills_repo=skills_repo,
        items_repo=items_repo,
        loot_tables_repo=loot_repo,
    )

    controller = BattleController(battle_service)

    rng = RNG(42)
    player = Player(
        id="hero",
        name="Hero",
        class_id="warrior",
        stats=Stats(max_hp=30, hp=30, max_mp=5, mp=5, attack=5, defense=2, speed=10),
    )
    state = GameState(seed=42, rng=rng, mode="battle", current_node_id="test", player=player)

    hero_combatant = Combatant(
        instance_id=player.id,
        display_name=player.name,
        side="allies",
        stats=player.stats,
    )
    enemy_combatant = Combatant(
        instance_id="enemy_1",
        display_name="Goblin",
        side="enemies",
        stats=Stats(max_hp=10, hp=10, max_mp=0, mp=0, attack=3, defense=1, speed=5),
    )
    battle_state = BattleState(
        battle_id="test_battle",
        allies=[hero_combatant],
        enemies=[enemy_combatant],
        current_actor_id=player.id,
        player_id=player.id,
    )

    return controller, state, battle_state


def test_controller_exposes_structured_state() -> None:
    """Verify controller provides structured state without needing CLI."""
    controller, state, battle_state = _build_battle_controller()

    view = controller.get_battle_view(battle_state)
    assert view.battle_id == "test_battle"
    assert len(view.allies) == 1
    assert len(view.enemies) == 1
    assert view.current_actor_id == "hero"


def test_controller_identifies_player_turn() -> None:
    """Verify controller can identify player-controlled turns."""
    controller, state, battle_state = _build_battle_controller()

    assert controller.is_player_controlled_turn(battle_state, state) is True
    assert controller.is_enemy_turn(battle_state) is False


def test_controller_provides_available_actions() -> None:
    """Verify controller exposes available actions as structured data."""
    controller, state, battle_state = _build_battle_controller()

    actions = controller.get_available_actions(battle_state, state)
    assert actions["can_attack"] is True
    assert actions["can_use_skill"] is False
    assert actions["can_use_item"] is False
    assert actions["can_talk"] is False
    assert isinstance(actions["available_skills"], list)
    assert actions["items"] == []


def test_controller_lists_items_when_available() -> None:
    controller, state, battle_state = _build_battle_controller()
    state.inventory.add_item("potion_hp_small", 1)

    actions = controller.get_available_actions(battle_state, state)

    assert actions["can_use_item"] is True
    assert len(actions["items"]) == 1


def test_controller_applies_action_and_returns_events() -> None:
    """Verify controller applies actions and returns events without printing."""
    controller, state, battle_state = _build_battle_controller()

    action = BattleAction(action_type="attack", target_id="enemy_1")
    events = controller.apply_player_action(battle_state, state, action)

    assert len(events) > 0
    assert any(isinstance(evt, AttackResolvedEvent) for evt in events)


def test_controller_applies_item_action() -> None:
    controller, state, battle_state = _build_battle_controller()
    state.inventory.add_item("potion_hp_small", 1)
    hero = battle_state.allies[0]
    hero.stats.hp = max(1, hero.stats.hp - 5)

    action = BattleAction(action_type="item", item_id="potion_hp_small", target_id=hero.instance_id)
    events = controller.apply_player_action(battle_state, state, action)

    assert any(isinstance(evt, ItemUsedEvent) for evt in events)


def test_controller_determines_state_panel_rendering() -> None:
    """Verify controller logic for when to render state panels."""
    controller, state, battle_state = _build_battle_controller()

    # First turn should render
    assert controller.should_render_state_panel(battle_state, state, is_first_turn=True) is True

    # Player turns should render
    assert controller.should_render_state_panel(battle_state, state, is_first_turn=False) is True

    # Change to enemy turn
    battle_state.current_actor_id = "enemy_1"
    assert controller.should_render_state_panel(battle_state, state, is_first_turn=False) is False


def test_controller_runs_ai_turns_without_input() -> None:
    """Verify controller can execute AI turns purely from game state."""
    controller, state, battle_state = _build_battle_controller()

    # Set enemy as current actor
    battle_state.current_actor_id = "enemy_1"

    events = controller.run_enemy_turn(battle_state, state.rng)
    assert len(events) > 0
    assert any(isinstance(evt, (AttackResolvedEvent, BattleResolvedEvent)) for evt in events)
