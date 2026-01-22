"""Factory for creating summon combatants from definitions."""
from __future__ import annotations

from tbg.core.rng import RNG
from tbg.data.repositories import SummonsRepository
from tbg.domain.battle_models import Combatant
from tbg.domain.entities import Stats
from tbg.domain.summon_scaling import scale_summon_stats
from tbg.services.factories.id_factory import make_instance_id
from tbg.services.errors import FactoryError


def create_summon_combatant(
    summon_id: str,
    *,
    summons_repo: SummonsRepository,
    owner_id: str,
    owner_bond: int,
    rng: RNG,
) -> Combatant:
    """Instantiate a summon combatant using the provided repository."""
    try:
        summon_def = summons_repo.get(summon_id)
    except KeyError as exc:
        raise FactoryError(f"Summon '{summon_id}' not found.") from exc

    base_stats = Stats(
        max_hp=summon_def.max_hp,
        hp=summon_def.max_hp,
        max_mp=summon_def.max_mp,
        mp=summon_def.max_mp,
        attack=summon_def.attack,
        defense=summon_def.defense,
        speed=summon_def.speed,
    )
    stats = scale_summon_stats(base_stats, owner_bond, summon_def.bond_scaling)
    instance_id = make_instance_id("summon", rng)
    tags = ("summon",) + summon_def.tags
    return Combatant(
        instance_id=instance_id,
        display_name=summon_def.name,
        side="allies",
        stats=stats,
        base_stats=base_stats,
        tags=tags,
        owner_id=owner_id,
        bond_cost=summon_def.bond_cost,
        source_id=summon_def.id,
    )
