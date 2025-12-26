"""Factory for creating enemy instances from definitions."""
from __future__ import annotations

from tbg.core.rng import RNG
from tbg.data.repositories import EnemiesRepository
from tbg.domain.entities import EnemyInstance, Stats
from tbg.services.errors import FactoryError

from .id_factory import make_instance_id


def create_enemy_instance(
    enemy_id: str,
    enemies_repo: EnemiesRepository,
    rng: RNG,
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

    stats = Stats(
        max_hp=enemy_def.hp,
        hp=enemy_def.hp,
        max_mp=enemy_def.mp,
        mp=enemy_def.mp,
        attack=enemy_def.attack,
        defense=enemy_def.defense,
        speed=enemy_def.speed,
    )

    instance_id = make_instance_id("enemy", rng)
    return EnemyInstance(
        id=instance_id,
        enemy_id=enemy_def.id,
        name=enemy_def.name,
        stats=stats,
        xp_reward=enemy_def.rewards_exp,
        gold_reward=enemy_def.rewards_gold,
        tags=enemy_def.tags,
    )


