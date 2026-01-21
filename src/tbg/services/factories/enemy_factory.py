"""Factory for creating enemy instances from definitions."""
from __future__ import annotations

from tbg.core.rng import RNG
from tbg.data.repositories import ArmourRepository, EnemiesRepository, WeaponsRepository
from tbg.domain.enemy_scaling import scale_enemy_stats
from tbg.domain.defs import EnemyDef
from tbg.domain.entities import EnemyInstance, Stats
from tbg.services.errors import FactoryError

from .id_factory import make_instance_id


def create_enemy_instance(
    enemy_id: str,
    enemies_repo: EnemiesRepository,
    weapons_repo: WeaponsRepository,
    armour_repo: ArmourRepository,
    rng: RNG,
    *,
    battle_level: int | None = None,
) -> EnemyInstance:
    """Instantiate an enemy using the provided repository."""
    try:
        enemy_def = enemies_repo.get(enemy_id)
    except KeyError as exc:
        raise FactoryError(f"Enemy '{enemy_id}' not found.") from exc

    if enemy_def.enemy_ids:
        raise FactoryError(f"Enemy '{enemy_id}' is a group definition and cannot be instantiated directly.")

    assert (
        enemy_def.hp is not None
        and enemy_def.mp is not None
        and enemy_def.attack is not None
        and enemy_def.defense is not None
        and enemy_def.speed is not None
        and enemy_def.rewards_exp is not None
        and enemy_def.rewards_gold is not None
    ), f"Enemy definition '{enemy_id}' missing combat stats."

    weapon_attack = _resolve_weapon_attack(enemy_def.weapon_ids, weapons_repo)
    armour_defense = _resolve_armour_defense(enemy_def, armour_repo)

    base_stats = Stats(
        max_hp=enemy_def.hp,
        hp=enemy_def.hp,
        max_mp=enemy_def.mp,
        mp=enemy_def.mp,
        attack=enemy_def.attack + weapon_attack,
        defense=enemy_def.defense + armour_defense,
        speed=enemy_def.speed,
    )
    stats = base_stats
    if battle_level is not None:
        stats = scale_enemy_stats(base_stats, battle_level=battle_level)
        stats.hp = stats.max_hp
        stats.mp = stats.max_mp

    instance_id = make_instance_id("enemy", rng)
    return EnemyInstance(
        id=instance_id,
        enemy_id=enemy_def.id,
        name=enemy_def.name,
        stats=stats,
        base_stats=base_stats,
        xp_reward=enemy_def.rewards_exp,
        gold_reward=enemy_def.rewards_gold,
        tags=enemy_def.tags,
    )


def _resolve_weapon_attack(weapon_ids: tuple[str, ...], weapons_repo: WeaponsRepository) -> int:
    for weapon_id in weapon_ids:
        try:
            weapon_def = weapons_repo.get(weapon_id)
        except KeyError:
            continue
        return max(0, weapon_def.attack)
    return 0


def _resolve_armour_defense(enemy_def: EnemyDef, armour_repo: ArmourRepository) -> int:
    total = 0
    if enemy_def.armour_id:
        try:
            armour_def = armour_repo.get(enemy_def.armour_id)
        except KeyError:
            armour_def = None
        if armour_def:
            total += armour_def.defense
    for armour_id in enemy_def.armour_slots.values():
        try:
            armour_def = armour_repo.get(armour_id)
        except KeyError:
            continue
        total += armour_def.defense
    return total




