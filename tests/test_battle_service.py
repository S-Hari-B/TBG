from __future__ import annotations

from tbg.core.rng import RNG
from tbg.data.repositories import (
    ArmourRepository,
    ClassesRepository,
    EnemiesRepository,
    KnowledgeRepository,
    PartyMembersRepository,
    SkillsRepository,
    WeaponsRepository,
)
from tbg.domain.state import GameState
from tbg.services.battle_service import (
    AttackResolvedEvent,
    BattleService,
    GuardAppliedEvent,
    PartyTalkEvent,
    SkillUsedEvent,
)
from tbg.services.factories import create_player_from_class_id


def _make_battle_service() -> BattleService:
    return BattleService(
        enemies_repo=EnemiesRepository(),
        party_members_repo=PartyMembersRepository(),
        knowledge_repo=KnowledgeRepository(),
        weapons_repo=WeaponsRepository(),
        armour_repo=ArmourRepository(),
        skills_repo=SkillsRepository(),
    )


def _make_state(seed: int = 123, with_party: bool = True, class_id: str = "warrior") -> GameState:
    rng = RNG(seed)
    state = GameState(seed=seed, rng=rng, mode="game_menu", current_node_id="class_select")
    classes_repo = ClassesRepository()
    weapons_repo = WeaponsRepository()
    armour_repo = ArmourRepository()
    player = create_player_from_class_id(
        class_id=class_id,
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

    events = service.party_talk(battle_state, "party_emma", RNG(7))

    talk_events = [evt for evt in events if isinstance(evt, PartyTalkEvent)]
    assert talk_events
    assert "Emma:" in talk_events[0].text


def test_party_talk_hp_estimate_is_deterministic() -> None:
    service = _make_battle_service()
    state = _make_state()
    battle_state, _ = service.start_battle("goblin_grunt", state)
    battle_state.current_actor_id = "party_emma"

    events = service.party_talk(battle_state, "party_emma", RNG(99))
    talk_event = next(evt for evt in events if isinstance(evt, PartyTalkEvent))

    assert (
        talk_event.text
        == "Emma: Goblin Grunt look to have around 20-25 HP. Average, but quicker than most untrained adventurers. Often attack in groups and try to overwhelm isolated targets."
    )


def test_party_talk_without_knowledge_defaults_to_uncertain() -> None:
    service = _make_battle_service()
    service._knowledge_repo._ensure_loaded()  # type: ignore[attr-defined]
    service._knowledge_repo._definitions["emma"] = []  # type: ignore[attr-defined]
    state = _make_state()
    battle_state, _ = service.start_battle("goblin_pack_3", state)
    battle_state.current_actor_id = "party_emma"

    events = service.party_talk(battle_state, "party_emma", RNG(10))
    talk_event = next(evt for evt in events if isinstance(evt, PartyTalkEvent))

    assert "I'm not sure" in talk_event.text


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


def test_skill_eligibility_by_weapon_tags() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False)
    battle_state, _ = service.start_battle("goblin_grunt", state)
    skills = service.get_available_skills(battle_state, state.player.id)
    skill_ids = {skill.id for skill in skills}
    assert "skill_power_slash" in skill_ids
    assert "skill_brace" in skill_ids


def test_single_target_skill_applies_damage_and_cost() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False)
    battle_state, _ = service.start_battle("goblin_grunt", state)
    enemy_id = battle_state.enemies[0].instance_id
    initial_mp = state.player.stats.mp

    events = service.use_skill(battle_state, state.player.id, "skill_power_slash", [enemy_id])

    assert any(isinstance(evt, SkillUsedEvent) for evt in events)
    assert battle_state.enemies[0].stats.hp == 12  # 22 - 10 damage
    assert state.player.stats.mp == initial_mp - 3


def test_multi_target_skill_hits_up_to_three_targets() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False, class_id="mage")
    battle_state, _ = service.start_battle("goblin_pack_3", state)
    enemy_ids = [enemy.instance_id for enemy in battle_state.enemies]
    initial_mp = state.player.stats.mp

    events = service.use_skill(battle_state, state.player.id, "skill_ember_wave", enemy_ids)

    assert sum(isinstance(evt, SkillUsedEvent) for evt in events) == 3
    assert state.player.stats.mp == initial_mp - 6
    for enemy in battle_state.enemies:
        assert enemy.stats.hp == 18  # 22 - 4


def test_guard_reduces_next_damage_then_expires() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False)
    battle_state, _ = service.start_battle("goblin_grunt", state)
    enemy_id = battle_state.enemies[0].instance_id

    guard_events = service.use_skill(battle_state, state.player.id, "skill_brace", [])
    assert any(isinstance(evt, GuardAppliedEvent) for evt in guard_events)

    attack_events = service.basic_attack(battle_state, enemy_id, state.player.id)
    damage_event = next(evt for evt in attack_events if isinstance(evt, AttackResolvedEvent))
    assert damage_event.damage == 0  # 5 guard absorbs the 5 damage


def test_ai_uses_skill_deterministically_with_seed() -> None:
    service = _make_battle_service()
    state = _make_state(seed=555, with_party=True, class_id="mage")
    battle_state, _ = service.start_battle("goblin_grunt", state)
    emma_id = next(ally.instance_id for ally in battle_state.allies if ally.instance_id != state.player.id)

    events = service.run_ally_ai_turn(battle_state, emma_id, state.rng)

    assert any(isinstance(evt, (SkillUsedEvent, AttackResolvedEvent)) for evt in events)

