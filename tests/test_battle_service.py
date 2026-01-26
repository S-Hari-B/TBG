from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tbg.core.rng import RNG
from tbg.data import paths
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
from tbg.domain.defs import ItemDef, KnowledgeEntry
from tbg.domain.enemy_scaling import (
    ATTACK_PER_LEVEL,
    DEFENSE_PER_LEVEL,
    HP_PER_LEVEL,
    SPEED_PER_LEVEL,
)
from tbg.domain.entities import Attributes
from tbg.domain.entities.stats import Stats
from tbg.domain.state import GameState
from tbg.services.battle_service import (
    ANTI_REPEAT_IGNORE_GAP,
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
from tbg.services.knowledge_keys import resolve_enemy_knowledge_key


FIXTURE_DEFINITIONS_DIR = Path(__file__).parent / "fixtures" / "data" / "definitions"


def _make_battle_service() -> BattleService:
    floors_repo = FloorsRepository(base_path=FIXTURE_DEFINITIONS_DIR)
    locations_repo = LocationsRepository(
        floors_repo=floors_repo, base_path=FIXTURE_DEFINITIONS_DIR
    )
    return BattleService(
        enemies_repo=EnemiesRepository(base_path=FIXTURE_DEFINITIONS_DIR),
        party_members_repo=PartyMembersRepository(base_path=FIXTURE_DEFINITIONS_DIR),
        knowledge_repo=KnowledgeRepository(base_path=FIXTURE_DEFINITIONS_DIR),
        weapons_repo=WeaponsRepository(base_path=FIXTURE_DEFINITIONS_DIR),
        armour_repo=ArmourRepository(base_path=FIXTURE_DEFINITIONS_DIR),
        skills_repo=SkillsRepository(base_path=FIXTURE_DEFINITIONS_DIR),
        items_repo=ItemsRepository(base_path=FIXTURE_DEFINITIONS_DIR),
        loot_tables_repo=LootTablesRepository(base_path=FIXTURE_DEFINITIONS_DIR),
        summons_repo=SummonsRepository(base_path=FIXTURE_DEFINITIONS_DIR),
        floors_repo=floors_repo,
        locations_repo=locations_repo,
    )


def _make_state(seed: int = 123, with_party: bool = True, class_id: str = "warrior") -> GameState:
    rng = RNG(seed)
    state = GameState(seed=seed, rng=rng, mode="game_menu", current_node_id="class_select")
    weapons_repo = WeaponsRepository(base_path=FIXTURE_DEFINITIONS_DIR)
    armour_repo = ArmourRepository(base_path=FIXTURE_DEFINITIONS_DIR)
    classes_repo = ClassesRepository(
        weapons_repo=weapons_repo, armour_repo=armour_repo, base_path=FIXTURE_DEFINITIONS_DIR
    )
    party_repo = PartyMembersRepository(base_path=FIXTURE_DEFINITIONS_DIR)
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
        state.party_member_attributes["emma"] = member_def.starting_attributes
    return state


def _make_live_battle_service() -> BattleService:
    definitions_dir = paths.get_definitions_path()
    floors_repo = FloorsRepository(base_path=definitions_dir)
    locations_repo = LocationsRepository(
        floors_repo=floors_repo, base_path=definitions_dir
    )
    return BattleService(
        enemies_repo=EnemiesRepository(base_path=definitions_dir),
        party_members_repo=PartyMembersRepository(base_path=definitions_dir),
        knowledge_repo=KnowledgeRepository(base_path=definitions_dir),
        weapons_repo=WeaponsRepository(base_path=definitions_dir),
        armour_repo=ArmourRepository(base_path=definitions_dir),
        skills_repo=SkillsRepository(base_path=definitions_dir),
        items_repo=ItemsRepository(base_path=definitions_dir),
        loot_tables_repo=LootTablesRepository(base_path=definitions_dir),
        summons_repo=SummonsRepository(base_path=definitions_dir),
        floors_repo=floors_repo,
        locations_repo=locations_repo,
    )


def _make_live_state(seed: int = 123, with_party: bool = True, class_id: str = "warrior") -> GameState:
    definitions_dir = paths.get_definitions_path()
    rng = RNG(seed)
    state = GameState(seed=seed, rng=rng, mode="game_menu", current_node_id="class_select")
    weapons_repo = WeaponsRepository(base_path=definitions_dir)
    armour_repo = ArmourRepository(base_path=definitions_dir)
    classes_repo = ClassesRepository(
        weapons_repo=weapons_repo, armour_repo=armour_repo, base_path=definitions_dir
    )
    party_repo = PartyMembersRepository(base_path=definitions_dir)
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
        state.party_member_attributes["emma"] = member_def.starting_attributes
    return state


def test_battle_view_hp_visibility_by_tier() -> None:
    service = _make_battle_service()
    knowledge_key = resolve_enemy_knowledge_key(service._enemies_repo.get("goblin_grunt"))

    state_tier0 = _make_state(seed=10)
    battle_state_tier0, _ = service.start_battle("goblin_grunt", state_tier0)
    view_tier0 = service.get_battle_view(battle_state_tier0)
    assert view_tier0.enemies[0].hp_display == "???"

    state_tier1 = _make_state(seed=11)
    state_tier1.knowledge_kill_counts[knowledge_key] = 25
    battle_state_tier1, _ = service.start_battle("goblin_grunt", state_tier1)
    view_tier1 = service.get_battle_view(battle_state_tier1)
    expected_range = service._format_static_hp_range(battle_state_tier1.enemies[0].stats.max_hp)
    assert view_tier1.enemies[0].hp_display == expected_range

    state_tier2 = _make_state(seed=12)
    state_tier2.knowledge_kill_counts[knowledge_key] = 75
    battle_state_tier2, _ = service.start_battle("goblin_grunt", state_tier2)
    view_tier2 = service.get_battle_view(battle_state_tier2)
    assert view_tier2.enemies[0].hp_display == (
        f"{battle_state_tier2.enemies[0].stats.hp}/{battle_state_tier2.enemies[0].stats.max_hp}"
    )


def test_tier1_hp_range_is_static() -> None:
    service = _make_battle_service()
    knowledge_key = resolve_enemy_knowledge_key(service._enemies_repo.get("goblin_grunt"))
    state = _make_state(seed=13)
    state.knowledge_kill_counts[knowledge_key] = 25
    battle_state, _ = service.start_battle("goblin_grunt", state)
    view_before = service.get_battle_view(battle_state)
    battle_state.enemies[0].stats.hp = max(0, battle_state.enemies[0].stats.hp - 5)
    view_after = service.get_battle_view(battle_state)
    assert view_before.enemies[0].hp_display == view_after.enemies[0].hp_display


def test_tier2_hp_display_updates_with_damage() -> None:
    service = _make_battle_service()
    knowledge_key = resolve_enemy_knowledge_key(service._enemies_repo.get("goblin_grunt"))
    state = _make_state(seed=14)
    state.knowledge_kill_counts[knowledge_key] = 75
    battle_state, _ = service.start_battle("goblin_grunt", state)
    view_before = service.get_battle_view(battle_state)
    battle_state.enemies[0].stats.hp = max(0, battle_state.enemies[0].stats.hp - 5)
    view_after = service.get_battle_view(battle_state)
    assert view_before.enemies[0].hp_display != view_after.enemies[0].hp_display
    assert view_after.enemies[0].hp_display.startswith(
        f"{battle_state.enemies[0].stats.hp}/"
    )


def test_knowledge_snapshot_does_not_consume_rng() -> None:
    service = _make_battle_service()
    state = _make_state(seed=15)
    battle_state, _ = service.start_battle("goblin_grunt", state)
    before = state.rng.export_state()
    _ = service._build_knowledge_snapshot(state, battle_state)
    after = state.rng.export_state()
    assert before == after


def test_refresh_knowledge_snapshot_updates_view() -> None:
    service = _make_battle_service()
    knowledge_key = resolve_enemy_knowledge_key(service._enemies_repo.get("goblin_grunt"))
    state = _make_state(seed=16)
    battle_state, _ = service.start_battle("goblin_grunt", state)
    view_before = service.get_battle_view(battle_state)
    assert view_before.enemies[0].hp_display == "???"
    state.knowledge_kill_counts[knowledge_key] = 75
    service.refresh_knowledge_snapshot(battle_state, state)
    view_after = service.get_battle_view(battle_state)
    assert view_after.enemies[0].hp_display == (
        f"{battle_state.enemies[0].stats.hp}/{battle_state.enemies[0].stats.max_hp}"
    )


def _make_threat_test_battle() -> tuple[BattleState, Combatant, Combatant, Combatant]:
    enemy = Combatant(
        instance_id="enemy_1",
        display_name="Enemy",
        side="enemies",
        stats=Stats(max_hp=10, hp=10, max_mp=0, mp=0, attack=5, defense=1, speed=1),
    )
    ally_a = Combatant(
        instance_id="ally_a",
        display_name="Ally A",
        side="allies",
        stats=Stats(max_hp=30, hp=30, max_mp=0, mp=0, attack=4, defense=5, speed=1),
    )
    ally_b = Combatant(
        instance_id="ally_b",
        display_name="Ally B",
        side="allies",
        stats=Stats(max_hp=10, hp=10, max_mp=0, mp=0, attack=4, defense=1, speed=1),
    )
    battle_state = BattleState(
        battle_id="battle_test",
        allies=[ally_a, ally_b],
        enemies=[enemy],
        current_actor_id=enemy.instance_id,
    )
    return battle_state, enemy, ally_a, ally_b


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
    summon_def = SummonsRepository(base_path=FIXTURE_DEFINITIONS_DIR).get("micro_raptor")
    assert [summon.bond_cost for summon in summons] == [summon_def.bond_cost] * 2
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


def test_auto_spawn_party_members_in_order_with_owner_bond() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=True, class_id="beastmaster")
    assert state.player is not None
    state.player.attributes.BOND = 10
    state.party_member_attributes["emma"].BOND = 5
    state.player.equipped_summons = ["micro_raptor"]
    state.party_member_summon_loadouts["emma"] = ["micro_raptor"]

    battle_state, events = service.start_battle("goblin_grunt", state)

    summon_events = [evt for evt in events if isinstance(evt, SummonSpawnedEvent)]
    assert [evt.owner_id for evt in summon_events] == [state.player.id, "party_emma"]
    summons = [ally for ally in battle_state.allies if "summon" in ally.tags]
    assert {summon.source_id for summon in summons} == {"micro_raptor"}
    emma_summon = next(summon for summon in summons if summon.owner_id == "party_emma")
    raptor_def = SummonsRepository(base_path=FIXTURE_DEFINITIONS_DIR).get("micro_raptor")
    expected_attack = raptor_def.attack + state.party_member_attributes["emma"].BOND * raptor_def.bond_scaling.atk_per_bond
    assert emma_summon.stats.attack == expected_attack


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


def test_party_talk_tier0_temp_reveal_updates_snapshot_and_text() -> None:
    service = _make_battle_service()
    state = _make_state()
    battle_state, _ = service.start_battle("goblin_grunt", state)
    battle_state.current_actor_id = "party_emma"

    events = service.party_talk(battle_state, state, "party_emma")

    talk_event = next(evt for evt in events if isinstance(evt, PartyTalkEvent))
    expected_range = service._format_static_hp_range(battle_state.enemies[0].stats.max_hp)
    view = service.get_battle_view(battle_state)
    assert expected_range in talk_event.text
    assert view.enemies[0].hp_display == expected_range


def test_party_talk_temp_reveal_is_battle_only() -> None:
    service = _make_battle_service()
    state = _make_state()

    battle_state, _ = service.start_battle("goblin_grunt", state)
    battle_state.current_actor_id = "party_emma"
    service.party_talk(battle_state, state, "party_emma")
    view_after = service.get_battle_view(battle_state)
    assert view_after.enemies[0].hp_display != "???"

    next_battle, _ = service.start_battle("goblin_grunt", state)
    view_next = service.get_battle_view(next_battle)
    assert view_next.enemies[0].hp_display == "???"


def test_party_talk_output_deterministic_across_seeds() -> None:
    service = _make_battle_service()
    state_a = _make_state(seed=1)
    state_b = _make_state(seed=999)
    battle_a, _ = service.start_battle("goblin_grunt", state_a)
    battle_b, _ = service.start_battle("goblin_grunt", state_b)
    battle_a.current_actor_id = "party_emma"
    battle_b.current_actor_id = "party_emma"

    events_a = service.party_talk(battle_a, state_a, "party_emma")
    events_b = service.party_talk(battle_b, state_b, "party_emma")
    talk_a = next(evt for evt in events_a if isinstance(evt, PartyTalkEvent)).text
    talk_b = next(evt for evt in events_b if isinstance(evt, PartyTalkEvent)).text

    assert talk_a == talk_b


def test_party_talk_tier0_without_hp_knowledge_has_no_numbers() -> None:
    service = _make_battle_service()
    service._knowledge_repo._ensure_loaded()  # type: ignore[attr-defined]
    service._knowledge_repo._definitions["emma"] = [
        KnowledgeEntry(
            knowledge_keys=(),
            enemy_tags=("goblin",),
            max_level=None,
            hp_range=None,
            speed_hint="Fast movers.",
            behavior="They harass the back line.",
        )
    ]  # type: ignore[attr-defined]
    state = _make_state()
    battle_state, _ = service.start_battle("goblin_grunt", state)
    battle_state.current_actor_id = "party_emma"

    events = service.party_talk(battle_state, state, "party_emma")
    talk_event = next(evt for evt in events if isinstance(evt, PartyTalkEvent))

    assert not re.search(r"\d", talk_event.text)


def test_party_talk_tier1_mentions_static_range() -> None:
    service = _make_battle_service()
    state = _make_state()
    knowledge_key = resolve_enemy_knowledge_key(service._enemies_repo.get("goblin_grunt"))
    state.knowledge_kill_counts[knowledge_key] = 25
    battle_state, _ = service.start_battle("goblin_grunt", state)
    battle_state.current_actor_id = "party_emma"

    events = service.party_talk(battle_state, state, "party_emma")
    talk_event = next(evt for evt in events if isinstance(evt, PartyTalkEvent))
    expected_range = service._format_static_hp_range(battle_state.enemies[0].stats.max_hp)

    assert expected_range in talk_event.text


def test_party_talk_tier2_has_no_numeric_hp() -> None:
    service = _make_battle_service()
    state = _make_state()
    knowledge_key = resolve_enemy_knowledge_key(service._enemies_repo.get("goblin_grunt"))
    state.knowledge_kill_counts[knowledge_key] = 75
    battle_state, _ = service.start_battle("goblin_grunt", state)
    battle_state.current_actor_id = "party_emma"

    events = service.party_talk(battle_state, state, "party_emma")
    talk_event = next(evt for evt in events if isinstance(evt, PartyTalkEvent))

    assert not re.search(r"\d+/\d+|\d+-\d+", talk_event.text)


def test_party_talk_matching_prefers_knowledge_keys() -> None:
    service = _make_battle_service()
    knowledge_key = resolve_enemy_knowledge_key(service._enemies_repo.get("goblin_grunt"))
    service._knowledge_repo._ensure_loaded()  # type: ignore[attr-defined]
    service._knowledge_repo._definitions["emma"] = [
        KnowledgeEntry(
            knowledge_keys=(knowledge_key,),
            enemy_tags=("goblin",),
            max_level=None,
            hp_range=None,
            speed_hint=None,
            behavior="Key match behavior.",
        ),
        KnowledgeEntry(
            knowledge_keys=(),
            enemy_tags=("goblin",),
            max_level=None,
            hp_range=None,
            speed_hint=None,
            behavior="Tag match behavior.",
        ),
    ]  # type: ignore[attr-defined]
    state = _make_state()
    battle_state, _ = service.start_battle("goblin_grunt", state)
    battle_state.current_actor_id = "party_emma"

    events = service.party_talk(battle_state, state, "party_emma")
    talk_event = next(evt for evt in events if isinstance(evt, PartyTalkEvent))

    assert "Key match behavior." in talk_event.text
    assert "Tag match behavior." not in talk_event.text


def test_party_talk_goblin_rampager_uses_knowledge_key() -> None:
    service = _make_live_battle_service()
    state = _make_live_state()
    battle_state, _ = service.start_battle("goblin_rampager", state)
    battle_state.current_actor_id = "party_emma"

    events = service.party_talk(battle_state, state, "party_emma")
    talk_event = next(evt for evt in events if isinstance(evt, PartyTalkEvent))

    assert "Goblin Rampager look to have around" in talk_event.text
    assert "Often attack in groups" in talk_event.text


def test_party_talk_tag_only_entries_still_work() -> None:
    service = _make_battle_service()
    service._knowledge_repo._ensure_loaded()  # type: ignore[attr-defined]
    service._knowledge_repo._definitions["emma"] = [
        KnowledgeEntry(
            knowledge_keys=(),
            enemy_tags=("goblin",),
            max_level=None,
            hp_range=None,
            speed_hint=None,
            behavior="Legacy tag behavior.",
        )
    ]  # type: ignore[attr-defined]
    state = _make_state()
    battle_state, _ = service.start_battle("goblin_grunt", state)
    battle_state.current_actor_id = "party_emma"

    events = service.party_talk(battle_state, state, "party_emma")
    talk_event = next(evt for evt in events if isinstance(evt, PartyTalkEvent))

    assert "Legacy tag behavior." in talk_event.text


def test_party_talk_preview_does_not_mutate_state() -> None:
    service = _make_battle_service()
    state = _make_state()
    battle_state, _ = service.start_battle("goblin_pack_3", state)
    battle_state.current_actor_id = "party_emma"

    rng_before = state.rng.export_state()
    snapshot_before = battle_state.knowledge_snapshot
    temp_reveals_before = set(battle_state.temp_knowledge_reveals)
    knowledge_before = dict(state.knowledge_kill_counts)
    actor_before = battle_state.current_actor_id

    service.party_talk_preview(battle_state, state, "party_emma")

    assert battle_state.current_actor_id == actor_before
    assert battle_state.temp_knowledge_reveals == temp_reveals_before
    assert battle_state.knowledge_snapshot is snapshot_before
    assert state.knowledge_kill_counts == knowledge_before
    assert state.rng.export_state() == rng_before


def test_party_talk_without_knowledge_defaults_to_uncertain() -> None:
    service = _make_battle_service()
    service._knowledge_repo._ensure_loaded()  # type: ignore[attr-defined]
    service._knowledge_repo._definitions["emma"] = []  # type: ignore[attr-defined]
    state = _make_state()
    battle_state, _ = service.start_battle("goblin_pack_3", state)
    battle_state.current_actor_id = "party_emma"

    events = service.party_talk(battle_state, state, "party_emma")
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


def test_enemy_ai_prefers_higher_aggro_target() -> None:
    service = _make_battle_service()
    battle_state, enemy, ally_a, ally_b = _make_threat_test_battle()
    service._initialize_enemy_aggro(battle_state)

    events = service.run_enemy_turn(battle_state, RNG(5))
    target_id = next(evt.target_id for evt in events if isinstance(evt, AttackResolvedEvent))

    assert target_id == ally_a.instance_id


def test_enemy_targets_highest_damage_source() -> None:
    service = _make_battle_service()
    battle_state, enemy, ally_a, ally_b = _make_threat_test_battle()
    service._initialize_enemy_aggro(battle_state)

    service._resolve_damage(battle_state, ally_b, enemy, bonus_power=2, minimum=1)

    events = service.run_enemy_turn(battle_state, RNG(1))
    target_id = next(evt.target_id for evt in events if isinstance(evt, AttackResolvedEvent))

    assert target_id == ally_b.instance_id


def test_enemy_aggro_includes_summon_damage() -> None:
    service = _make_battle_service()
    battle_state, enemy, ally_a, ally_b = _make_threat_test_battle()
    summon = Combatant(
        instance_id="summon_1",
        display_name="Summon",
        side="allies",
        stats=Stats(max_hp=8, hp=8, max_mp=0, mp=0, attack=3, defense=0, speed=2),
        owner_id=ally_a.instance_id,
    )
    battle_state.allies.append(summon)
    service._initialize_enemy_aggro(battle_state)

    service._resolve_damage(battle_state, summon, enemy, bonus_power=6, minimum=1)

    events = service.run_enemy_turn(battle_state, RNG(2))
    target_id = next(evt.target_id for evt in events if isinstance(evt, AttackResolvedEvent))

    assert target_id == summon.instance_id


def test_enemy_ai_anti_repeat_penalty_can_switch_target() -> None:
    service = _make_battle_service()
    battle_state, enemy, ally_a, ally_b = _make_threat_test_battle()
    battle_state.enemy_aggro = {enemy.instance_id: {ally_a.instance_id: 10, ally_b.instance_id: 9}}
    battle_state.last_target = {enemy.instance_id: ally_a.instance_id}

    events = service.run_enemy_turn(battle_state, RNG(3))
    target_id = next(evt.target_id for evt in events if isinstance(evt, AttackResolvedEvent))

    assert target_id == ally_b.instance_id


def test_enemy_ai_anti_repeat_ignores_large_threat_gap() -> None:
    service = _make_battle_service()
    battle_state, enemy, ally_a, ally_b = _make_threat_test_battle()
    battle_state.enemy_aggro = {
        enemy.instance_id: {ally_a.instance_id: ANTI_REPEAT_IGNORE_GAP + 20, ally_b.instance_id: 5}
    }
    battle_state.last_target = {enemy.instance_id: ally_a.instance_id}

    events = service.run_enemy_turn(battle_state, RNG(3))
    target_id = next(evt.target_id for evt in events if isinstance(evt, AttackResolvedEvent))

    assert target_id == ally_a.instance_id


def test_enemy_ai_tie_break_uses_rng() -> None:
    service = _make_battle_service()
    battle_state, enemy, ally_a, ally_b = _make_threat_test_battle()
    battle_state.enemy_aggro = {enemy.instance_id: {ally_a.instance_id: 10, ally_b.instance_id: 10}}

    expected_index = RNG(7).randint(0, 1)
    expected_target = [ally_a.instance_id, ally_b.instance_id][expected_index]
    events = service.run_enemy_turn(battle_state, RNG(7))
    target_id = next(evt.target_id for evt in events if isinstance(evt, AttackResolvedEvent))

    assert target_id == expected_target


def test_aggro_damage_overtakes_base_seed() -> None:
    service = _make_battle_service()
    battle_state, enemy, ally_a, ally_b = _make_threat_test_battle()
    service._initialize_enemy_aggro(battle_state)
    aggro_map = battle_state.enemy_aggro[enemy.instance_id]
    assert aggro_map[ally_a.instance_id] > aggro_map[ally_b.instance_id]

    service._resolve_damage(battle_state, ally_b, enemy, bonus_power=2, minimum=1)

    assert aggro_map[ally_b.instance_id] > aggro_map[ally_a.instance_id]


def test_enemy_aggro_resets_per_battle() -> None:
    service = _make_battle_service()
    state = _make_state()
    battle_a, _ = service.start_battle("goblin_grunt", state)
    enemy_id = battle_a.enemies[0].instance_id
    ally_id = battle_a.allies[0].instance_id
    battle_a.enemy_aggro[enemy_id][ally_id] += 50
    battle_a.last_target[enemy_id] = ally_id

    battle_b, _ = service.start_battle("goblin_grunt", state)
    for enemy in battle_b.enemies:
        assert battle_b.last_target[enemy.instance_id] is None
        for ally in battle_b.allies:
            expected = service._base_threat_for_target(ally)
            assert battle_b.enemy_aggro[enemy.instance_id][ally.instance_id] == expected


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


def test_party_ai_avoids_aoe_when_one_enemy_alive() -> None:
    service = _make_battle_service()
    state = _make_state()
    battle_state, _ = service.start_battle("goblin_pack_3", state)
    emma = next(ally for ally in battle_state.allies if ally.instance_id == "party_emma")
    battle_state.current_actor_id = emma.instance_id
    emma.stats.mp = emma.stats.max_mp
    for enemy in battle_state.enemies[1:]:
        enemy.stats.hp = 0

    events = service.run_ally_ai_turn(battle_state, emma.instance_id, state.rng)

    assert not any(
        isinstance(evt, SkillUsedEvent) and evt.skill_id == "skill_ember_wave" for evt in events
    )


def test_party_ai_targets_highest_threat_enemy() -> None:
    service = _make_battle_service()
    state = _make_state()
    battle_state, _ = service.start_battle("goblin_pack_3", state)
    emma = next(ally for ally in battle_state.allies if ally.instance_id == "party_emma")
    battle_state.current_actor_id = emma.instance_id
    emma.stats.mp = emma.stats.max_mp
    enemy_a, enemy_b = battle_state.enemies[:2]
    battle_state.party_threat[emma.instance_id][enemy_b.instance_id] = (
        battle_state.party_threat[emma.instance_id][enemy_a.instance_id] + 50
    )

    events = service.run_ally_ai_turn(battle_state, emma.instance_id, state.rng)
    skill_event = next(evt for evt in events if isinstance(evt, SkillUsedEvent))

    assert skill_event.target_id == enemy_b.instance_id


def test_party_ai_multitarget_selects_top_threat_targets() -> None:
    service = _make_battle_service()
    state = _make_state()
    battle_state, _ = service.start_battle("goblin_pack_3", state)
    emma = next(ally for ally in battle_state.allies if ally.instance_id == "party_emma")
    living_enemies = [enemy for enemy in battle_state.enemies if enemy.is_alive]
    skill = service._skills_repo.get("skill_ember_wave")  # type: ignore[attr-defined]

    threat_map = battle_state.party_threat[emma.instance_id]
    threat_map[living_enemies[0].instance_id] = 10
    threat_map[living_enemies[1].instance_id] = 9
    threat_map[living_enemies[2].instance_id] = 1

    targets = service._select_ai_skill_targets(battle_state, skill, emma, living_enemies, RNG(4))

    assert targets == [living_enemies[0].instance_id, living_enemies[1].instance_id, living_enemies[2].instance_id]


def test_party_ai_multitarget_tie_breaks_with_rng() -> None:
    service = _make_battle_service()
    state = _make_state()
    battle_state, _ = service.start_battle("goblin_pack_3", state)
    emma = next(ally for ally in battle_state.allies if ally.instance_id == "party_emma")
    living_enemies = [enemy for enemy in battle_state.enemies if enemy.is_alive]
    skill = service._skills_repo.get("skill_ember_wave")  # type: ignore[attr-defined]

    threat_map = battle_state.party_threat[emma.instance_id]
    threat_map[living_enemies[0].instance_id] = 10
    threat_map[living_enemies[1].instance_id] = 10
    threat_map[living_enemies[2].instance_id] = 1

    expected_group = [living_enemies[0], living_enemies[1]]
    expected_rng = RNG(7)
    expected_rng.shuffle(expected_group)
    expected = [expected_group[0].instance_id, expected_group[1].instance_id, living_enemies[2].instance_id]

    targets = service._select_ai_skill_targets(battle_state, skill, emma, living_enemies, RNG(7))

    assert targets == expected


def test_party_ai_falls_back_to_basic_attack_with_insufficient_mp() -> None:
    service = _make_battle_service()
    state = _make_state()
    battle_state, _ = service.start_battle("goblin_pack_3", state)
    
    # Use player instead of emma, who has a sword (no skills with [] required_weapon_tags match sword tags)
    player = next(ally for ally in battle_state.allies if ally.instance_id == state.player.id)
    battle_state.current_actor_id = player.instance_id
    player.stats.mp = 0

    events = service.run_ally_ai_turn(battle_state, player.instance_id, state.rng)

    # Should fall back to basic attack since no skills match sword requirements with 0 MP
    assert any(isinstance(evt, AttackResolvedEvent) for evt in events)


def test_apply_victory_rewards_grants_gold_exp_and_loot() -> None:
    service = _make_battle_service()
    state = _make_state()
    battle_state, _ = service.start_battle("goblin_pack_3", state)
    for enemy in battle_state.enemies:
        enemy.stats.hp = 0
    state.rng = RNG(1)
    gold_before = state.gold
    exp_before = state.member_exp[state.player.id]
    level_before = state.member_levels[state.player.id]
    events = service.apply_victory_rewards(battle_state, state)

    assert state.gold > gold_before
    assert state.member_exp[state.player.id] > exp_before or state.member_levels[state.player.id] > level_before
    assert any(isinstance(evt, LootAcquiredEvent) for evt in events)


def test_apply_victory_rewards_idempotent() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False)
    battle_state, _ = service.start_battle("goblin_grunt", state)
    for enemy in battle_state.enemies:
        enemy.stats.hp = 0

    events_first = service.apply_victory_rewards(battle_state, state)

    assert events_first
    gold_after = state.gold
    exp_after = dict(state.member_exp)
    levels_after = dict(state.member_levels)
    inventory_after = dict(state.inventory.items)
    knowledge_after = dict(state.knowledge_kill_counts)

    events_second = service.apply_victory_rewards(battle_state, state)

    assert events_second == []
    assert state.gold == gold_after
    assert state.member_exp == exp_after
    assert state.member_levels == levels_after
    assert state.inventory.items == inventory_after
    assert state.knowledge_kill_counts == knowledge_after


def test_apply_victory_rewards_records_knowledge_kills() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False)
    battle_state, _ = service.start_battle("goblin_pack_3", state)
    for enemy in battle_state.enemies:
        enemy.stats.hp = 0
    state.knowledge_kill_counts["goblin_grunt"] = 1

    service.apply_victory_rewards(battle_state, state)

    assert state.knowledge_kill_counts["goblin_grunt"] == 4


def test_apply_victory_rewards_knowledge_key_resolution() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False)
    shaman_key = resolve_enemy_knowledge_key(service._enemies_repo.get("goblin_shaman"))
    battle_state, _ = service.start_battle("goblin_shaman", state)
    for enemy in battle_state.enemies:
        enemy.stats.hp = 0

    service.apply_victory_rewards(battle_state, state)

    assert state.knowledge_kill_counts[shaman_key] == 1
    assert "goblin_shaman" not in state.knowledge_kill_counts

    battle_state, _ = service.start_battle("goblin_grunt", state)
    for enemy in battle_state.enemies:
        enemy.stats.hp = 0

    service.apply_victory_rewards(battle_state, state)

    assert state.knowledge_kill_counts["goblin_grunt"] == 1


def test_apply_victory_rewards_does_not_consume_rng_without_loot(tmp_path) -> None:
    loot_dir = tmp_path / "loot_defs"
    loot_dir.mkdir()
    (loot_dir / "loot_tables.json").write_text("[]", encoding="utf-8")
    floors_repo = FloorsRepository(base_path=FIXTURE_DEFINITIONS_DIR)
    locations_repo = LocationsRepository(
        floors_repo=floors_repo, base_path=FIXTURE_DEFINITIONS_DIR
    )
    service = BattleService(
        enemies_repo=EnemiesRepository(base_path=FIXTURE_DEFINITIONS_DIR),
        party_members_repo=PartyMembersRepository(base_path=FIXTURE_DEFINITIONS_DIR),
        knowledge_repo=KnowledgeRepository(base_path=FIXTURE_DEFINITIONS_DIR),
        weapons_repo=WeaponsRepository(base_path=FIXTURE_DEFINITIONS_DIR),
        armour_repo=ArmourRepository(base_path=FIXTURE_DEFINITIONS_DIR),
        skills_repo=SkillsRepository(base_path=FIXTURE_DEFINITIONS_DIR),
        items_repo=ItemsRepository(base_path=FIXTURE_DEFINITIONS_DIR),
        loot_tables_repo=LootTablesRepository(base_path=loot_dir),
        summons_repo=SummonsRepository(base_path=FIXTURE_DEFINITIONS_DIR),
        floors_repo=floors_repo,
        locations_repo=locations_repo,
    )
    state = _make_state(with_party=False)
    battle_state, _ = service.start_battle("goblin_grunt", state)
    for enemy in battle_state.enemies:
        enemy.stats.hp = 0

    before = state.rng.export_state()
    service.apply_victory_rewards(battle_state, state)
    after = state.rng.export_state()

    assert after == before


def test_enemy_scaling_floor_zero_no_change() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False)
    state.current_location_id = "threshold_inn"

    battle_state, _ = service.start_battle("goblin_grunt", state)

    enemy = battle_state.enemies[0]
    assert enemy.stats.max_hp > 0
    assert enemy.stats.attack > 0
    assert enemy.stats.defense >= 0
    assert enemy.stats.speed > 0


def test_enemy_scaling_floor_one_applies() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False)
    state.current_location_id = "floor_one_gate"

    battle_state, _ = service.start_battle("goblin_grunt", state)

    enemy = battle_state.enemies[0]
    state_floor_zero = _make_state(with_party=False)
    state_floor_zero.current_location_id = "threshold_inn"
    battle_zero, _ = service.start_battle("goblin_grunt", state_floor_zero)
    base_stats = battle_zero.enemies[0].stats
    assert enemy.stats.max_hp - base_stats.max_hp == HP_PER_LEVEL
    assert enemy.stats.attack - base_stats.attack == ATTACK_PER_LEVEL
    assert enemy.stats.defense - base_stats.defense == DEFENSE_PER_LEVEL
    assert enemy.stats.speed - base_stats.speed == SPEED_PER_LEVEL


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
        floors_repo = FloorsRepository(base_path=FIXTURE_DEFINITIONS_DIR)
        locations_repo = LocationsRepository(
            floors_repo=floors_repo, base_path=FIXTURE_DEFINITIONS_DIR
        )
        service = BattleService(
            enemies_repo=EnemiesRepository(base_path=FIXTURE_DEFINITIONS_DIR),
            party_members_repo=PartyMembersRepository(base_path=FIXTURE_DEFINITIONS_DIR),
            knowledge_repo=KnowledgeRepository(base_path=FIXTURE_DEFINITIONS_DIR),
            weapons_repo=WeaponsRepository(base_path=FIXTURE_DEFINITIONS_DIR),
            armour_repo=ArmourRepository(base_path=FIXTURE_DEFINITIONS_DIR),
            skills_repo=SkillsRepository(base_path=FIXTURE_DEFINITIONS_DIR),
            items_repo=ItemsRepository(base_path=FIXTURE_DEFINITIONS_DIR),
            loot_tables_repo=LootTablesRepository(base_path=loot_dir),
            summons_repo=SummonsRepository(base_path=FIXTURE_DEFINITIONS_DIR),
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
    enemy = battle_state.enemies[0]
    attacker = battle_state.allies[0]
    initial_mp = state.player.stats.mp
    initial_hp = enemy.stats.hp
    skill_def = service._skills_repo.get("skill_power_slash")  # type: ignore[attr-defined]
    expected_damage = min(
        initial_hp,
        service.estimate_damage(
            attacker, enemy, bonus_power=skill_def.base_power, skill_tags=skill_def.tags
        ),
    )

    events = service.use_skill(battle_state, state.player.id, "skill_power_slash", [enemy_id])

    assert any(isinstance(evt, SkillUsedEvent) for evt in events)
    assert enemy.stats.hp == initial_hp - expected_damage
    assert state.player.stats.mp == initial_mp - skill_def.mp_cost


def test_multi_target_skill_hits_up_to_three_targets() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False, class_id="mage")
    battle_state, _ = service.start_battle("goblin_pack_3", state)
    enemy_ids = [enemy.instance_id for enemy in battle_state.enemies]
    initial_mp = state.player.stats.mp
    attacker = battle_state.allies[0]
    skill_def = service._skills_repo.get("skill_ember_wave")  # type: ignore[attr-defined]
    initial_hp = {enemy.instance_id: enemy.stats.hp for enemy in battle_state.enemies}
    expected = {
        enemy.instance_id: service.estimate_damage(
            attacker, enemy, bonus_power=skill_def.base_power, skill_tags=skill_def.tags
        )
        for enemy in battle_state.enemies
    }

    events = service.use_skill(battle_state, state.player.id, "skill_ember_wave", enemy_ids)

    assert sum(isinstance(evt, SkillUsedEvent) for evt in events) == 3
    assert state.player.stats.mp == initial_mp - skill_def.mp_cost
    for enemy in battle_state.enemies:
        assert enemy.stats.hp == initial_hp[enemy.instance_id] - expected[enemy.instance_id]


def test_magic_skill_uses_int_not_str_for_action_attack() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False, class_id="mage")
    battle_state, _ = service.start_battle("goblin_grunt", state)
    attacker = battle_state.allies[0]
    enemy = battle_state.enemies[0]
    assert attacker.attributes is not None
    attacker.weapon_tags = ("finesse",)
    base_power = 5
    magic_tags = ("fire",)

    baseline = service.estimate_damage(
        attacker, enemy, bonus_power=base_power, skill_tags=magic_tags
    )

    attacker.attributes = Attributes(
        STR=attacker.attributes.STR,
        DEX=attacker.attributes.DEX,
        INT=attacker.attributes.INT + 3,
        VIT=attacker.attributes.VIT,
        BOND=attacker.attributes.BOND,
    )
    int_scaled = service.estimate_damage(
        attacker, enemy, bonus_power=base_power, skill_tags=magic_tags
    )

    attacker.attributes = Attributes(
        STR=attacker.attributes.STR + 3,
        DEX=attacker.attributes.DEX,
        INT=attacker.attributes.INT - 3,
        VIT=attacker.attributes.VIT,
        BOND=attacker.attributes.BOND,
    )
    str_scaled = service.estimate_damage(
        attacker, enemy, bonus_power=base_power, skill_tags=magic_tags
    )

    assert int_scaled == baseline + 3
    assert str_scaled == baseline


def test_basic_attack_finesse_scales_with_dex_only() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False)
    battle_state, _ = service.start_battle("goblin_grunt", state)
    attacker = battle_state.allies[0]
    enemy = battle_state.enemies[0]
    assert attacker.attributes is not None
    attacker.weapon_tags = ("dagger", "finesse")
    base_attributes = attacker.attributes

    baseline = service.estimate_damage(attacker, enemy)

    attacker.attributes = Attributes(
        STR=base_attributes.STR,
        DEX=base_attributes.DEX + 4,
        INT=base_attributes.INT,
        VIT=base_attributes.VIT,
        BOND=base_attributes.BOND,
    )
    dex_scaled = service.estimate_damage(attacker, enemy)

    attacker.attributes = Attributes(
        STR=base_attributes.STR + 4,
        DEX=base_attributes.DEX,
        INT=base_attributes.INT,
        VIT=base_attributes.VIT,
        BOND=base_attributes.BOND,
    )
    str_scaled = service.estimate_damage(attacker, enemy)

    assert dex_scaled > baseline
    assert str_scaled == baseline


def test_physical_skill_uses_finesse_for_physical_scaling() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False)
    battle_state, _ = service.start_battle("goblin_grunt", state)
    attacker = battle_state.allies[0]
    enemy = battle_state.enemies[0]
    assert attacker.attributes is not None
    attacker.weapon_tags = ("dagger", "finesse")
    base_power = 4
    physical_tags = ("physical",)
    base_attributes = attacker.attributes

    baseline = service.estimate_damage(
        attacker, enemy, bonus_power=base_power, skill_tags=physical_tags
    )

    attacker.attributes = Attributes(
        STR=base_attributes.STR,
        DEX=base_attributes.DEX + 4,
        INT=base_attributes.INT,
        VIT=base_attributes.VIT,
        BOND=base_attributes.BOND,
    )
    dex_scaled = service.estimate_damage(
        attacker, enemy, bonus_power=base_power, skill_tags=physical_tags
    )

    attacker.attributes = Attributes(
        STR=base_attributes.STR + 4,
        DEX=base_attributes.DEX,
        INT=base_attributes.INT,
        VIT=base_attributes.VIT,
        BOND=base_attributes.BOND,
    )
    str_scaled = service.estimate_damage(
        attacker, enemy, bonus_power=base_power, skill_tags=physical_tags
    )

    assert dex_scaled > baseline
    assert str_scaled == baseline


def test_hybrid_skill_finesse_uses_dex_for_physical_portion() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False)
    battle_state, _ = service.start_battle("goblin_grunt", state)
    attacker = battle_state.allies[0]
    enemy = battle_state.enemies[0]
    assert attacker.attributes is not None
    attacker.weapon_tags = ("bow", "finesse")
    base_power = 6
    hybrid_tags = ("physical", "fire")
    base_attributes = attacker.attributes

    baseline = service.estimate_damage(
        attacker, enemy, bonus_power=base_power, skill_tags=hybrid_tags
    )

    attacker.attributes = Attributes(
        STR=base_attributes.STR,
        DEX=base_attributes.DEX + 4,
        INT=base_attributes.INT,
        VIT=base_attributes.VIT,
        BOND=base_attributes.BOND,
    )
    dex_scaled = service.estimate_damage(
        attacker, enemy, bonus_power=base_power, skill_tags=hybrid_tags
    )

    attacker.attributes = Attributes(
        STR=base_attributes.STR,
        DEX=base_attributes.DEX,
        INT=base_attributes.INT + 2,
        VIT=base_attributes.VIT,
        BOND=base_attributes.BOND,
    )
    int_scaled = service.estimate_damage(
        attacker, enemy, bonus_power=base_power, skill_tags=hybrid_tags
    )

    attacker.attributes = Attributes(
        STR=base_attributes.STR + 2,
        DEX=base_attributes.DEX,
        INT=base_attributes.INT,
        VIT=base_attributes.VIT,
        BOND=base_attributes.BOND,
    )
    str_scaled = service.estimate_damage(
        attacker, enemy, bonus_power=base_power, skill_tags=hybrid_tags
    )

    assert dex_scaled > baseline
    assert int_scaled > baseline
    assert str_scaled == baseline


def test_physical_skill_uses_str_not_int_for_action_attack() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False)
    battle_state, _ = service.start_battle("goblin_grunt", state)
    attacker = battle_state.allies[0]
    enemy = battle_state.enemies[0]
    assert attacker.attributes is not None
    base_power = 4
    physical_tags = ("physical",)
    base_attributes = attacker.attributes

    baseline = service.estimate_damage(
        attacker, enemy, bonus_power=base_power, skill_tags=physical_tags
    )

    attacker.attributes = Attributes(
        STR=base_attributes.STR + 3,
        DEX=base_attributes.DEX,
        INT=base_attributes.INT,
        VIT=base_attributes.VIT,
        BOND=base_attributes.BOND,
    )
    str_scaled = service.estimate_damage(
        attacker, enemy, bonus_power=base_power, skill_tags=physical_tags
    )

    attacker.attributes = Attributes(
        STR=base_attributes.STR,
        DEX=base_attributes.DEX,
        INT=base_attributes.INT + 3,
        VIT=base_attributes.VIT,
        BOND=base_attributes.BOND,
    )
    int_scaled = service.estimate_damage(
        attacker, enemy, bonus_power=base_power, skill_tags=physical_tags
    )

    assert str_scaled > baseline
    assert int_scaled == baseline


def test_hybrid_skill_scales_with_str_and_int() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False)
    battle_state, _ = service.start_battle("goblin_grunt", state)
    attacker = battle_state.allies[0]
    enemy = battle_state.enemies[0]
    assert attacker.attributes is not None
    base_power = 6
    hybrid_tags = ("physical", "fire")
    base_attributes = attacker.attributes

    baseline = service.estimate_damage(
        attacker, enemy, bonus_power=base_power, skill_tags=hybrid_tags
    )

    attacker.attributes = Attributes(
        STR=base_attributes.STR + 2,
        DEX=base_attributes.DEX,
        INT=base_attributes.INT,
        VIT=base_attributes.VIT,
        BOND=base_attributes.BOND,
    )
    str_scaled = service.estimate_damage(
        attacker, enemy, bonus_power=base_power, skill_tags=hybrid_tags
    )

    attacker.attributes = Attributes(
        STR=base_attributes.STR,
        DEX=base_attributes.DEX,
        INT=base_attributes.INT + 2,
        VIT=base_attributes.VIT,
        BOND=base_attributes.BOND,
    )
    int_scaled = service.estimate_damage(
        attacker, enemy, bonus_power=base_power, skill_tags=hybrid_tags
    )

    assert str_scaled > baseline
    assert int_scaled > baseline


def test_guard_reduces_next_damage_then_expires() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False)
    battle_state, _ = service.start_battle("goblin_grunt", state)
    enemy_id = battle_state.enemies[0].instance_id
    enemy = battle_state.enemies[0]
    player = battle_state.allies[0]

    guard_events = service.use_skill(battle_state, state.player.id, "skill_brace", [])
    assert any(isinstance(evt, GuardAppliedEvent) for evt in guard_events)
    guard_def = service._skills_repo.get("skill_brace")  # type: ignore[attr-defined]

    attack_events = service.basic_attack(battle_state, enemy_id, state.player.id)
    damage_event = next(evt for evt in attack_events if isinstance(evt, AttackResolvedEvent))
    expected_damage = service.estimate_damage(enemy, player, bonus_power=0)
    assert damage_event.damage == max(0, expected_damage - guard_def.base_power)


def test_spawn_summon_injects_combatant_with_expected_fields() -> None:
    service = _make_battle_service()
    state = _make_state(with_party=False)
    battle_state, _ = service.start_battle("goblin_grunt", state)
    summon_def = SummonsRepository(base_path=FIXTURE_DEFINITIONS_DIR).get("micro_raptor")

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

    damage, _ = service._resolve_damage(battle_state, enemy, hero, bonus_power=0, minimum=1)
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

    damage, _ = service._resolve_damage(battle_state, hero, enemy, bonus_power=0, minimum=1)
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
    damage, _ = service._resolve_damage(battle_state, hero, enemy, bonus_power=0, minimum=1)
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


def test_enemy_uses_skill_when_available() -> None:
    """Test that an enemy with MP and enemy_skill_ids uses a skill."""
    service = _make_battle_service()
    state = _make_state(seed=123)
    
    # Create a battle state with goblin_shaman (has skill_hex_spark)
    battle_state, _ = service.start_battle("goblin_shaman", state)
    shaman = battle_state.enemies[0]
    
    # Ensure shaman has MP for the skill
    assert shaman.stats.mp >= 2  # skill_hex_spark costs 2 MP
    battle_state.current_actor_id = shaman.instance_id
    
    # Run enemy turn
    events = service.run_enemy_turn(battle_state, state.rng)
    
    # Should use the skill
    assert any(isinstance(evt, SkillUsedEvent) and evt.skill_id == "skill_hex_spark" for evt in events)
    # MP should be consumed
    assert shaman.stats.mp < shaman.stats.max_mp


def test_enemy_falls_back_to_attack_without_mp() -> None:
    """Test that an enemy without sufficient MP falls back to basic attack."""
    service = _make_battle_service()
    state = _make_state(seed=123)
    
    battle_state, _ = service.start_battle("goblin_shaman", state)
    shaman = battle_state.enemies[0]
    
    # Drain MP
    shaman.stats.mp = 0
    battle_state.current_actor_id = shaman.instance_id
    
    # Run enemy turn
    events = service.run_enemy_turn(battle_state, state.rng)
    
    # Should fall back to basic attack
    assert any(isinstance(evt, AttackResolvedEvent) for evt in events)
    assert not any(isinstance(evt, SkillUsedEvent) for evt in events)


def test_rampager_aoe_usage_cap() -> None:
    """Test that Rampager AoE skill is capped at 2 uses per battle."""
    service = _make_battle_service()
    state = _make_state(seed=123, with_party=True)
    
    # Create battle with goblin_rampager
    battle_state, _ = service.start_battle("goblin_rampager", state)
    rampager = battle_state.enemies[0]
    
    # Ensure rampager has enough MP for 3+ uses (skill costs 8 MP)
    rampager.stats.mp = 30
    rampager.stats.max_mp = 30
    battle_state.current_actor_id = rampager.instance_id
    
    use_count = 0
    
    # Try to use skill multiple times
    for _ in range(5):
        if not rampager.is_alive or rampager.stats.mp < 8:
            break
        
        events = service.run_enemy_turn(battle_state, state.rng)
        
        if any(isinstance(evt, SkillUsedEvent) and evt.skill_id == "skill_rampager_cleave" for evt in events):
            use_count += 1
        
        # Reset for next turn (advance turn queue manually)
        battle_state.current_actor_id = rampager.instance_id
        
        # If we've seen 2 uses, next one should be basic attack
        if use_count == 2:
            # One more turn should NOT use the skill
            rampager.stats.mp = 30  # Give it MP
            events = service.run_enemy_turn(battle_state, state.rng)
            assert not any(isinstance(evt, SkillUsedEvent) and evt.skill_id == "skill_rampager_cleave" for evt in events)
            break
    
    # Should have used skill exactly 2 times
    assert use_count == 2


def test_rampager_aoe_cap_resets_per_battle() -> None:
    """Test that Rampager AoE usage cap resets in a fresh battle."""
    service = _make_battle_service()
    state = _make_state(seed=123, with_party=True)
    
    # First battle
    battle_a, _ = service.start_battle("goblin_rampager", state)
    rampager_a = battle_a.enemies[0]
    rampager_a.stats.mp = 30
    battle_a.current_actor_id = rampager_a.instance_id
    
    # Use skill twice
    for _ in range(2):
        events = service.run_enemy_turn(battle_a, state.rng)
        if not any(isinstance(evt, SkillUsedEvent) and evt.skill_id == "skill_rampager_cleave" for evt in events):
            break
        battle_a.current_actor_id = rampager_a.instance_id
        rampager_a.stats.mp = 30
    
    # Second battle (fresh)
    battle_b, _ = service.start_battle("goblin_rampager", state)
    rampager_b = battle_b.enemies[0]
    rampager_b.stats.mp = 30
    battle_b.current_actor_id = rampager_b.instance_id
    
    # Should be able to use skill again
    events = service.run_enemy_turn(battle_b, state.rng)
    assert any(isinstance(evt, SkillUsedEvent) and evt.skill_id == "skill_rampager_cleave" for evt in events)


def test_enemy_multi_target_selection_deterministic() -> None:
    """Test that multi-target enemy skills select targets deterministically."""
    service = _make_battle_service()
    state_a = _make_state(seed=999, with_party=True)
    state_b = _make_state(seed=999, with_party=True)
    
    # Create two identical battles
    battle_a, _ = service.start_battle("goblin_rampager", state_a)
    battle_b, _ = service.start_battle("goblin_rampager", state_b)
    
    rampager_a = battle_a.enemies[0]
    rampager_b = battle_b.enemies[0]
    
    rampager_a.stats.mp = 20
    rampager_b.stats.mp = 20
    
    battle_a.current_actor_id = rampager_a.instance_id
    battle_b.current_actor_id = rampager_b.instance_id
    
    # Set up specific aggro values to test deterministic ordering
    living_allies_a = [ally for ally in battle_a.allies if ally.is_alive]
    living_allies_b = [ally for ally in battle_b.allies if ally.is_alive]
    
    # Need at least 2 allies for multi-target
    assert len(living_allies_a) >= 2
    assert len(living_allies_b) >= 2
    
    # Set aggro in battle_a with different values to test sorting
    battle_a.enemy_aggro[rampager_a.instance_id] = {
        living_allies_a[0].instance_id: 100,
        living_allies_a[1].instance_id: 50,
    }
    
    # Set identical aggro in battle_b
    battle_b.enemy_aggro[rampager_b.instance_id] = {
        living_allies_b[0].instance_id: 100,
        living_allies_b[1].instance_id: 50,
    }
    
    # Run enemy turns
    events_a = service.run_enemy_turn(battle_a, state_a.rng)
    events_b = service.run_enemy_turn(battle_b, state_b.rng)
    
    # Extract skill events
    skill_events_a = [evt for evt in events_a if isinstance(evt, SkillUsedEvent)]
    skill_events_b = [evt for evt in events_b if isinstance(evt, SkillUsedEvent)]
    
    # Should have used the AoE skill
    assert len(skill_events_a) > 0
    assert len(skill_events_b) > 0
    
    # Targets should be identical (deterministic)
    targets_a = [evt.target_id for evt in skill_events_a]
    targets_b = [evt.target_id for evt in skill_events_b]
    assert targets_a == targets_b
    
    # Verify targets are sorted by aggro (highest first)
    # The target with 100 aggro should come before the target with 50 aggro
    if len(targets_a) >= 2:
        assert targets_a[0] == living_allies_a[0].instance_id  # highest aggro



def test_enemy_skill_selection_order() -> None:
    """Test that enemies iterate skills in order and pick first usable."""
    service = _make_battle_service()
    
    # Manually create a test enemy with multiple skills
    service._enemies_repo._ensure_loaded()  # type: ignore[attr-defined]
    from tbg.domain.defs.enemy_def import EnemyDef
    
    # Create test enemy with two skills, first costs too much MP
    service._enemies_repo._definitions["test_enemy_multi_skill"] = EnemyDef(  # type: ignore[attr-defined]
        id="test_enemy_multi_skill",
        name="Test Multi-Skill Enemy",
        hp=50,
        mp=5,
        attack=10,
        defense=2,
        speed=5,
        rewards_exp=10,
        rewards_gold=5,
        tags=("test",),
        weapon_ids=(),
        armour_slots={},
        enemy_skill_ids=("skill_hex_spark", "skill_savage_bite"),  # hex costs 2, bite costs 0
    )
    
    state = _make_state(seed=123)
    battle_state, _ = service.start_battle("test_enemy_multi_skill", state)
    enemy = battle_state.enemies[0]
    
    # Give just enough MP for the first skill
    enemy.stats.mp = 2
    battle_state.current_actor_id = enemy.instance_id
    
    # Should use first skill (skill_hex_spark) since it has enough MP
    events = service.run_enemy_turn(battle_state, state.rng)
    assert any(isinstance(evt, SkillUsedEvent) and evt.skill_id == "skill_hex_spark" for evt in events)



