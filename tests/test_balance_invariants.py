"""Invariant tests for balance targets and constraints post-30f.

These tests validate balance sanity bands and relationships, not exact numbers.
They should not fail due to routine tuning unless an explicit invariant is violated.
"""
from tbg.domain.attribute_scaling import INT_MP_PER_POINT, compute_action_attack
from tbg.domain.summon_scaling import scale_summon_stats
from tests.helpers.balance_asserts import (
    BASELINE_COMPANION_LEVEL_MAX,
    BASELINE_COMPANION_LEVEL_MIN,
    assert_in_range,
    get_class_def,
    get_enemy_def,
    get_item_def,
    get_party_member_def,
    get_skill_def,
    get_summon_def,
    get_weapon_def,
    kills_required,
)


def test_starter_classes_can_cast_core_skills_multiple_times() -> None:
    """All starter classes should have enough MP to cast their core low-cost skills at least 2 times."""
    # Warrior: should cast core skill multiple times
    warrior = get_class_def("warrior")
    power_slash = get_skill_def("skill_power_slash")
    warrior_mp = warrior.base_mp + (warrior.starting_attributes.INT * INT_MP_PER_POINT)
    assert (
        warrior_mp >= power_slash.mp_cost * 2
    ), f"Warrior MP {warrior_mp} should allow 2x Power Slash ({power_slash.mp_cost} MP each)"

    # Rogue: should cast core skill multiple times
    rogue = get_class_def("rogue")
    quick_stab = get_skill_def("skill_quick_stab")
    rogue_mp = rogue.base_mp + (rogue.starting_attributes.INT * INT_MP_PER_POINT)
    assert (
        rogue_mp >= quick_stab.mp_cost * 4
    ), f"Rogue MP {rogue_mp} should allow 4x Quick Stab ({quick_stab.mp_cost} MP each)"

    # Mage: should cast core skill multiple times
    mage = get_class_def("mage")
    firebolt = get_skill_def("skill_firebolt")
    mage_mp = mage.base_mp + (mage.starting_attributes.INT * INT_MP_PER_POINT)
    assert (
        mage_mp >= firebolt.mp_cost * 8
    ), f"Mage MP {mage_mp} should allow 8x Firebolt ({firebolt.mp_cost} MP each)"


def test_physical_skills_have_physical_tag_for_proper_scaling() -> None:
    """All physical damage skills must have 'physical' tag to ensure STR/DEX scaling."""
    physical_skills = [
        "skill_power_slash",
        "skill_quick_stab",
        "skill_backstab",
        "skill_skull_thump",
        "skill_piercing_thrust",
        "skill_sweeping_polearm",
        "skill_impale",
    ]

    for skill_id in physical_skills:
        skill = get_skill_def(skill_id)
        assert (
            "physical" in skill.tags
        ), f"Skill {skill_id} is a physical skill but missing 'physical' tag"


def test_magic_skills_have_elemental_tag_for_int_scaling() -> None:
    """All magic damage skills must have elemental tags to ensure INT scaling."""
    magic_skills = ["skill_firebolt", "skill_ember_wave"]

    for skill_id in magic_skills:
        skill = get_skill_def(skill_id)
        assert (
            "fire" in skill.tags
        ), f"Skill {skill_id} is a magic skill but missing 'fire' tag"


def test_starter_damage_above_minimum_vs_equal_level_trash() -> None:
    """Starter classes should do >1 damage vs equal-level trash enemies with baseline gear."""
    # Test warrior vs Goblin Grunt using current defs
    warrior = get_class_def("warrior")
    grunt = get_enemy_def("goblin_grunt")
    warrior_weapon = get_weapon_def(warrior.starting_weapon_id)
    warrior_atk = compute_action_attack(
        warrior_weapon.attack,
        warrior.starting_attributes,
        ["physical"],
        warrior_weapon.tags,
    )
    warrior_damage = max(1, warrior_atk - grunt.defense)

    # Should do more than minimal damage (avoid DEF floor)
    assert (
        warrior_damage > 2
    ), f"Warrior damage {warrior_damage} vs Goblin Grunt should be >2 to avoid DEF floor problems"

    # Test rogue finesse vs Goblin Grunt using current defs
    rogue = get_class_def("rogue")
    rogue_weapon = get_weapon_def(rogue.starting_weapon_id)
    rogue_atk = compute_action_attack(
        rogue_weapon.attack,
        rogue.starting_attributes,
        ["physical"],
        rogue_weapon.tags,
    )
    rogue_damage = max(1, rogue_atk - grunt.defense)

    assert (
        rogue_damage > 2
    ), f"Rogue damage {rogue_damage} vs Goblin Grunt should be >2"


def test_summon_throughput_bounded_by_bond_cost() -> None:
    """Summons should scale with BOND but not trivialize encounters."""
    from tbg.domain.entities import Stats

    beastmaster = get_class_def("beastmaster")
    raptor_def = get_summon_def("micro_raptor")

    # Should be able to summon at least two without external BOND buffs.
    bond = beastmaster.starting_attributes.BOND
    assert raptor_def.bond_cost > 0, "Summon bond cost should be positive"
    assert (
        bond >= raptor_def.bond_cost * 2
    ), f"Beastmaster BOND {bond} should allow 2x summon at cost {raptor_def.bond_cost}"

    # Scale raptor stats
    raptor_base = Stats(
        max_hp=raptor_def.max_hp,
        hp=raptor_def.max_hp,
        max_mp=raptor_def.max_mp,
        mp=raptor_def.max_mp,
        attack=raptor_def.attack,
        defense=raptor_def.defense,
        speed=raptor_def.speed,
    )
    raptor_scaled = scale_summon_stats(raptor_base, bond, raptor_def.bond_scaling)

    # With BOND 10 and atk_per_bond 0.8, Raptor ATK should be: 5 + (10 * 0.8) = 13
    expected_atk = raptor_def.attack + int(bond * raptor_def.bond_scaling.atk_per_bond)
    assert (
        raptor_scaled.attack == expected_atk
    ), f"Raptor ATK should be {expected_atk}, got {raptor_scaled.attack}"

    # 2 Raptors + Beastmaster personal ATK should be 2-3x warrior ATK
    warrior = get_class_def("warrior")
    warrior_weapon = get_weapon_def(warrior.starting_weapon_id)
    warrior_atk = compute_action_attack(
        warrior_weapon.attack,
        warrior.starting_attributes,
        ["physical"],
        warrior_weapon.tags,
    )
    total_party_atk = (
        raptor_scaled.attack * 2 + 6 + int(beastmaster.starting_attributes.DEX * 0.75)
    )

    # Total party output should be 2-3x solo warrior (bounded scaling)
    assert (
        total_party_atk >= warrior_atk * 2
    ), f"Beastmaster party ATK {total_party_atk} should be >= 2x warrior ATK {warrior_atk}"
    assert (
        total_party_atk <= warrior_atk * 3
    ), f"Beastmaster party ATK {total_party_atk} should be <= 3x warrior ATK {warrior_atk} to avoid trivializing"


def test_healing_potions_cover_reasonable_attrition() -> None:
    """Small HP Potion should heal 30-50% of lowest-HP class (rogue)."""
    hp_potion = get_item_def("potion_hp_small")
    rogue = get_class_def("rogue")

    # Rogue total HP: 32 base + (4 VIT * 3) + 4 armour bonus = 48
    rogue_total_hp = rogue.base_hp + (rogue.starting_attributes.VIT * 3) + 4

    heal_amount = hp_potion.heal_hp or 0
    heal_percent = (heal_amount / rogue_total_hp) * 100

    # Should heal 30-50% of rogue HP (balance target)
    assert (
        30 <= heal_percent <= 50
    ), f"Small HP Potion heals {heal_percent:.1f}% of rogue HP, should be 30-50%"


def test_mp_potions_restore_reasonable_percentage() -> None:
    """Small Energy Potion should restore ~25-35% of mage MP pool."""
    mp_potion = get_item_def("potion_energy_small")
    mage = get_class_def("mage")

    # Mage total MP: 18 base + (10 INT * 2) = 38
    mage_total_mp = mage.base_mp + (mage.starting_attributes.INT * INT_MP_PER_POINT)

    restore_amount = mp_potion.heal_mp or 0
    restore_percent = (restore_amount / mage_total_mp) * 100

    # Should restore 25-35% of mage MP (balance target)
    assert (
        25 <= restore_percent <= 35
    ), f"Small Energy Potion restores {restore_percent:.1f}% of mage MP, should be 25-35%"


def test_summon_item_price_prevents_early_rush_buy() -> None:
    """Summon items should cost enough to prevent rush-buying in first shop visit."""
    summon_item = get_item_def("summon_micro_raptor")
    grunt = get_enemy_def("goblin_grunt")

    # Summon should cost equivalent to a meaningful number of grunt kills.
    required_kills = kills_required(summon_item.value, grunt.rewards_gold)
    assert_in_range(
        required_kills,
        12,
        30,
        "Summon price kills required",
    )


def test_party_members_reflect_appropriate_level_scaling() -> None:
    """Emma and Niale are L1 baseline for floor_zero party play (as of Ticket 30g)."""
    emma = get_party_member_def("emma")
    niale = get_party_member_def("niale")
    mage = get_class_def("mage")
    rogue = get_class_def("rogue")

    assert_in_range(
        emma.starting_level,
        BASELINE_COMPANION_LEVEL_MIN,
        BASELINE_COMPANION_LEVEL_MAX,
        "Emma starting_level",
    )
    assert_in_range(
        niale.starting_level,
        BASELINE_COMPANION_LEVEL_MIN,
        BASELINE_COMPANION_LEVEL_MAX,
        "Niale starting_level",
    )

    # Companion base stats should not exceed their class baselines.
    max_hp_over_base = 4
    max_mp_over_base = 4
    assert (
        emma.base_hp <= mage.base_hp + max_hp_over_base
    ), f"Emma HP {emma.base_hp} should be <= mage baseline +{max_hp_over_base}"
    assert (
        emma.base_mp <= mage.base_mp + max_mp_over_base
    ), f"Emma MP {emma.base_mp} should be <= mage baseline +{max_mp_over_base}"

    assert (
        niale.base_hp <= rogue.base_hp + max_hp_over_base
    ), f"Niale HP {niale.base_hp} should be <= rogue baseline +{max_hp_over_base}"
    assert (
        niale.base_mp <= rogue.base_mp + max_mp_over_base
    ), f"Niale MP {niale.base_mp} should be <= rogue baseline +{max_mp_over_base}"


def test_low_cost_skills_are_modest_upgrades_over_basic_attacks() -> None:
    """Low-cost skills (2-3 MP) should have modest base_power (3-5) relative to basic attacks."""
    low_cost_skills = [
        ("skill_quick_stab", 2, 3),  # (id, mp_cost, expected_base_power_range)
        ("skill_power_slash", 3, 4),
        ("skill_skull_thump", 2, 4),
    ]

    for skill_id, expected_mp, _ in low_cost_skills:
        skill = get_skill_def(skill_id)
        assert (
            skill.mp_cost <= 3
        ), f"{skill_id} should be low-cost (MP <= 3), got {skill.mp_cost}"
        assert (
            3 <= skill.base_power <= 5
        ), f"{skill_id} base_power {skill.base_power} should be 3-5 (modest upgrade)"


def test_high_cost_skills_have_meaningful_power_spike() -> None:
    """High-cost skills (6-7 MP) should have high base_power (7-9) for meaningful burst."""
    high_cost_skills = [
        ("skill_ember_wave", 6, 7),  # (id, mp_cost, expected_base_power)
        ("skill_impale", 7, 9),
    ]

    for skill_id, expected_mp, expected_power in high_cost_skills:
        skill = get_skill_def(skill_id)
        assert (
            skill.mp_cost >= 6
        ), f"{skill_id} should be high-cost (MP >= 6), got {skill.mp_cost}"
        assert (
            skill.base_power >= 7
        ), f"{skill_id} base_power {skill.base_power} should be >= 7 (meaningful burst)"


def test_aoe_skills_have_reduced_per_target_power() -> None:
    """AOE skills should have lower base_power than single-target skills of similar MP cost."""
    # Ember Wave (6 MP, AOE 3 targets, base_power 7) vs Firebolt (4 MP, single, base_power 9)
    ember_wave = get_skill_def("skill_ember_wave")
    firebolt = get_skill_def("skill_firebolt")

    assert ember_wave.max_targets > firebolt.max_targets, "AOE should hit more targets"
    assert firebolt.max_targets >= 1, "Single-target skills should hit at least one target"

    # AOE should have lower base_power despite higher MP cost (trade power for coverage)
    assert (
        ember_wave.base_power < firebolt.base_power
    ), f"AOE skill {ember_wave.name} base_power {ember_wave.base_power} should be < single-target {firebolt.name} {firebolt.base_power}"


def test_skill_damage_projection_with_starter_gear() -> None:
    """Validate that skill damage projections align with design targets."""
    # Warrior Power Slash damage projection
    warrior = get_class_def("warrior")
    warrior_weapon = get_weapon_def(warrior.starting_weapon_id)
    power_slash = get_skill_def("skill_power_slash")
    grunt_def = get_enemy_def("goblin_grunt").defense

    warrior_action_atk = compute_action_attack(
        warrior_weapon.attack,
        warrior.starting_attributes,
        power_slash.tags,
        warrior_weapon.tags,
    )
    basic_damage = max(1, warrior_action_atk - grunt_def)
    skill_damage = max(1, warrior_action_atk + power_slash.base_power - grunt_def)
    assert (
        skill_damage >= basic_damage + 1
    ), f"Power Slash should beat basic attack (basic {basic_damage}, skill {skill_damage})"

    # Mage Firebolt damage projection
    mage = get_class_def("mage")
    mage_weapon = get_weapon_def(mage.starting_weapon_id)
    firebolt = get_skill_def("skill_firebolt")

    mage_action_atk = compute_action_attack(
        mage_weapon.attack,
        mage.starting_attributes,
        firebolt.tags,
        mage_weapon.tags,
    )
    mage_basic_damage = max(1, mage_action_atk - grunt_def)
    mage_skill_damage = max(1, mage_action_atk + firebolt.base_power - grunt_def)
    assert (
        mage_skill_damage >= mage_basic_damage + 1
    ), f"Firebolt should beat basic attack (basic {mage_basic_damage}, skill {mage_skill_damage})"


def test_debuff_items_have_meaningful_but_not_mandatory_impact() -> None:
    """Debuff items should provide meaningful bonuses without being mandatory for equal-level fights."""
    weakening_vial = get_item_def("weakening_vial")
    armor_sunder = get_item_def("armor_sunder_powder")
    grunt = get_enemy_def("goblin_grunt")

    debuff_atk = weakening_vial.debuff_attack_flat or 0
    assert debuff_atk >= 1, "Weakening Vial should reduce ATK by at least 1"
    atk_reduction_percent = (debuff_atk / max(1, grunt.attack)) * 100
    assert_in_range(
        atk_reduction_percent,
        10,
        60,
        "Weakening Vial ATK reduction %",
    )

    debuff_def = armor_sunder.debuff_defense_flat or 0
    assert debuff_def >= 1, "Armor Sunder should reduce DEF by at least 1"
    def_reduction_percent = (debuff_def / max(1, grunt.defense)) * 100
    assert_in_range(
        def_reduction_percent,
        25,
        300,
        "Armor Sunder DEF reduction %",
    )


def test_companion_starting_level_within_baseline_range() -> None:
    """Companion starting levels should stay within baseline bounds."""
    emma = get_party_member_def("emma")
    niale = get_party_member_def("niale")

    assert_in_range(
        emma.starting_level,
        BASELINE_COMPANION_LEVEL_MIN,
        BASELINE_COMPANION_LEVEL_MAX,
        "Emma starting_level",
    )
    assert_in_range(
        niale.starting_level,
        BASELINE_COMPANION_LEVEL_MIN,
        BASELINE_COMPANION_LEVEL_MAX,
        "Niale starting_level",
    )


def test_economy_gate_kills_required_computed_from_defs() -> None:
    """Economy gates should be computed from current defs, not hardcoded."""
    summon_item = get_item_def("summon_micro_raptor")
    grunt = get_enemy_def("goblin_grunt")

    required_kills = kills_required(summon_item.value, grunt.rewards_gold)
    assert_in_range(
        required_kills,
        12,
        30,
        "Summon price kills required",
    )
