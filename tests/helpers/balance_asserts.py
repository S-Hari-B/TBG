from __future__ import annotations

from tbg.data.repositories import (
    ClassesRepository,
    EnemiesRepository,
    ItemsRepository,
    PartyMembersRepository,
    SkillsRepository,
    SummonsRepository,
    WeaponsRepository,
)

BASELINE_COMPANION_LEVEL_MIN = 1
BASELINE_COMPANION_LEVEL_MAX = 3

_classes_repo = ClassesRepository()
_enemies_repo = EnemiesRepository()
_items_repo = ItemsRepository()
_party_repo = PartyMembersRepository()
_skills_repo = SkillsRepository()
_summons_repo = SummonsRepository()
_weapons_repo = WeaponsRepository()


def get_class_def(class_id: str):
    return _classes_repo.get(class_id)


def get_enemy_def(enemy_id: str):
    return _enemies_repo.get(enemy_id)


def get_item_def(item_id: str):
    return _items_repo.get(item_id)


def get_party_member_def(member_id: str):
    return _party_repo.get(member_id)


def get_skill_def(skill_id: str):
    return _skills_repo.get(skill_id)


def get_summon_def(summon_id: str):
    return _summons_repo.get(summon_id)


def get_weapon_def(weapon_id: str):
    return _weapons_repo.get(weapon_id)


def assert_in_range(value: float, lo: float, hi: float, label: str) -> None:
    assert lo <= value <= hi, f"{label} {value} not in range {lo}-{hi}"


def kills_required(item_price: int, per_kill_gold: int) -> float:
    assert per_kill_gold > 0, "per_kill_gold must be > 0"
    return item_price / per_kill_gold
