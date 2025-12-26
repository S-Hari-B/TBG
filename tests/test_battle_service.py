from __future__ import annotations

from tbg.core.rng import RNG
from tbg.data.repositories import (
    ArmourRepository,
    ClassesRepository,
    EnemiesRepository,
    KnowledgeRepository,
    PartyMembersRepository,
    WeaponsRepository,
)
from tbg.domain.state import GameState
from tbg.services.battle_service import AttackResolvedEvent, BattleService, PartyTalkEvent
from tbg.services.factories import create_player_from_class_id


def _make_battle_service() -> BattleService:
    return BattleService(
        enemies_repo=EnemiesRepository(),
        party_members_repo=PartyMembersRepository(),
        knowledge_repo=KnowledgeRepository(),
        weapons_repo=WeaponsRepository(),
        armour_repo=ArmourRepository(),
    )


def _make_state(seed: int = 123, with_party: bool = True) -> GameState:
    rng = RNG(seed)
    state = GameState(seed=seed, rng=rng, mode="game_menu", current_node_id="class_select")
    classes_repo = ClassesRepository()
    weapons_repo = WeaponsRepository()
    armour_repo = ArmourRepository()
    player = create_player_from_class_id(
        class_id="warrior",
        name="Tester",
        classes_repo=classes_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        rng=rng,
    )
    state.player = player
    if with_party:
        state.party_members = ["emma"]
    return state


def test_start_battle_single_enemy_creates_expected_combatants() -> None:
    service = _make_battle_service()
    state = _make_state()
    battle_state, events = service.start_battle("goblin_grunt", state)

    assert battle_state.battle_id
    assert len(battle_state.enemies) == 1
    assert battle_state.enemies[0].display_name == "Goblin Grunt"
    assert len(battle_state.allies) == 2  # player + emma
    assert events  # battle started event emitted


def test_start_battle_group_enemy_creates_multiple_enemies() -> None:
    service = _make_battle_service()
    state = _make_state()
    battle_state, _ = service.start_battle("goblin_pack_3", state)

    assert len(battle_state.enemies) == 3


def test_basic_attack_reduces_hp_and_can_kill() -> None:
    service = _make_battle_service()
    state = _make_state()
    battle_state, _ = service.start_battle("goblin_grunt", state)

    attacker = battle_state.allies[0]
    target = battle_state.enemies[0]
    starting_hp = target.stats.hp
    events = service.basic_attack(battle_state, attacker.instance_id, target.instance_id)

    assert target.stats.hp < starting_hp
    assert any(isinstance(evt, AttackResolvedEvent) for evt in events)


def test_battle_resolves_victory_when_all_enemies_dead() -> None:
    service = _make_battle_service()
    state = _make_state()
    battle_state, _ = service.start_battle("goblin_grunt", state)

    player = battle_state.allies[0]
    while not battle_state.is_over:
        living_enemy = next(enemy for enemy in battle_state.enemies if enemy.is_alive)
        service.basic_attack(battle_state, player.instance_id, living_enemy.instance_id)
        if battle_state.is_over:
            break
        service.run_enemy_turn(battle_state, state.rng)

    assert battle_state.victor == "allies"


def test_battle_turn_order_deterministic_for_seed() -> None:
    service = _make_battle_service()
    state = _make_state()
    battle_state, _ = service.start_battle("goblin_pack_3", state)

    expected_order = [
        combatant.instance_id
        for combatant in sorted(
            battle_state.allies + battle_state.enemies, key=lambda c: (-c.stats.speed, c.instance_id)
        )
    ]
    assert battle_state.turn_queue == expected_order


def test_party_talk_returns_expected_knowledge_text_for_goblins() -> None:
    service = _make_battle_service()
    state = _make_state()
    battle_state, _ = service.start_battle("goblin_pack_3", state)
    battle_state.current_actor_id = "party_emma"

    events = service.party_talk(battle_state, "party_emma")

    talk_events = [evt for evt in events if isinstance(evt, PartyTalkEvent)]
    assert talk_events
    assert "HP tends to be around" in talk_events[0].text


def test_enemy_ai_target_selection_deterministic_for_seed() -> None:
    service = _make_battle_service()
    state_a = _make_state(seed=999, with_party=False)
    state_b = _make_state(seed=999, with_party=False)

    battle_a, _ = service.start_battle("goblin_grunt", state_a)
    battle_b, _ = service.start_battle("goblin_grunt", state_b)

    events_a = service.run_enemy_turn(battle_a, state_a.rng)
    events_b = service.run_enemy_turn(battle_b, state_b.rng)

    target_a = next(evt.target_id for evt in events_a if isinstance(evt, AttackResolvedEvent))
    target_b = next(evt.target_id for evt in events_b if isinstance(evt, AttackResolvedEvent))

    assert target_a == target_b

