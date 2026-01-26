"""Helpers for resolving knowledge keys."""
from __future__ import annotations

from tbg.domain.defs import EnemyDef


def resolve_enemy_knowledge_key(enemy_def: EnemyDef) -> str:
    """Return the stable knowledge key for an enemy definition."""
    return enemy_def.knowledge_key or enemy_def.id


def list_all_knowledge_keys(enemies_repo) -> list[str]:
    keys = {resolve_enemy_knowledge_key(enemy) for enemy in enemies_repo.all()}
    return sorted(keys)
