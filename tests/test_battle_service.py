from __future__ import annotations

import json

from tbg.core.rng import RNG
from tbg.data.repositories import (
    ArmourRepository,
    ClassesRepository,
    EnemiesRepository,
    ItemsRepository,
    KnowledgeRepository,
    LootTablesRepository,
    PartyMembersRepository,
    SkillsRepository,
    WeaponsRepository,
)
from tbg.domain.state import GameState
from tbg.services.battle_service import (
    AttackResolvedEvent,
    BattleResolvedEvent,
    BattleService,
    GuardAppliedEvent,
    LootAcquiredEvent,
    PartyTalkEvent,
    SkillUsedEvent,
)
from tbg.services.factories import create_player_from_class_id
from tbg.services.inventory_service import InventoryService


def _make_battle_service() -> BattleService:
    return BattleService(
        enemies_repo=EnemiesRepository(),
        party_members_repo=PartyMembersRepository(),
        knowledge_repo=KnowledgeRepository(),
        weapons_repo=WeaponsRepository(),
        armour_repo=ArmourRepository(),
        skills_repo=SkillsRepository(),
        items_repo=ItemsRepository(),
        loot_tables_repo=LootTablesRepository(),
    )


def _make_state(seed: int = 123, with_party: bool = True, class_id: str = "warrior") -> GameState:
    rng = RNG(seed)
    state = GameState(seed=seed, rng=rng, mode="game_menu", current_node_id="class_select")
    weapons_repo = WeaponsRepository()
    armour_repo = ArmourRepository()
    classes_repo = ClassesRepository(weapons_repo=weapons_repo, armour_repo=armour_repo)
    party_repo = PartyMembersRepository()
    inventory_service = InventoryService(
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        party_members_repo=party_repo,
    )
    player = create_player_from_class_id(
        class_id=class_id,
        name="Tester",
        classes_repo=classes_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        rng=rng,
    )
    state.player = player
    class_def = classes_repo.get(class_id)
    inventory_service.initialize_player_loadout(state, player.id, class_def)
    state.member_levels[player.id] = classes_repo.get_starting_level(class_id)
    state.member_exp[player.id] = 0
    if with_party:
        state.party_members = ["emma"]
        member_def = party_repo.get("emma")
        inventory_service.initialize_party_member_loadout(state, "emma", member_def)
        state.member_levels["emma"] = member_def.starting_level
        state.member_exp["emma"] = 0
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
    names = [enemy.display_name for enemy in battle_state.enemies]
    assert len(set(names)) == len(names)
    assert all("(" in name for name in names)


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


def test_player_ko_immediately_ends_battle() -> None:
    service = _make_battle_service()
    state = _make_state()
    battle_state, _ = service.start_battle("goblin_pack_3", state)
    player = next(ally for ally in battle_state.allies if ally.instance_id == state.player.id)
    enemy = battle_state.enemies[0]
    enemy.stats.attack = 999

    events = service.basic_attack(battle_state, enemy.instance_id, player.instance_id)

    assert battle_state.is_over is True
    assert battle_state.victor == "enemies"
    assert any(isinstance(evt, BattleResolvedEvent) for evt in events)


def test_apply_victory_rewards_restores_player_mp_and_clears_defeat_flag() -> None:
    service = _make_battle_service()
    state = _make_state()
    battle_state, _ = service.start_battle("goblin_grunt", state)
    for enemy in battle_state.enemies:
        enemy.stats.hp = 0
    assert state.player is not None
    state.player.stats.mp = 0

    service.apply_victory_rewards(battle_state, state)

    assert state.player.stats.mp == state.player.stats.max_mp
    assert state.flags["flag_last_battle_defeat"] is False


def test_level_up_restores_player_hp_and_mp() -> None:
    service = _make_battle_service()
    state = _make_state()
    assert state.player is not None
    player_id = state.player.id
    state.player.stats.hp = 1
    state.player.stats.mp = 0

    service._award_exp(state, player_id, 20)

    assert state.player.stats.hp == state.player.stats.max_hp
    assert state.player.stats.mp == state.player.stats.max_mp


def test_party_ai_prefers_skill_when_available() -> None:
    service = _make_battle_service()
    state = _make_state()
    battle_state, _ = service.start_battle("goblin_pack_3", state)
    emma = next(ally for ally in battle_state.allies if ally.instance_id == "party_emma")
    battle_state.current_actor_id = emma.instance_id
    emma.stats.mp = emma.stats.max_mp

    events = service.run_ally_ai_turn(battle_state, emma.instance_id, state.rng)

    assert any(isinstance(evt, SkillUsedEvent) for evt in events)


def test_party_ai_falls_back_to_basic_attack_with_insufficient_mp() -> None:
    service = _make_battle_service()
    state = _make_state()
    battle_state, _ = service.start_battle("goblin_pack_3", state)
    emma = next(ally for ally in battle_state.allies if ally.instance_id == "party_emma")
    battle_state.current_actor_id = emma.instance_id
    emma.stats.mp = 0

    events = service.run_ally_ai_turn(battle_state, emma.instance_id, state.rng)

    assert any(isinstance(evt, AttackResolvedEvent) for evt in events)


def test_apply_victory_rewards_grants_gold_exp_and_loot() -> None:
    service = _make_battle_service()
    state = _make_state()
    battle_state, _ = service.start_battle("goblin_pack_3", state)
    for enemy in battle_state.enemies:
        enemy.stats.hp = 0
    state.rng = RNG(1)
    events = service.apply_victory_rewards(battle_state, state)

    assert state.gold >= 9
    assert state.member_levels[state.player.id] >= 2
    assert any(isinstance(evt, LootAcquiredEvent) for evt in events)


def test_optional_loot_drop_is_deterministic_by_seed(tmp_path) -> None:
    loot_dir = tmp_path / "loot_defs"
    loot_dir.mkdir()
    (loot_dir / "loot_tables.json").write_text(
        json.dumps(
            [
                {
                    "id": "test_goblin_drops",
                    "required_enemy_tags": ["goblin"],
                    "drops": [
                        {"item_id": "potion_energy_small", "chance": 0.5, "min_qty": 1, "max_qty": 1},
                    ],
                }
            ],
            indent=2,
        ),
        encoding="utf-8",
    )

    def _drops(seed: int) -> bool:
        service = BattleService(
            enemies_repo=EnemiesRepository(),
            party_members_repo=PartyMembersRepository(),
            knowledge_repo=KnowledgeRepository(),
            weapons_repo=WeaponsRepository(),
            armour_repo=ArmourRepository(),
            skills_repo=SkillsRepository(),
            items_repo=ItemsRepository(),
            loot_tables_repo=LootTablesRepository(base_path=loot_dir),
        )
        state = _make_state(with_party=False)
        battle_state, _ = service.start_battle("goblin_grunt", state)
        for enemy in battle_state.enemies:
            enemy.stats.hp = 0
        state.rng = RNG(seed)
        events = service.apply_victory_rewards(battle_state, state)
        return any(isinstance(evt, LootAcquiredEvent) and evt.item_id == "potion_energy_small" for evt in events)

    assert _drops(1) is True
    assert _drops(2) is False


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

