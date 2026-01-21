"""Factory for creating player entities from class definitions."""
from __future__ import annotations

from tbg.core.rng import RNG
from tbg.data.repositories import ArmourRepository, ClassesRepository, WeaponsRepository
from tbg.domain.attribute_scaling import apply_attribute_scaling
from tbg.domain.entities import Attributes, BaseStats, Player, Stats
from tbg.services.errors import FactoryError

from .id_factory import make_instance_id


def create_player_from_class_id(
    class_id: str,
    name: str,
    classes_repo: ClassesRepository,
    weapons_repo: WeaponsRepository,
    armour_repo: ArmourRepository,
    rng: RNG,
) -> Player:
    """Instantiate a player using the provided repositories."""
    try:
        class_def = classes_repo.get(class_id)
    except KeyError as exc:
        raise FactoryError(f"Class '{class_id}' not found.") from exc

    try:
        weapon_def = weapons_repo.get(class_def.starting_weapon_id)
    except KeyError as exc:
        raise FactoryError(
            f"Weapon '{class_def.starting_weapon_id}' not found for class '{class_id}'."
        ) from exc

    try:
        armour_def = armour_repo.get(class_def.starting_armour_id)
    except KeyError as exc:
        raise FactoryError(
            f"Armour '{class_def.starting_armour_id}' not found for class '{class_id}'."
        ) from exc

    base_stats = BaseStats(
        max_hp=class_def.base_hp,
        max_mp=class_def.base_mp,
        attack=weapon_def.attack,
        defense=armour_def.defense,
        speed=class_def.speed,
    )
    attributes = Attributes(
        STR=class_def.starting_attributes.STR,
        DEX=class_def.starting_attributes.DEX,
        INT=class_def.starting_attributes.INT,
        VIT=class_def.starting_attributes.VIT,
        BOND=class_def.starting_attributes.BOND,
    )

    player_id = make_instance_id("player", rng)
    stats = apply_attribute_scaling(
        base_stats,
        attributes,
        current_hp=base_stats.max_hp,
        current_mp=base_stats.max_mp,
    )
    stats.hp = stats.max_hp
    stats.mp = stats.max_mp
    return Player(
        id=player_id,
        name=name,
        class_id=class_id,
        stats=stats,
        attributes=attributes,
        base_stats=base_stats,
    )




