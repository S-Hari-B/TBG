"""Factory for creating player entities from class definitions."""
from __future__ import annotations

from tbg.core.rng import RNG
from tbg.data.repositories import ArmourRepository, ClassesRepository, WeaponsRepository
from tbg.domain.entities import Equipment, Player, Stats
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

    stats = Stats(
        max_hp=class_def.base_hp,
        hp=class_def.base_hp,
        max_mp=class_def.base_mp,
        mp=class_def.base_mp,
        attack=weapon_def.attack,
        defense=armour_def.defense,
        speed=class_def.speed,
    )

    equipment = Equipment(weapon=weapon_def, armour=armour_def)
    player_id = make_instance_id("player", rng)
    extra_weapons = tuple(class_def.starting_weapons)
    return Player(
        id=player_id,
        name=name,
        class_id=class_id,
        stats=stats,
        equipment=equipment,
        extra_weapon_ids=extra_weapons,
    )


