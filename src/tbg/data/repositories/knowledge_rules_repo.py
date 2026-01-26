"""Repository for knowledge progression rules."""
from __future__ import annotations

from typing import Dict

from tbg.data.errors import DataValidationError
from tbg.data.repositories.base import RepositoryBase
from tbg.domain.knowledge_models import (
    EnemyHpVisibilityMode,
    KnowledgeRules,
    KnowledgeThresholds,
    KnowledgeTier,
)


class KnowledgeRulesRepository(RepositoryBase[KnowledgeRules]):
    """Loads global knowledge progression rules."""

    def __init__(self, base_path=None) -> None:
        super().__init__("knowledge_rules.json", base_path)

    def _build(self, raw: dict[str, object]) -> Dict[str, KnowledgeRules]:
        thresholds_map = self._require_mapping(raw.get("thresholds"), "knowledge_rules.thresholds")
        tier1 = self._require_non_negative_int(
            thresholds_map.get("tier1_kills"), "knowledge_rules.thresholds.tier1_kills"
        )
        tier2 = self._require_non_negative_int(
            thresholds_map.get("tier2_kills"), "knowledge_rules.thresholds.tier2_kills"
        )
        tier3 = self._require_non_negative_int(
            thresholds_map.get("tier3_kills"), "knowledge_rules.thresholds.tier3_kills"
        )
        thresholds = KnowledgeThresholds(tier1_kills=tier1, tier2_kills=tier2, tier3_kills=tier3)

        visibility_map = self._require_mapping(
            raw.get("hp_visibility_by_tier"), "knowledge_rules.hp_visibility_by_tier"
        )
        hp_visibility: dict[KnowledgeTier, EnemyHpVisibilityMode] = {}
        for tier_key, mode_raw in visibility_map.items():
            tier = self._require_tier_key(tier_key, "knowledge_rules.hp_visibility_by_tier key")
            mode = self._require_visibility_mode(
                mode_raw, f"knowledge_rules.hp_visibility_by_tier[{tier.value}]"
            )
            hp_visibility[tier] = mode
        missing_tiers = {KnowledgeTier.TIER_0, KnowledgeTier.TIER_1, KnowledgeTier.TIER_2, KnowledgeTier.TIER_3} - set(
            hp_visibility.keys()
        )
        if missing_tiers:
            missing_values = sorted(tier.value for tier in missing_tiers)
            raise DataValidationError(
                f"knowledge_rules.hp_visibility_by_tier missing tiers: {missing_values}"
            )

        overrides_raw = raw.get("overrides", {})
        overrides_map = self._require_mapping(overrides_raw, "knowledge_rules.overrides")
        overrides = self._coerce_overrides(overrides_map)

        return {
            "rules": KnowledgeRules(
                thresholds=thresholds,
                hp_visibility_by_tier=hp_visibility,
                overrides=overrides,
            )
        }

    def get_rules(self) -> KnowledgeRules:
        self._ensure_loaded()
        assert self._definitions is not None
        return self._definitions["rules"]

    @staticmethod
    def _require_mapping(value: object, context: str) -> dict[str, object]:
        if not isinstance(value, dict):
            raise DataValidationError(f"{context} must be an object.")
        return value

    @staticmethod
    def _require_non_negative_int(value: object, context: str) -> int:
        if not isinstance(value, int):
            raise DataValidationError(f"{context} must be an integer.")
        if value < 0:
            raise DataValidationError(f"{context} must be non-negative.")
        return value

    @staticmethod
    def _require_tier_key(value: object, context: str) -> KnowledgeTier:
        tier_value: int | None = None
        if isinstance(value, int):
            tier_value = value
        elif isinstance(value, str) and value.isdigit():
            tier_value = int(value)
        if tier_value is None:
            raise DataValidationError(f"{context} must be an integer 0-3.")
        try:
            return KnowledgeTier(tier_value)
        except ValueError as exc:
            raise DataValidationError(f"{context} must be an integer 0-3.") from exc

    @staticmethod
    def _require_visibility_mode(value: object, context: str) -> EnemyHpVisibilityMode:
        if not isinstance(value, str):
            raise DataValidationError(f"{context} must be a string.")
        try:
            return EnemyHpVisibilityMode(value)
        except ValueError as exc:
            raise DataValidationError(f"{context} has invalid value '{value}'.") from exc

    @staticmethod
    def _coerce_overrides(overrides: dict[str, object]) -> dict[str, dict]:
        output: dict[str, dict] = {}
        for key, entry in overrides.items():
            if not isinstance(key, str):
                raise DataValidationError("knowledge_rules.overrides keys must be strings.")
            if not isinstance(entry, dict):
                raise DataValidationError(
                    f"knowledge_rules.overrides[{key}] must be an object."
                )
            output[key] = dict(entry)
        return output
