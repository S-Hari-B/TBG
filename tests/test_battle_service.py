from __future__ import annotations

import json

import pytest

from tbg.core.rng import RNG
from tbg.data.repositories import (
    ArmourRepository,
    ClassesRepository,
    EnemiesRepository,
    FloorsRepository,
    ItemsRepository,
    KnowledgeRepository,
    LocationsRepository,
    LootTablesRepository,
    PartyMembersRepository,
    SkillsRepository,
    SummonsRepository,
    WeaponsRepository,
)
from tbg.domain.battle_models import BattleState, Combatant
from tbg.domain.defs import ItemDef
from tbg.domain.entities.stats import Stats
from tbg.domain.state import GameState
from tbg.services.battle_service import (
    AttackResolvedEvent,
    BattleResolvedEvent,
    BattleService,
    DebuffAppliedEvent,
    DebuffExpiredEvent,
    GuardAppliedEvent,
    ItemUsedEvent,
    LootAcquiredEvent,
    PartyTalkEvent,
    SummonSpawnedEvent,
    SkillUsedEvent,
)
from tbg.services.factories import create_player_from_class_id
from tbg.services.inventory_service import InventoryService


def _make_battle_service() -> BattleService:
    floors_repo = FloorsRepository()
    locations_repo = LocationsRepository(floors_repo=floors_repo)
    return BattleService(
        enemies_repo=EnemiesRepository(),
        party_members_repo=PartyMembersRepository(),
        knowledge_repo=KnowledgeRepository(),
        weapons_repo=WeaponsRepository(),
        armour_repo=ArmourRepository(),
        skills_repo=SkillsRepository(),
        items_repo=ItemsRepository(),
        loot_tables_repo=LootTablesRepository(),
        floors_repo=floors_repo,
        locations_repo=locations_repo,
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
    assert len({id(enemy) for enemy in battle_state.enemies}) == len(battle_state.enemies)


def test_auto_spawn_equipped_summons_respects_bond_capacity() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False, class_id="beastmaster")
    assert state.player is not None
    state.player.attributes.BOND = 10
    state.player.equipped_summons = ["micro_raptor", "micro_raptor"]

    battle_state, events = service.start_battle("goblin_grunt", state)

    summons = [ally for ally in battle_state.allies if "summon" in ally.tags]
    assert len(summons) == 2
    assert all(summon.owner_id == state.player.id for summon in summons)
    assert [summon.source_id for summon in summons] == ["micro_raptor", "micro_raptor"]
    assert [summon.bond_cost for summon in summons] == [5, 5]
    summon_def = SummonsRepository().get("micro_raptor")
    expected_attack = summon_def.attack + state.player.attributes.BOND * summon_def.bond_scaling.atk_per_bond
    assert summons[0].stats.attack == expected_attack
    assert sum(isinstance(evt, SummonSpawnedEvent) for evt in events) == 2


def test_auto_spawn_stops_when_capacity_exceeded() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False, class_id="beastmaster")
    assert state.player is not None
    state.player.attributes.BOND = 8
    state.player.equipped_summons = ["micro_raptor", "micro_raptor"]

    battle_state, _ = service.start_battle("goblin_grunt", state)

    summons = [ally for ally in battle_state.allies if "summon" in ally.tags]
    assert len(summons) == 1
    assert summons[0].source_id == "micro_raptor"


def test_auto_spawn_respects_order_and_stop_rule() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False, class_id="beastmaster")
    assert state.player is not None
    state.player.attributes.BOND = 10
    state.player.equipped_summons = ["black_hawk", "micro_raptor"]

    battle_state, _ = service.start_battle("goblin_grunt", state)

    summons = [ally for ally in battle_state.allies if "summon" in ally.tags]
    assert len(summons) == 1
    assert summons[0].source_id == "black_hawk"


def test_auto_spawn_deterministic_for_same_seed() -> None:
    service_a = _make_battle_service()
    service_b = _make_battle_service()
    state_a = _make_state(seed=555, with_party=False, class_id="beastmaster")
    state_b = _make_state(seed=555, with_party=False, class_id="beastmaster")
    assert state_a.player is not None
    assert state_b.player is not None
    state_a.player.attributes.BOND = 10
    state_b.player.attributes.BOND = 10
    state_a.player.equipped_summons = ["micro_raptor", "micro_raptor"]
    state_b.player.equipped_summons = ["micro_raptor", "micro_raptor"]

    battle_a, events_a = service_a.start_battle("goblin_grunt", state_a)
    battle_b, events_b = service_b.start_battle("goblin_grunt", state_b)

    summon_ids_a = [evt.summon_instance_id for evt in events_a if isinstance(evt, SummonSpawnedEvent)]
    summon_ids_b = [evt.summon_instance_id for evt in events_b if isinstance(evt, SummonSpawnedEvent)]
    assert summon_ids_a == summon_ids_b
    assert battle_a.turn_queue == battle_b.turn_queue


def test_auto_spawn_noop_when_equipped_empty() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False, class_id="beastmaster")
    assert state.player is not None
    state.player.attributes.BOND = 10
    state.player.equipped_summons = []

    battle_state, events = service.start_battle("goblin_grunt", state)

    summons = [ally for ally in battle_state.allies if "summon" in ally.tags]
    assert len(summons) == 0
    assert not any(isinstance(evt, SummonSpawnedEvent) for evt in events)


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


def test_estimate_damage_matches_basic_attack_when_guard_zero() -> None:
    service = _make_battle_service()
    attacker_stats = Stats(max_hp=10, hp=10, max_mp=0, mp=0, attack=6, defense=1, speed=1)
    target_stats = Stats(max_hp=12, hp=12, max_mp=0, mp=0, attack=3, defense=2, speed=1)
    attacker = Combatant(
        instance_id="attacker",
        display_name="Attacker",
        side="allies",
        stats=attacker_stats,
        guard_reduction=0,
    )
    target = Combatant(
        instance_id="target",
        display_name="Target",
        side="enemies",
        stats=target_stats,
        guard_reduction=0,
    )
    estimate = service.estimate_damage(attacker, target)
    battle_state = BattleState(battle_id="test", allies=[attacker], enemies=[target])
    starting_hp = target.stats.hp
    service.basic_attack(battle_state, attacker.instance_id, target.instance_id)
    actual_damage = starting_hp - target.stats.hp
    assert estimate == actual_damage


def test_estimate_damage_does_not_mutate_target() -> None:
    service = _make_battle_service()
    attacker_stats = Stats(max_hp=10, hp=10, max_mp=0, mp=0, attack=6, defense=1, speed=1)
    target_stats = Stats(max_hp=12, hp=12, max_mp=0, mp=0, attack=3, defense=2, speed=1)
    attacker = Combatant(
        instance_id="attacker",
        display_name="Attacker",
        side="allies",
        stats=attacker_stats,
        guard_reduction=0,
    )
    target = Combatant(
        instance_id="target",
        display_name="Target",
        side="enemies",
        stats=target_stats,
        guard_reduction=5,
    )
    hp_before = target.stats.hp
    guard_before = target.guard_reduction
    _ = service.estimate_damage(attacker, target)
    assert target.stats.hp == hp_before
    assert target.guard_reduction == guard_before


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
        == "Emma: Goblin Grunt look to have around 27-32 HP. Average, but quicker than most untrained adventurers. Often attack in groups and try to overwhelm isolated targets."
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


def test_level_up_recalculates_attribute_scaled_stats() -> None:
    service = _make_battle_service()
    state = _make_state()
    assert state.player is not None
    base = state.player.base_stats
    # Simulate unscaled stats to ensure recalculation runs.
    state.player.stats.max_hp = base.max_hp
    state.player.stats.max_mp = base.max_mp
    state.player.stats.attack = base.attack
    state.player.stats.speed = base.speed

    service._award_exp(state, state.player.id, 20)

    expected_max_hp = base.max_hp + state.player.attributes.VIT * 3
    expected_max_mp = base.max_mp + state.player.attributes.INT * 2
    expected_attack = base.attack + state.player.attributes.STR
    expected_speed = base.speed + state.player.attributes.DEX
    assert state.player.stats.max_hp == expected_max_hp
    assert state.player.stats.max_mp == expected_max_mp
    assert state.player.stats.attack == expected_attack
    assert state.player.stats.speed == expected_speed


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


def test_enemy_scaling_floor_zero_no_change() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False)
    state.current_location_id = "threshold_inn"

    battle_state, _ = service.start_battle("goblin_grunt", state)

    enemy = battle_state.enemies[0]
    assert enemy.stats.max_hp == 29  # rebalance baseline
    assert enemy.stats.attack == 10  # 7 base + 3 weapon
    assert enemy.stats.defense == 8
    assert enemy.stats.speed == 8


def test_enemy_scaling_floor_one_applies() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False)
    state.current_location_id = "floor_one_gate"

    battle_state, _ = service.start_battle("goblin_grunt", state)

    enemy = battle_state.enemies[0]
    assert enemy.stats.max_hp == 39  # +10 per level
    assert enemy.stats.attack == 12  # +2 per level
    assert enemy.stats.defense == 9
    assert enemy.stats.speed == 8


def test_enemy_scaling_deterministic_for_same_seed() -> None:
    service = _make_battle_service()
    state_a = _make_state(seed=444, with_party=False)
    state_b = _make_state(seed=444, with_party=False)
    state_a.current_location_id = "floor_one_gate"
    state_b.current_location_id = "floor_one_gate"

    battle_a, _ = service.start_battle("goblin_grunt", state_a)
    battle_b, _ = service.start_battle("goblin_grunt", state_b)

    stats_a = battle_a.enemies[0].stats
    stats_b = battle_b.enemies[0].stats
    assert (stats_a.max_hp, stats_a.attack, stats_a.defense, stats_a.speed) == (
        stats_b.max_hp,
        stats_b.attack,
        stats_b.defense,
        stats_b.speed,
    )


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
        floors_repo = FloorsRepository()
        locations_repo = LocationsRepository(floors_repo=floors_repo)
        service = BattleService(
            enemies_repo=EnemiesRepository(),
            party_members_repo=PartyMembersRepository(),
            knowledge_repo=KnowledgeRepository(),
            weapons_repo=WeaponsRepository(),
            armour_repo=ArmourRepository(),
            skills_repo=SkillsRepository(),
            items_repo=ItemsRepository(),
            loot_tables_repo=LootTablesRepository(base_path=loot_dir),
            floors_repo=floors_repo,
            locations_repo=locations_repo,
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
    assert battle_state.enemies[0].stats.hp == 17  # 29 - 12 damage
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
        assert enemy.stats.hp == 28  # 29 - 1


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


def test_spawn_summon_injects_combatant_with_expected_fields() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False)
    battle_state, _ = service.start_battle("goblin_grunt", state)
    summon_def = SummonsRepository().get("micro_raptor")

    events = service._spawn_summon_into_battle(
        state,
        battle_state,
        owner_id=state.player.id,
        owner_bond=state.player.attributes.BOND,
        summon_id="micro_raptor",
    )

    summon = next(
        ally for ally in battle_state.allies if ally.source_id == "micro_raptor"
    )
    assert summon.display_name == summon_def.name
    assert summon.owner_id == state.player.id
    assert summon.bond_cost == summon_def.bond_cost
    assert summon.source_id == "micro_raptor"
    assert "summon" in summon.tags
    assert summon.instance_id in battle_state.turn_queue
    assert any(isinstance(evt, SummonSpawnedEvent) for evt in events)


def test_spawn_summon_is_deterministic_for_same_seed() -> None:
    service_a = _make_battle_service()
    service_b = _make_battle_service()
    state_a = _make_state(seed=777, with_party=False)
    state_b = _make_state(seed=777, with_party=False)
    battle_a, _ = service_a.start_battle("goblin_grunt", state_a)
    battle_b, _ = service_b.start_battle("goblin_grunt", state_b)

    events_a = service_a._spawn_summon_into_battle(
        state_a,
        battle_a,
        owner_id=state_a.player.id,
        owner_bond=state_a.player.attributes.BOND,
        summon_id="micro_raptor",
    )
    events_b = service_b._spawn_summon_into_battle(
        state_b,
        battle_b,
        owner_id=state_b.player.id,
        owner_bond=state_b.player.attributes.BOND,
        summon_id="micro_raptor",
    )

    summon_id_a = next(evt.summon_instance_id for evt in events_a if isinstance(evt, SummonSpawnedEvent))
    summon_id_b = next(evt.summon_instance_id for evt in events_b if isinstance(evt, SummonSpawnedEvent))
    assert summon_id_a == summon_id_b
    assert battle_a.turn_queue == battle_b.turn_queue


def test_spawn_summon_rejects_unknown_owner() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False)
    battle_state, _ = service.start_battle("goblin_grunt", state)

    with pytest.raises(ValueError):
        service._spawn_summon_into_battle(
            state,
            battle_state,
            owner_id="missing_owner",
            owner_bond=0,
            summon_id="micro_raptor",
        )


def test_attack_debuff_lasts_until_round_boundary() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False)
    battle_state, _ = service.start_battle("goblin_grunt", state)
    assert state.player is not None
    player_id = state.player.id
    enemy = battle_state.enemies[0]
    enemy.stats.attack = 12
    state.inventory.add_item("weakening_vial", 1)

    events = service.use_item(battle_state, state, player_id, "weakening_vial", enemy.instance_id)
    assert any(isinstance(evt, DebuffAppliedEvent) for evt in events)
    hero = battle_state.allies[0]
    hero.stats.defense = 5

    expiry_round = enemy.debuffs[0].expires_at_round
    while battle_state.round_index < expiry_round - 1:
        round_events = service._start_new_round(battle_state)
        assert not any(isinstance(evt, DebuffExpiredEvent) for evt in round_events)

    damage, _ = service._resolve_damage(enemy, hero, bonus_power=0, minimum=1)
    expected_damage = max(1, (enemy.stats.attack - 2) - hero.stats.defense)
    assert damage == expected_damage
    assert enemy.debuffs

    expire_events = service._start_new_round(battle_state)
    assert battle_state.round_index == expiry_round
    assert any(isinstance(evt, DebuffExpiredEvent) for evt in expire_events)
    assert not enemy.debuffs

    # Second attack should no longer benefit from the debuff
    battle_state.current_actor_id = enemy.instance_id
    second_attack_events = service.run_enemy_turn(battle_state, state.rng)
    attack_event_two = next(evt for evt in second_attack_events if isinstance(evt, AttackResolvedEvent))
    assert attack_event_two.damage == max(1, enemy.stats.attack - hero.stats.defense)


def test_defense_debuff_persists_until_round_boundary() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False)
    battle_state, _ = service.start_battle("goblin_grunt", state)
    assert state.player is not None
    enemy = battle_state.enemies[0]
    hero = next(ally for ally in battle_state.allies if ally.instance_id == state.player.id)
    hero.stats.attack = 15
    enemy.stats.defense = 6
    state.inventory.add_item("armor_sunder_powder", 1)

    service.use_item(battle_state, state, state.player.id, "armor_sunder_powder", enemy.instance_id)
    assert enemy.debuffs

    expiry_round = enemy.debuffs[0].expires_at_round
    while battle_state.round_index < expiry_round - 1:
        round_events = service._start_new_round(battle_state)
        assert not any(isinstance(evt, DebuffExpiredEvent) for evt in round_events)

    damage, _ = service._resolve_damage(hero, enemy, bonus_power=0, minimum=1)
    assert damage == max(1, hero.stats.attack - (enemy.stats.defense - 2))
    assert enemy.debuffs

    expire_events = service._start_new_round(battle_state)
    assert battle_state.round_index == expiry_round
    assert any(isinstance(evt, DebuffExpiredEvent) for evt in expire_events)
    assert not enemy.debuffs


def test_reapplying_same_debuff_has_no_effect_but_consumes_item() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False)
    battle_state, _ = service.start_battle("goblin_grunt", state)
    assert state.player is not None
    player_id = state.player.id
    enemy = battle_state.enemies[0]
    initial_qty = state.inventory.items.get("weakening_vial", 0)
    state.inventory.add_item("weakening_vial", 2)

    first = service.use_item(battle_state, state, player_id, "weakening_vial", enemy.instance_id)
    assert any(isinstance(evt, DebuffAppliedEvent) for evt in first)

    second = service.use_item(battle_state, state, player_id, "weakening_vial", enemy.instance_id)
    assert not any(isinstance(evt, DebuffAppliedEvent) for evt in second)
    assert any(
        isinstance(evt, ItemUsedEvent) and evt.result_text and "had no effect" in evt.result_text
        for evt in second
    )
    assert state.inventory.items.get("weakening_vial", 0) == initial_qty


def test_debuff_expiry_events_suppressed_for_dead_enemies() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False)
    battle_state, _ = service.start_battle("goblin_grunt", state)
    assert state.player is not None
    player_id = state.player.id
    enemy = battle_state.enemies[0]
    state.inventory.add_item("weakening_vial", 1)

    service.use_item(battle_state, state, player_id, "weakening_vial", enemy.instance_id)
    enemy.stats.hp = 0  # simulate death before expiry

    expire_events = service._start_new_round(battle_state)
    expire_events.extend(service._start_new_round(battle_state))

    assert not any(isinstance(evt, DebuffExpiredEvent) for evt in expire_events)
    assert not enemy.debuffs


def test_debuffs_cleared_immediately_on_death() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False)
    battle_state, _ = service.start_battle("goblin_grunt", state)
    assert state.player is not None

    enemy = battle_state.enemies[0]
    state.inventory.add_item("armor_sunder_powder", 1)
    service.use_item(battle_state, state, state.player.id, "armor_sunder_powder", enemy.instance_id)
    assert enemy.debuffs

    hero = next(ally for ally in battle_state.allies if ally.instance_id == state.player.id)
    hero.stats.attack = 999
    damage, _ = service._resolve_damage(hero, enemy, bonus_power=0, minimum=1)
    assert damage >= enemy.stats.hp
    assert not enemy.is_alive
    assert not enemy.debuffs

def test_use_item_heals_player_and_consumes_inventory() -> None:
    service = _make_battle_service()
    state = _make_state()
    state.inventory.add_item("potion_hp_small", 1)
    battle_state, _ = service.start_battle("goblin_grunt", state)
    assert state.player is not None
    player = next(ally for ally in battle_state.allies if ally.instance_id == state.player.id)
    player.stats.hp = max(1, player.stats.hp - 12)
    qty_before = state.inventory.items.get("potion_hp_small", 0)

    events = service.use_item(battle_state, state, player.instance_id, "potion_hp_small", player.instance_id)

    assert state.inventory.items.get("potion_hp_small", 0) == max(0, qty_before - 1)
    assert player.stats.hp > 0
    assert any(isinstance(evt, ItemUsedEvent) for evt in events)


def test_use_item_consumes_even_without_effect() -> None:
    service = _make_battle_service()
    state = _make_state()
    state.inventory.add_item("potion_hp_small", 1)
    battle_state, _ = service.start_battle("goblin_grunt", state)
    assert state.player is not None
    player = next(ally for ally in battle_state.allies if ally.instance_id == state.player.id)
    player.stats.hp = player.stats.max_hp
    qty_before = state.inventory.items.get("potion_hp_small", 0)

    events = service.use_item(battle_state, state, player.instance_id, "potion_hp_small", player.instance_id)
    event = next(evt for evt in events if isinstance(evt, ItemUsedEvent))

    assert state.inventory.items.get("potion_hp_small", 0) == max(0, qty_before - 1)
    assert event.hp_delta == 0


def test_use_item_cannot_target_defeated_ally() -> None:
    service = _make_battle_service()
    state = _make_state()
    state.inventory.add_item("potion_hp_small", 1)
    battle_state, _ = service.start_battle("goblin_grunt", state)
    ally = next(ally for ally in battle_state.allies if ally.instance_id.startswith("party_"))
    ally.stats.hp = 0
    qty_before = state.inventory.items.get("potion_hp_small", 0)

    with pytest.raises(ValueError):
        service.use_item(battle_state, state, battle_state.allies[0].instance_id, "potion_hp_small", ally.instance_id)

    assert state.inventory.items.get("potion_hp_small", 0) == qty_before


def test_enemy_targeting_items_blocked_for_now() -> None:
    service = _make_battle_service()
    service._items_repo._ensure_loaded()  # type: ignore[attr-defined]
    service._items_repo._definitions["bomb_enemy"] = ItemDef(  # type: ignore[attr-defined]
        id="bomb_enemy",
        name="Bomb",
        kind="consumable",
        value=5,
        heal_hp=0,
        heal_mp=0,
        restore_energy=0,
        targeting="enemy",
    )
    state = _make_state()
    battle_state, _ = service.start_battle("goblin_grunt", state)
    state.inventory.add_item("bomb_enemy", 1)
    qty_before = state.inventory.items.get("bomb_enemy", 0)

    with pytest.raises(ValueError):
        service.use_item(
            battle_state, state, battle_state.allies[0].instance_id, "bomb_enemy", battle_state.enemies[0].instance_id
        )

    assert state.inventory.items.get("bomb_enemy", 0) == qty_before


def test_ai_uses_skill_deterministically_with_seed() -> None:
    service = _make_battle_service()
    state = _make_state(seed=555, with_party=True, class_id="mage")
    battle_state, _ = service.start_battle("goblin_grunt", state)
    emma_id = next(ally.instance_id for ally in battle_state.allies if ally.instance_id != state.player.id)

    events = service.run_ally_ai_turn(battle_state, emma_id, state.rng)

    assert any(isinstance(evt, (SkillUsedEvent, AttackResolvedEvent)) for evt in events)

