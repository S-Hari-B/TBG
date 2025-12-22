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

    stats = Stats(
        max_hp=enemy_def.max_hp,
        hp=enemy_def.max_hp,
        max_mp=0,
        mp=0,
        attack=enemy_def.attack,
        defense=enemy_def.defense,
    )

    instance_id = make_instance_id("enemy", rng)
    return EnemyInstance(
        id=instance_id,
        enemy_id=enemy_def.id,
        name=enemy_def.name,
        stats=stats,
        xp_reward=enemy_def.xp,
        gold_reward=enemy_def.gold,
    )


