from tbg.domain.battle_models import Combatant, is_summon, summon_owner_id
from tbg.domain.entities import Stats


def test_combatant_summon_metadata_fields() -> None:
    stats = Stats(max_hp=10, hp=10, max_mp=0, mp=0, attack=3, defense=1, speed=2)
    combatant = Combatant(
        instance_id="summon_1",
        display_name="Summon",
        side="allies",
        stats=stats,
        owner_id="player_1",
        bond_cost=5,
    )

    assert combatant.owner_id == "player_1"
    assert combatant.bond_cost == 5


def test_is_summon_false_for_normal_combatant() -> None:
    stats = Stats(max_hp=10, hp=10, max_mp=0, mp=0, attack=3, defense=1, speed=2)
    combatant = Combatant(instance_id="hero", display_name="Hero", side="allies", stats=stats)

    assert is_summon(combatant) is False
    assert summon_owner_id(combatant) is None


def test_is_summon_true_for_owned_combatant() -> None:
    stats = Stats(max_hp=10, hp=10, max_mp=0, mp=0, attack=3, defense=1, speed=2)
    combatant = Combatant(
        instance_id="summon_1",
        display_name="Summon",
        side="allies",
        stats=stats,
        owner_id="player_1",
    )

    assert is_summon(combatant) is True
    assert summon_owner_id(combatant) == "player_1"
