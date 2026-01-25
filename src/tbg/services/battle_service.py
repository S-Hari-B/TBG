"""Battle service handling deterministic combat."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

from tbg.core.rng import RNG
from tbg.data.repositories import (
    ArmourRepository,
    EnemiesRepository,
    FloorsRepository,
    ItemsRepository,
    KnowledgeRepository,
    LootTablesRepository,
    LocationsRepository,
    PartyMembersRepository,
    SkillsRepository,
    SummonsRepository,
    WeaponsRepository,
)
from tbg.domain.battle_models import BattleCombatantView, BattleState, Combatant
from tbg.domain.defs import ItemDef, KnowledgeEntry, LootTableDef, SkillDef
from tbg.domain.attribute_scaling import apply_attribute_scaling
from tbg.domain.enemy_scaling import (
    ATTACK_PER_LEVEL,
    DEFENSE_PER_LEVEL,
    HP_PER_LEVEL,
    SPEED_PER_LEVEL,
)
from tbg.domain.debuffs import (
    ActiveDebuff,
    apply_debuff_no_stack,
    compute_effective_attack,
    compute_effective_defense,
)
from tbg.domain.item_effects import apply_item_effects
from tbg.domain.entities import Attributes, BaseStats, Stats
from tbg.domain.inventory import ARMOUR_SLOTS, MemberEquipment
from tbg.domain.state import GameState
from tbg.services.errors import FactoryError
from tbg.services.factories import create_enemy_instance, create_summon_combatant, make_instance_id
from tbg.services.quest_service import QuestService

ANTI_REPEAT_MULTIPLIER = 0.8  # Reduce threat for repeat targets when eligible.
ANTI_REPEAT_IGNORE_GAP = 10  # Ignore repeat penalty if top threat exceeds runner-up by this amount.
AGGRO_BASE_DIVISOR = 5  # Smaller base seed so damage quickly dominates.
AGGRO_HIT_BONUS = 2  # Flat bonus so low-damage hits still build aggro.


@dataclass(slots=True)
class BattleView:
    """Presentation view for the current battle state."""

    battle_id: str
    allies: List[BattleCombatantView]
    enemies: List[BattleCombatantView]
    current_actor_id: str | None


@dataclass(slots=True)
class BattleInventoryItem:
    """Lightweight view of a consumable item available during battle."""

    item_id: str
    item_name: str
    quantity: int
    targeting: str


@dataclass(slots=True)
class BattleEvent:
    """Base battle event."""


@dataclass(slots=True)
class BattleStartedEvent(BattleEvent):
    battle_id: str
    enemy_names: List[str]
    battle_level: int | None = None
    level_source: str | None = None
    level_source_value: int | None = None
    location_id: str | None = None
    floor_id: str | None = None
    scaling_hp_per_level: int | None = None
    scaling_attack_per_level: int | None = None
    scaling_defense_per_level: int | None = None
    scaling_speed_per_level: int | None = None


@dataclass(slots=True)
class EnemyTargetingDebugEvent(BattleEvent):
    attacker_id: str
    attacker_name: str
    target_id: str
    target_name: str
    top_value: int
    anti_repeat_applied: bool


@dataclass(slots=True)
class SummonSpawnedEvent(BattleEvent):
    owner_id: str
    summon_id: str
    summon_instance_id: str
    summon_name: str
    bond_cost: int | None = None
    owner_bond: int | None = None
    base_stats: Stats | None = None
    scaled_stats: Stats | None = None


@dataclass(slots=True)
class SummonAutoSpawnDebugEvent(BattleEvent):
    bond_capacity: int
    equipped_summons: List[str]
    decisions: List[tuple[str, int, bool]]


@dataclass(slots=True)
class BattleLevelInfo:
    level: int
    source: str
    source_value: int | None
    location_id: str | None
    floor_id: str | None


@dataclass(slots=True)
class AttackResolvedEvent(BattleEvent):
    attacker_id: str
    attacker_name: str
    target_id: str
    target_name: str
    damage: int
    target_hp: int


@dataclass(slots=True)
class CombatantDefeatedEvent(BattleEvent):
    combatant_id: str
    combatant_name: str


@dataclass(slots=True)
class PartyTalkEvent(BattleEvent):
    speaker_id: str
    speaker_name: str
    text: str


@dataclass(slots=True)
class BattleResolvedEvent(BattleEvent):
    victor: str


@dataclass(slots=True)
class SkillUsedEvent(BattleEvent):
    attacker_id: str
    attacker_name: str
    skill_id: str
    skill_name: str
    target_id: str
    target_name: str
    damage: int
    target_hp: int


@dataclass(slots=True)
class GuardAppliedEvent(BattleEvent):
    combatant_id: str
    combatant_name: str
    amount: int


@dataclass(slots=True)
class SkillFailedEvent(BattleEvent):
    combatant_id: str
    combatant_name: str
    reason: str


@dataclass(slots=True)
class ItemUsedEvent(BattleEvent):
    user_id: str
    user_name: str
    target_id: str
    target_name: str
    item_id: str
    item_name: str
    hp_delta: int
    mp_delta: int
    energy_delta: int
    result_text: str | None = None


@dataclass(slots=True)
class DebuffAppliedEvent(BattleEvent):
    target_id: str
    target_name: str
    debuff_type: str
    amount: int


@dataclass(slots=True)
class DebuffExpiredEvent(BattleEvent):
    target_id: str
    target_name: str
    debuff_type: str


@dataclass(slots=True)
class BattleRewardsHeaderEvent(BattleEvent):
    pass


@dataclass(slots=True)
class BattleGoldRewardEvent(BattleEvent):
    amount: int
    total_gold: int


@dataclass(slots=True)
class BattleExpRewardEvent(BattleEvent):
    member_id: str
    member_name: str
    amount: int
    new_level: int


@dataclass(slots=True)
class BattleLevelUpEvent(BattleEvent):
    member_id: str
    member_name: str
    new_level: int


@dataclass(slots=True)
class LootAcquiredEvent(BattleEvent):
    item_id: str
    item_name: str
    quantity: int


class BattleService:
    """Deterministic battle orchestrator supporting basic attacks and party talk."""

    def __init__(
        self,
        enemies_repo: EnemiesRepository,
        party_members_repo: PartyMembersRepository,
        knowledge_repo: KnowledgeRepository,
        weapons_repo: WeaponsRepository,
        armour_repo: ArmourRepository,
        skills_repo: SkillsRepository,
        items_repo: ItemsRepository,
        loot_tables_repo: LootTablesRepository,
        summons_repo: SummonsRepository | None = None,
        floors_repo: FloorsRepository | None = None,
        locations_repo: LocationsRepository | None = None,
        quest_service: QuestService | None = None,
    ) -> None:
        self._enemies_repo = enemies_repo
        self._party_members_repo = party_members_repo
        self._knowledge_repo = knowledge_repo
        self._weapons_repo = weapons_repo
        self._armour_repo = armour_repo
        self._skills_repo = skills_repo
        self._items_repo = items_repo
        self._loot_tables_repo = loot_tables_repo
        self._loot_tables_cache: List[LootTableDef] | None = None
        self._summons_repo = summons_repo or SummonsRepository()
        self._floors_repo = floors_repo
        self._locations_repo = locations_repo
        self._quest_service = quest_service

    # -----------------------
    # Battle Lifecycle
    # -----------------------
    def start_battle(self, enemy_id: str, state: GameState) -> tuple[BattleState, List[BattleEvent]]:
        """Instantiate a battle against the requested enemy or group."""
        if state.player is None:
            raise FactoryError("Cannot start battle before a class has been chosen.")

        try:
            self._enemies_repo.get(enemy_id)
            enemy_ids = [enemy_id]
        except KeyError:
            group_def = self._enemies_repo.get_group(enemy_id)
            enemy_ids = list(group_def.enemy_ids or [])

        battle_level_info = self._resolve_battle_level(state)
        enemies: List[Combatant] = []
        for _id in enemy_ids:
            enemy_instance = create_enemy_instance(
                _id,
                enemies_repo=self._enemies_repo,
                weapons_repo=self._weapons_repo,
                armour_repo=self._armour_repo,
                rng=state.rng,
                battle_level=battle_level_info.level,
            )
            enemies.append(
                Combatant(
                    instance_id=enemy_instance.id,
                    display_name=enemy_instance.name,
                    side="enemies",
                    stats=enemy_instance.stats,
                    base_stats=enemy_instance.base_stats,
                    tags=enemy_instance.tags,
                    weapon_tags=(),
                    source_id=enemy_instance.enemy_id,
                )
            )

        self._ensure_unique_enemy_instances(enemies, state.rng)
        self._disambiguate_enemy_names(enemies)
        allies = [self._player_to_combatant(state)]
        for member_id in state.party_members:
            allies.append(self._party_member_to_combatant(member_id, state))

        battle_id = make_instance_id("battle", state.rng)
        player_id = state.player.id if state.player else None
        battle_state = BattleState(battle_id=battle_id, allies=allies, enemies=enemies, player_id=player_id)

        events = [
            BattleStartedEvent(
                battle_id=battle_id,
                enemy_names=[enemy.display_name for enemy in enemies],
                battle_level=battle_level_info.level,
                level_source=battle_level_info.source,
                level_source_value=battle_level_info.source_value,
                location_id=battle_level_info.location_id,
                floor_id=battle_level_info.floor_id,
                scaling_hp_per_level=HP_PER_LEVEL,
                scaling_attack_per_level=ATTACK_PER_LEVEL,
                scaling_defense_per_level=DEFENSE_PER_LEVEL,
                scaling_speed_per_level=SPEED_PER_LEVEL,
            )
        ]
        events.extend(self._auto_spawn_equipped_summons(state, battle_state))
        self._initialize_enemy_aggro(battle_state)
        self._initialize_party_threat(battle_state)
        self._rebuild_turn_queue(battle_state)
        if battle_state.turn_queue:
            battle_state.current_actor_id = battle_state.turn_queue[0]
            battle_state.round_last_actor_id = battle_state.turn_queue[-1]
        else:
            battle_state.round_last_actor_id = None
        return battle_state, events

    def _auto_spawn_equipped_summons(
        self,
        state: GameState,
        battle_state: BattleState,
    ) -> List[BattleEvent]:
        owners = self._summon_spawn_owners(state)
        if not owners:
            return []
        events: List[BattleEvent] = []
        for owner_id, owner_key, equipped in owners:
            remaining = self._resolve_owner_bond(state, owner_key)
            if remaining <= 0 or not equipped:
                continue
            decisions: List[tuple[str, int, bool]] = []
            for summon_id in equipped:
                summon_def = self._summons_repo.get(summon_id)
                if summon_def.bond_cost > remaining:
                    decisions.append((summon_id, summon_def.bond_cost, False))
                    break
                events.extend(
                    self._spawn_summon_into_battle(
                        state,
                        battle_state,
                        owner_id=owner_id,
                        owner_bond=self._resolve_owner_bond(state, owner_key),
                        summon_id=summon_id,
                    )
                )
                decisions.append((summon_id, summon_def.bond_cost, True))
                remaining -= summon_def.bond_cost
            events.append(
                SummonAutoSpawnDebugEvent(
                    bond_capacity=self._resolve_owner_bond(state, owner_key),
                    equipped_summons=list(equipped),
                    decisions=decisions,
                )
            )
        return events

    def _spawn_summon_into_battle(
        self,
        state: GameState,
        battle_state: BattleState,
        owner_id: str,
        owner_bond: int,
        summon_id: str,
    ) -> List[BattleEvent]:
        if not any(ally.instance_id == owner_id for ally in battle_state.allies):
            raise ValueError(f"Summon owner '{owner_id}' not found among allies.")

        summon = create_summon_combatant(
            summon_id,
            summons_repo=self._summons_repo,
            owner_id=owner_id,
            owner_bond=owner_bond,
            rng=state.rng,
        )
        battle_state.allies.append(summon)
        self._seed_aggro_for_ally(battle_state, summon)
        self._seed_party_threat_for_ally(battle_state, summon)
        self._rebuild_turn_queue(battle_state)
        return [
            SummonSpawnedEvent(
                owner_id=owner_id,
                summon_id=summon_id,
                summon_instance_id=summon.instance_id,
                summon_name=summon.display_name,
                bond_cost=summon.bond_cost,
                owner_bond=owner_bond,
                base_stats=summon.base_stats,
                scaled_stats=summon.stats,
            )
        ]

    def _resolve_owner_bond(self, state: GameState, owner_key: str) -> int:
        if state.player and state.player.id == owner_key:
            return state.player.attributes.BOND
        return state.party_member_attributes.get(
            owner_key, Attributes(STR=0, DEX=0, INT=0, VIT=0, BOND=0)
        ).BOND

    def _summon_spawn_owners(self, state: GameState) -> List[tuple[str, str, List[str]]]:
        owners: List[tuple[str, str, List[str]]] = []
        if state.player:
            owners.append((state.player.id, state.player.id, list(state.player.equipped_summons)))
        for member_id in state.party_members:
            loadout = list(state.party_member_summon_loadouts.get(member_id, []))
            if not loadout:
                owners.append((f"party_{member_id}", member_id, []))
                continue
            owners.append((f"party_{member_id}", member_id, loadout))
        return owners

    def _resolve_battle_level(self, state: GameState) -> BattleLevelInfo:
        if not state.current_location_id or not self._locations_repo or not self._floors_repo:
            return BattleLevelInfo(
                level=0,
                source="default",
                source_value=None,
                location_id=state.current_location_id or None,
                floor_id=None,
            )
        try:
            location_def = self._locations_repo.get(state.current_location_id)
        except KeyError:
            return BattleLevelInfo(
                level=0,
                source="default",
                source_value=None,
                location_id=state.current_location_id or None,
                floor_id=None,
            )
        if location_def.area_level is not None:
            return BattleLevelInfo(
                level=max(0, location_def.area_level),
                source="area_level",
                source_value=location_def.area_level,
                location_id=location_def.id,
                floor_id=location_def.floor_id,
            )
        try:
            floor_def = self._floors_repo.get(location_def.floor_id)
        except KeyError:
            return BattleLevelInfo(
                level=0,
                source="default",
                source_value=None,
                location_id=location_def.id,
                floor_id=location_def.floor_id,
            )
        return BattleLevelInfo(
            level=max(0, floor_def.level),
            source="floor_level",
            source_value=floor_def.level,
            location_id=location_def.id,
            floor_id=floor_def.id,
        )

    def get_battle_view(self, battle_state: BattleState) -> BattleView:
        """Return structured information for rendering."""
        return BattleView(
            battle_id=battle_state.battle_id,
            allies=[self._to_view(ally, hide_hp=False) for ally in battle_state.allies],
            enemies=[self._to_view(enemy, hide_hp=True) for enemy in battle_state.enemies],
            current_actor_id=battle_state.current_actor_id,
        )

    def get_battle_items(self, state: GameState) -> List[BattleInventoryItem]:
        """List consumable inventory entries available for battle."""
        entries: List[BattleInventoryItem] = []
        for item_id, quantity in sorted(state.inventory.items.items()):
            if quantity <= 0:
                continue
            try:
                item_def = self._items_repo.get(item_id)
            except KeyError:
                continue
            if item_def.kind != "consumable":
                continue
            entries.append(
                BattleInventoryItem(
                    item_id=item_id,
                    item_name=item_def.name,
                    quantity=quantity,
                    targeting=item_def.targeting,
                )
            )
        return entries

    # -----------------------
    # Player Actions
    # -----------------------
    def basic_attack(self, battle_state: BattleState, attacker_id: str, target_id: str) -> List[BattleEvent]:
        attacker = self._get_combatant(battle_state, attacker_id)
        target = self._get_combatant(battle_state, target_id)
        damage, debuff_events = self._resolve_damage(
            battle_state, attacker, target, bonus_power=0, minimum=1
        )

        events: List[BattleEvent] = [
            AttackResolvedEvent(
                attacker_id=attacker.instance_id,
                attacker_name=attacker.display_name,
                target_id=target.instance_id,
                target_name=target.display_name,
                damage=damage,
                target_hp=target.stats.hp,
            )
        ]
        events.extend(debuff_events)
        if not target.is_alive:
            events.append(CombatantDefeatedEvent(combatant_id=target.instance_id, combatant_name=target.display_name))

        player_defeat_event = self._check_player_defeat(battle_state)
        if player_defeat_event:
            events.append(player_defeat_event)
            return events

        maybe_resolved = self._update_victory(battle_state)
        if maybe_resolved:
            events.append(maybe_resolved)
        else:
            round_events = self._advance_turn(battle_state, attacker.instance_id)
            events.extend(round_events)
        return events

    def get_available_skills(self, battle_state: BattleState, combatant_id: str) -> List[SkillDef]:
        combatant = self._get_combatant(battle_state, combatant_id)
        if not combatant.weapon_tags:
            return []
        available: List[SkillDef] = []
        for skill in self._skills_repo.all():
            if set(skill.required_weapon_tags).issubset(set(combatant.weapon_tags)):
                available.append(skill)
        return available

    def use_skill(
        self, battle_state: BattleState, attacker_id: str, skill_id: str, target_ids: Sequence[str]
    ) -> List[BattleEvent]:
        attacker = self._get_combatant(battle_state, attacker_id)
        skill = self._skills_repo.get(skill_id)
        if attacker.stats.mp < skill.mp_cost:
            return [
                SkillFailedEvent(
                    combatant_id=attacker.instance_id,
                    combatant_name=attacker.display_name,
                    reason="insufficient_mp",
                )
            ]

        resolved_targets = self._resolve_skill_targets(battle_state, attacker, skill, target_ids)

        events: List[BattleEvent] = []
        attacker.stats.mp -= skill.mp_cost

        if skill.effect_type == "damage":
            for target in resolved_targets:
                damage, debuff_events = self._resolve_damage(
                    battle_state, attacker, target, bonus_power=skill.base_power, minimum=1
                )
                events.append(
                    SkillUsedEvent(
                        attacker_id=attacker.instance_id,
                        attacker_name=attacker.display_name,
                        skill_id=skill.id,
                        skill_name=skill.name,
                        target_id=target.instance_id,
                        target_name=target.display_name,
                        damage=damage,
                        target_hp=target.stats.hp,
                    )
                )
                events.extend(debuff_events)
                if not target.is_alive:
                    events.append(
                        CombatantDefeatedEvent(combatant_id=target.instance_id, combatant_name=target.display_name)
                    )
                player_defeat_event = self._check_player_defeat(battle_state)
                if player_defeat_event:
                    events.append(player_defeat_event)
                    return events
        elif skill.effect_type == "guard":
            attacker.guard_reduction = skill.base_power
            events.append(
                GuardAppliedEvent(
                    combatant_id=attacker.instance_id,
                    combatant_name=attacker.display_name,
                    amount=skill.base_power,
                )
            )

        maybe_resolved = self._update_victory(battle_state)
        if maybe_resolved:
            events.append(maybe_resolved)
        else:
            round_events = self._advance_turn(battle_state, attacker.instance_id)
            events.extend(round_events)
        return events

    def party_talk(self, battle_state: BattleState, speaker_id: str, rng: RNG) -> List[BattleEvent]:
        speaker = self._get_combatant(battle_state, speaker_id)
        source_id = speaker.source_id or speaker.instance_id
        text = self._build_party_talk_text(source_id, speaker.display_name, battle_state, rng)
        events = [PartyTalkEvent(speaker_id=speaker.instance_id, speaker_name=speaker.display_name, text=text)]
        events.extend(self._advance_turn(battle_state, speaker.instance_id))
        return events
    def _apply_debuff_item(
        self,
        *,
        battle_state: BattleState,
        actor: Combatant,
        target: Combatant,
        item_def: ItemDef,
    ) -> List[BattleEvent]:
        if target.side != "enemies":
            raise ValueError("target_not_enemy")

        debuff_type = "attack_down" if item_def.debuff_attack_flat > 0 else "defense_down"
        amount = item_def.debuff_attack_flat or item_def.debuff_defense_flat
        expires_at_round = battle_state.round_index + 2
        applied = apply_debuff_no_stack(
            target.debuffs,
            debuff_type=debuff_type,
            amount=amount,
            expires_at_round=expires_at_round,
        )

        description = self._describe_debuff_text(debuff_type, amount)
        events: List[BattleEvent] = [
            ItemUsedEvent(
                user_id=actor.instance_id,
                user_name=actor.display_name,
                target_id=target.instance_id,
                target_name=target.display_name,
                item_id=item_def.id,
                item_name=item_def.name,
                hp_delta=0,
                mp_delta=0,
                energy_delta=0,
                result_text=(
                    f"{actor.display_name} uses {item_def.name} on {target.display_name}: {description}"
                    if applied
                    else f"{actor.display_name} uses {item_def.name} on {target.display_name}: had no effect."
                ),
            )
        ]

        if applied:
            events.append(
                DebuffAppliedEvent(
                    target_id=target.instance_id,
                    target_name=target.display_name,
                    debuff_type=debuff_type,
                    amount=amount,
                )
            )
        return events

    def use_item(
        self,
        battle_state: BattleState,
        state: GameState,
        actor_id: str,
        item_id: str,
        target_id: str,
    ) -> List[BattleEvent]:
        actor = self._get_combatant(battle_state, actor_id)
        target = self._get_combatant(battle_state, target_id)
        if not target.is_alive:
            raise ValueError("target_not_alive")

        try:
            item_def = self._items_repo.get(item_id)
        except KeyError as exc:
            raise ValueError("unknown_item") from exc

        if item_def.kind != "consumable":
            raise ValueError("item_not_consumable")

        targeting = item_def.targeting
        is_debuff_item = item_def.debuff_attack_flat > 0 or item_def.debuff_defense_flat > 0
        if targeting == "enemy" and not is_debuff_item:
            raise ValueError("targeting_not_supported")

        if targeting == "self" and actor.instance_id != target.instance_id:
            raise ValueError("target_not_allowed")
        if targeting == "ally" and target.side != actor.side:
            raise ValueError("invalid_target_side")
        if targeting == "enemy" and target.side != "enemies":
            raise ValueError("invalid_target_side")
        if targeting not in {"self", "ally", "enemy"}:
            raise ValueError("targeting_not_supported")

        if not state.inventory.remove_item(item_id, 1):
            raise ValueError("item_not_available")

        events: List[BattleEvent] = []

        if is_debuff_item:
            events.extend(
                self._apply_debuff_item(
                    battle_state=battle_state,
                    actor=actor,
                    target=target,
                    item_def=item_def,
                )
            )
        else:
            effect = apply_item_effects(target.stats, item_def)
            events.append(
                ItemUsedEvent(
                    user_id=actor.instance_id,
                    user_name=actor.display_name,
                    target_id=target.instance_id,
                    target_name=target.display_name,
                    item_id=item_def.id,
                    item_name=item_def.name,
                    hp_delta=effect.hp_delta,
                    mp_delta=effect.mp_delta,
                    energy_delta=effect.energy_delta,
                )
            )

        self._advance_turn(battle_state, actor.instance_id)
        return events

    # -----------------------
    # Enemy AI
    # -----------------------
    def run_enemy_turn(self, battle_state: BattleState, rng: RNG) -> List[BattleEvent]:
        actor = self._get_combatant(battle_state, battle_state.current_actor_id or "")
        living_allies = [ally for ally in battle_state.allies if ally.is_alive]
        if not living_allies:
            return self._finalize_defeat(battle_state)
        target, anti_repeat_applied = self._select_enemy_target(battle_state, actor, living_allies, rng)
        aggro_value = battle_state.enemy_aggro.get(actor.instance_id, {}).get(target.instance_id, 0)
        events = self.basic_attack(battle_state, actor.instance_id, target.instance_id)
        debug_event = EnemyTargetingDebugEvent(
            attacker_id=actor.instance_id,
            attacker_name=actor.display_name,
            target_id=target.instance_id,
            target_name=target.display_name,
            top_value=aggro_value,
            anti_repeat_applied=anti_repeat_applied,
        )
        return [debug_event, *events]

    def run_ally_ai_turn(self, battle_state: BattleState, actor_id: str, rng: RNG) -> List[BattleEvent]:
        actor = self._get_combatant(battle_state, actor_id)
        living_enemies = [enemy for enemy in battle_state.enemies if enemy.is_alive]
        if not living_enemies:
            return []

        available_skills = self.get_available_skills(battle_state, actor_id)
        for skill in available_skills:
            if actor.stats.mp < skill.mp_cost:
                continue
            target_ids = self._select_ai_skill_targets(battle_state, skill, actor, living_enemies, rng)
            if target_ids is None:
                continue
            return self.use_skill(battle_state, actor_id, skill.id, target_ids)

        target = self._select_party_target(battle_state, actor, living_enemies, rng)
        return self.basic_attack(battle_state, actor_id, target.instance_id)

    def _select_ai_skill_targets(
        self,
        battle_state: BattleState,
        skill: SkillDef,
        actor: Combatant,
        living_enemies: List[Combatant],
        rng: RNG,
    ) -> List[str] | None:
        if skill.target_mode == "self":
            return []
        if not living_enemies:
            return None
        if skill.target_mode == "single_enemy":
            target = self._select_party_target(battle_state, actor, living_enemies, rng)
            return [target.instance_id]
        if skill.target_mode == "multi_enemy":
            if len(living_enemies) < 2:
                return None
            ordered = self._order_enemies_by_party_threat(battle_state, actor, living_enemies, rng)
            targets = [enemy.instance_id for enemy in ordered[: skill.max_targets]]
            return targets if len(targets) >= 2 else None
        return None

    # -----------------------
    # Helpers
    # -----------------------
    def _player_to_combatant(self, state: GameState) -> Combatant:
        assert state.player is not None
        equipment = state.equipment.get(state.player.id)
        weapon_ids = self._weapon_ids_from_equipment(equipment)
        armour_ids = self._armour_ids_from_equipment(equipment)
        base_stats = BaseStats(
            max_hp=state.player.base_stats.max_hp,
            max_mp=state.player.base_stats.max_mp,
            attack=self._calculate_attack(weapon_ids, state.player.base_stats.attack),
            defense=self._calculate_defense(armour_ids, state.player.base_stats.defense),
            speed=state.player.base_stats.speed,
        )
        state.player.base_stats = base_stats
        state.player.stats = apply_attribute_scaling(
            base_stats,
            state.player.attributes,
            current_hp=state.player.stats.hp,
            current_mp=state.player.stats.mp,
        )
        return Combatant(
            instance_id=state.player.id,
            display_name=state.player.name,
            side="allies",
            stats=state.player.stats,
            tags=(),
            weapon_tags=self._weapon_tags_for_ids(weapon_ids),
            source_id=state.player.class_id,
        )

    def _party_member_to_combatant(self, member_id: str, state: GameState) -> Combatant:
        member_def = self._party_members_repo.get(member_id)
        equipment = state.equipment.get(member_id)
        weapon_ids = self._weapon_ids_from_equipment(equipment)
        armour_ids = self._armour_ids_from_equipment(equipment)
        if not weapon_ids:
            weapon_ids = list(member_def.weapon_ids[:2])
        if not armour_ids and member_def.armour_slots:
            armour_ids = list(member_def.armour_slots.values())
        base_attack = 1
        if member_def.weapon_ids:
            try:
                base_attack = self._weapons_repo.get(member_def.weapon_ids[0]).attack
            except KeyError:
                base_attack = 1
        base_defense = 0
        base_stats = BaseStats(
            max_hp=member_def.base_hp,
            max_mp=member_def.base_mp,
            attack=self._calculate_attack(weapon_ids, base_attack),
            defense=self._calculate_defense(armour_ids, base_defense),
            speed=member_def.speed,
        )
        attributes = state.party_member_attributes.get(member_id, member_def.starting_attributes)
        stats = apply_attribute_scaling(
            base_stats,
            attributes,
            current_hp=base_stats.max_hp,
            current_mp=base_stats.max_mp,
        )
        stats.hp = stats.max_hp
        stats.mp = stats.max_mp
        return Combatant(
            instance_id=f"party_{member_id}",
            display_name=member_def.name,
            side="allies",
            stats=stats,
            tags=member_def.tags,
            weapon_tags=self._weapon_tags_for_ids(weapon_ids),
            source_id=member_id,
        )

    def _get_combatant(self, battle_state: BattleState, combatant_id: str) -> Combatant:
        for combatant in self._iter_combatants(battle_state):
            if combatant.instance_id == combatant_id:
                return combatant
        raise ValueError(f"Combatant '{combatant_id}' not found.")

    def _iter_combatants(self, battle_state: BattleState) -> Iterable[Combatant]:
        yield from battle_state.allies
        yield from battle_state.enemies

    def _initialize_enemy_aggro(self, battle_state: BattleState) -> None:
        battle_state.enemy_aggro = {}
        battle_state.last_target = {}
        living_allies = [ally for ally in battle_state.allies if ally.is_alive]
        for enemy in battle_state.enemies:
            aggro_map: Dict[str, int] = {}
            for ally in living_allies:
                aggro_map[ally.instance_id] = self._base_threat_for_target(ally)
            battle_state.enemy_aggro[enemy.instance_id] = aggro_map
            battle_state.last_target[enemy.instance_id] = None

    def _initialize_party_threat(self, battle_state: BattleState) -> None:
        battle_state.party_threat = {}
        living_enemies = [enemy for enemy in battle_state.enemies if enemy.is_alive]
        for ally in battle_state.allies:
            threat_map: Dict[str, int] = {}
            for enemy in living_enemies:
                threat_map[enemy.instance_id] = self._base_threat_for_target(enemy)
            battle_state.party_threat[ally.instance_id] = threat_map

    def _seed_aggro_for_ally(self, battle_state: BattleState, ally: Combatant) -> None:
        for enemy in battle_state.enemies:
            aggro_map = battle_state.enemy_aggro.setdefault(enemy.instance_id, {})
            aggro_map.setdefault(ally.instance_id, self._base_threat_for_target(ally))
            battle_state.last_target.setdefault(enemy.instance_id, None)

    def _seed_party_threat_for_ally(self, battle_state: BattleState, ally: Combatant) -> None:
        threat_map = battle_state.party_threat.setdefault(ally.instance_id, {})
        for enemy in battle_state.enemies:
            threat_map.setdefault(enemy.instance_id, self._base_threat_for_target(enemy))

    @staticmethod
    def _base_threat_for_target(target: Combatant) -> int:
        # Base threat uses a small fraction of max HP + DEF as a starting nudge.
        base = (target.stats.max_hp + target.stats.defense) // AGGRO_BASE_DIVISOR
        return max(1, base)

    def _rebuild_turn_queue(self, battle_state: BattleState) -> None:
        living = [c for c in self._iter_combatants(battle_state) if c.is_alive]
        living.sort(key=lambda c: (-c.stats.speed, c.instance_id))
        battle_state.turn_queue = [c.instance_id for c in living]
        if not living:
            battle_state.current_actor_id = None

    def _advance_turn(self, battle_state: BattleState, last_actor_id: str) -> List[BattleEvent]:
        self._rebuild_turn_queue(battle_state)
        queue = battle_state.turn_queue
        events: List[BattleEvent] = []
        if not queue:
            battle_state.current_actor_id = None
            return events

        round_last_actor = battle_state.round_last_actor_id
        wrapped = False
        if round_last_actor and round_last_actor not in queue:
            wrapped = True

        if last_actor_id in queue:
            idx = queue.index(last_actor_id)
            next_index = (idx + 1) % len(queue)
            if next_index == 0:
                wrapped = True
            next_actor_id = queue[next_index]
        else:
            next_actor_id = queue[0]

        if wrapped:
            events.extend(self._start_new_round(battle_state))
            queue = battle_state.turn_queue
            if not queue:
                battle_state.current_actor_id = None
                return events
            if last_actor_id in queue:
                idx = queue.index(last_actor_id)
                next_index = (idx + 1) % len(queue)
                next_actor_id = queue[next_index]
            else:
                next_actor_id = queue[0]

        battle_state.current_actor_id = next_actor_id
        return events

    def _select_enemy_target(
        self,
        battle_state: BattleState,
        enemy: Combatant,
        living_allies: List[Combatant],
        rng: RNG,
    ) -> tuple[Combatant, bool]:
        threat_map = battle_state.enemy_aggro.setdefault(enemy.instance_id, {})
        for ally in living_allies:
            threat_map.setdefault(ally.instance_id, self._base_threat_for_target(ally))

        last_target_id = battle_state.last_target.get(enemy.instance_id)
        base_threats = {ally.instance_id: threat_map.get(ally.instance_id, 0) for ally in living_allies}
        top_threat = max(base_threats.values())
        top_ids = [target_id for target_id, value in base_threats.items() if value == top_threat]
        second_threat = None
        if len(base_threats) > 1:
            sorted_values = sorted(base_threats.values(), reverse=True)
            second_threat = sorted_values[1]
        ignore_repeat = (
            last_target_id in base_threats
            and len(living_allies) > 1
            and len(top_ids) == 1
            and top_ids[0] == last_target_id
            and second_threat is not None
            and top_threat - second_threat >= ANTI_REPEAT_IGNORE_GAP
        )

        effective: Dict[str, int] = {}
        for ally in living_allies:
            base_value = base_threats[ally.instance_id]
            if ally.instance_id == last_target_id and len(living_allies) > 1 and not ignore_repeat:
                effective[ally.instance_id] = int(base_value * ANTI_REPEAT_MULTIPLIER)
            else:
                effective[ally.instance_id] = base_value

        max_effective = max(effective.values())
        tied = [ally for ally in living_allies if effective[ally.instance_id] == max_effective]
        if len(tied) == 1:
            target = tied[0]
        else:
            target = tied[rng.randint(0, len(tied) - 1)]
        anti_repeat_applied = (
            target.instance_id == last_target_id and len(living_allies) > 1 and not ignore_repeat
        )
        return target, anti_repeat_applied

    def _select_party_target(
        self,
        battle_state: BattleState,
        ally: Combatant,
        living_enemies: List[Combatant],
        rng: RNG,
    ) -> Combatant:
        ordered = self._order_enemies_by_party_threat(battle_state, ally, living_enemies, rng)
        return ordered[0]

    def _order_enemies_by_party_threat(
        self,
        battle_state: BattleState,
        ally: Combatant,
        living_enemies: List[Combatant],
        rng: RNG,
    ) -> List[Combatant]:
        threat_map = battle_state.party_threat.setdefault(ally.instance_id, {})
        for enemy in living_enemies:
            threat_map.setdefault(enemy.instance_id, self._base_threat_for_target(enemy))
        threat_values: Dict[str, int] = {
            enemy.instance_id: threat_map.get(enemy.instance_id, 0) for enemy in living_enemies
        }
        grouped: Dict[int, List[Combatant]] = {}
        for enemy in living_enemies:
            grouped.setdefault(threat_values[enemy.instance_id], []).append(enemy)
        ordered: List[Combatant] = []
        for threat_value in sorted(grouped.keys(), reverse=True):
            group = grouped[threat_value]
            if len(group) > 1:
                rng.shuffle(group)
            ordered.extend(group)
        return ordered

    def _update_victory(self, battle_state: BattleState) -> BattleResolvedEvent | None:
        if all(not enemy.is_alive for enemy in battle_state.enemies):
            battle_state.is_over = True
            battle_state.victor = "allies"
            battle_state.current_actor_id = None
            return BattleResolvedEvent(victor="allies")
        if all(not ally.is_alive for ally in battle_state.allies):
            battle_state.is_over = True
            battle_state.victor = "enemies"
            battle_state.current_actor_id = None
            return BattleResolvedEvent(victor="enemies")
        return None

    def _finalize_defeat(self, battle_state: BattleState) -> List[BattleEvent]:
        if not battle_state.is_over:
            result = self._update_victory(battle_state)
            return [result] if result else []
        return []

    def _check_player_defeat(self, battle_state: BattleState) -> BattleResolvedEvent | None:
        player_id = battle_state.player_id
        if not player_id:
            return None
        for combatant in battle_state.allies:
            if combatant.instance_id == player_id:
                if combatant.is_alive:
                    return None
                battle_state.is_over = True
                battle_state.victor = "enemies"
                battle_state.current_actor_id = None
                return BattleResolvedEvent(victor="enemies")
        return None

    def _build_party_talk_text(
        self,
        member_id: str,
        member_name: str,
        battle_state: BattleState,
        rng: RNG,
    ) -> str:
        entries = self._knowledge_repo.get_entries(member_id)
        if not entries:
            return f"{member_name}: I'm not sure about these foes."

        info_lines: List[str] = []
        for group in self._group_alive_enemies(battle_state):
            entry = self._match_knowledge_entry(entries, group["tags"])
            if not entry:
                continue
            low, high = self._estimate_hp_range(group["max_hp"], rng)
            parts = [f"{group['name']} look to have around {low}-{high} HP."]
            if entry.speed_hint:
                parts.append(entry.speed_hint)
            if entry.behavior:
                parts.append(entry.behavior)
            info_lines.append(" ".join(parts))

        if not info_lines:
            return f"{member_name}: I'm not sure about these foes."
        return f"{member_name}: {' '.join(info_lines)}"

    def _to_view(self, combatant: Combatant, *, hide_hp: bool) -> BattleCombatantView:
        if hide_hp:
            hp_display = "???"
        else:
            hp_display = f"{combatant.stats.hp}/{combatant.stats.max_hp}"
        return BattleCombatantView(
            instance_id=combatant.instance_id,
            name=combatant.display_name,
            hp_display=hp_display,
            side=combatant.side,
            is_alive=combatant.is_alive,
            current_hp=combatant.stats.hp,
            max_hp=combatant.stats.max_hp,
            defense=combatant.stats.defense,
        )

    def _weapon_tags_for_ids(self, weapon_ids: Sequence[str]) -> Tuple[str, ...]:
        tags: set[str] = set()
        for weapon_id in weapon_ids:
            try:
                weapon = self._weapons_repo.get(weapon_id)
            except KeyError:
                continue
            tags.update(weapon.tags)
        return tuple(sorted(tags))

    def _disambiguate_enemy_names(self, enemies: List[Combatant]) -> None:
        name_groups: Dict[str, List[Combatant]] = {}
        for enemy in enemies:
            name_groups.setdefault(enemy.display_name, []).append(enemy)
        for base_name, group in name_groups.items():
            if len(group) <= 1:
                continue
            for idx, combatant in enumerate(group, start=1):
                combatant.display_name = f"{base_name} ({idx})"

    @staticmethod
    def _ensure_unique_enemy_instances(enemies: List[Combatant], rng: RNG) -> None:
        """Ensure enemy entries are distinct objects before name disambiguation."""
        seen: set[int] = set()
        for index, enemy in enumerate(enemies):
            identity = id(enemy)
            if identity in seen:
                enemies[index] = Combatant(
                    instance_id=make_instance_id("enemy", rng),
                    display_name=enemy.display_name,
                    side=enemy.side,
                    stats=Stats(
                        max_hp=enemy.stats.max_hp,
                        hp=enemy.stats.hp,
                        max_mp=enemy.stats.max_mp,
                        mp=enemy.stats.mp,
                        attack=enemy.stats.attack,
                        defense=enemy.stats.defense,
                        speed=enemy.stats.speed,
                    ),
                    tags=enemy.tags,
                    weapon_tags=enemy.weapon_tags,
                    source_id=enemy.source_id,
                )
            else:
                seen.add(identity)

    def _weapon_ids_from_equipment(self, equipment: MemberEquipment | None) -> List[str]:
        if equipment is None:
            return []
        ordered: List[str] = []
        for weapon_id in equipment.weapon_slots:
            if weapon_id and weapon_id not in ordered:
                ordered.append(weapon_id)
        return ordered

    def _armour_ids_from_equipment(self, equipment: MemberEquipment | None) -> List[str]:
        if equipment is None:
            return []
        ids: List[str] = []
        for slot in ARMOUR_SLOTS:
            armour_id = equipment.armour_slots.get(slot)
            if armour_id:
                ids.append(armour_id)
        return ids

    def _calculate_attack(self, weapon_ids: Sequence[str], fallback: int) -> int:
        for weapon_id in weapon_ids:
            try:
                weapon_def = self._weapons_repo.get(weapon_id)
            except KeyError:
                continue
            return max(1, weapon_def.attack)
        return max(1, fallback)

    def _calculate_defense(self, armour_ids: Sequence[str], fallback: int) -> int:
        total = 0
        for armour_id in armour_ids:
            try:
                armour_def = self._armour_repo.get(armour_id)
            except KeyError:
                continue
            total += armour_def.defense
        return total if total > 0 else max(0, fallback)

    def _start_new_round(self, battle_state: BattleState) -> List[BattleEvent]:
        battle_state.round_index += 1
        events = self._expire_enemy_debuffs(battle_state)
        self._set_round_last_actor_id(battle_state)
        return events

    def _set_round_last_actor_id(self, battle_state: BattleState) -> None:
        if battle_state.turn_queue:
            battle_state.round_last_actor_id = battle_state.turn_queue[-1]
        else:
            battle_state.round_last_actor_id = None

    @staticmethod
    def estimate_damage(
        attacker: Combatant, target: Combatant, *, bonus_power: int = 0, minimum: int = 1
    ) -> int:
        """Estimate damage without mutating combatants or guard values."""
        effective_attack = compute_effective_attack(attacker.stats, attacker.debuffs)
        effective_defense = compute_effective_defense(target.stats, target.debuffs)
        base_damage = max(minimum, effective_attack + bonus_power - effective_defense)
        return max(0, base_damage)

    def estimate_damage_for_ids(
        self,
        battle_state: BattleState,
        attacker_id: str,
        target_id: str,
        *,
        bonus_power: int = 0,
        minimum: int = 1,
    ) -> int:
        attacker = self._get_combatant(battle_state, attacker_id)
        target = self._get_combatant(battle_state, target_id)
        return self.estimate_damage(attacker, target, bonus_power=bonus_power, minimum=minimum)

    def _resolve_damage(
        self,
        battle_state: BattleState,
        attacker: Combatant,
        target: Combatant,
        *,
        bonus_power: int,
        minimum: int,
    ) -> tuple[int, List[BattleEvent]]:
        effective_attack = compute_effective_attack(attacker.stats, attacker.debuffs)
        effective_defense = compute_effective_defense(target.stats, target.debuffs)
        base_damage = max(minimum, effective_attack + bonus_power - effective_defense)
        damage = base_damage
        if target.guard_reduction > 0:
            absorbed = min(damage, target.guard_reduction)
            damage -= absorbed
            target.guard_reduction = 0
        damage = max(0, damage)
        target.stats.hp = max(0, target.stats.hp - damage)
        debuff_events: List[BattleEvent] = []
        if not target.is_alive and target.debuffs:
            target.debuffs = []

        if damage > 0 and attacker.side == "allies" and target.side == "enemies":
            aggro_map = battle_state.enemy_aggro.setdefault(target.instance_id, {})
            if attacker.instance_id not in aggro_map:
                aggro_map[attacker.instance_id] = self._base_threat_for_target(attacker)
            aggro_map[attacker.instance_id] += damage + AGGRO_HIT_BONUS
            threat_map = battle_state.party_threat.setdefault(attacker.instance_id, {})
            if target.instance_id not in threat_map:
                threat_map[target.instance_id] = self._base_threat_for_target(target)
            threat_map[target.instance_id] += damage + AGGRO_HIT_BONUS
        elif damage > 0 and attacker.side == "enemies" and target.side == "allies":
            battle_state.last_target[attacker.instance_id] = target.instance_id

        return damage, debuff_events

    def _resolve_skill_targets(
        self,
        battle_state: BattleState,
        attacker: Combatant,
        skill: SkillDef,
        requested_target_ids: Sequence[str],
    ) -> List[Combatant]:
        if skill.target_mode == "self":
            return [attacker]

        if skill.target_mode == "single_enemy":
            if len(requested_target_ids) != 1:
                raise ValueError("Single-target skill requires exactly one target.")
        elif skill.target_mode == "multi_enemy":
            if not requested_target_ids:
                raise ValueError("Multi-target skill requires at least one target.")
            if len(requested_target_ids) > skill.max_targets:
                raise ValueError("Too many targets selected for skill.")

        targets: List[Combatant] = []
        for target_id in requested_target_ids:
            target = self._get_combatant(battle_state, target_id)
            if target.side == attacker.side:
                raise ValueError("Cannot target allies with this skill.")
            if not target.is_alive:
                raise ValueError("Cannot target defeated combatants.")
            if target in targets:
                raise ValueError("Duplicate targets are not allowed.")
            targets.append(target)
        return targets

    def _group_alive_enemies(self, battle_state: BattleState) -> List[Dict[str, object]]:
        groups: Dict[str, Dict[str, object]] = {}
        for enemy in battle_state.enemies:
            if not enemy.is_alive:
                continue
            key = enemy.source_id or enemy.instance_id
            if key not in groups:
                groups[key] = {
                    "name": enemy.display_name,
                    "tags": tuple(enemy.tags),
                    "max_hp": enemy.stats.max_hp,
                }
        return [groups[key] for key in sorted(groups.keys())]

    @staticmethod
    def _match_knowledge_entry(entries: Sequence[KnowledgeEntry], tags: Tuple[str, ...]) -> KnowledgeEntry | None:
        tag_set = set(tags)
        for entry in entries:
            if set(entry.enemy_tags) & tag_set:
                return entry
        return None

    @staticmethod
    def _estimate_hp_range(actual_hp: int, rng: RNG) -> Tuple[int, int]:
        low = max(1, actual_hp + rng.randint(-3, -1))
        high = max(low, actual_hp + rng.randint(0, 3))
        return low, high

    # -----------------------
    # Rewards & Loot
    # -----------------------
    def apply_victory_rewards(self, battle_state: BattleState, state: GameState) -> List[BattleEvent]:
        if not state.player:
            return []
        defeated: List[tuple[Combatant, object]] = []
        total_gold = 0
        total_exp = 0
        for enemy in battle_state.enemies:
            if enemy.source_id is None:
                continue
            try:
                enemy_def = self._enemies_repo.get(enemy.source_id)
            except KeyError:
                continue
            total_gold += getattr(enemy_def, "rewards_gold", 0) or 0
            total_exp += getattr(enemy_def, "rewards_exp", 0) or 0
            defeated.append((enemy, enemy_def))

        reward_events: List[BattleEvent] = []
        if total_gold <= 0 and total_exp <= 0 and not defeated:
            return reward_events

        reward_events.append(BattleRewardsHeaderEvent())
        if total_gold > 0:
            state.gold += total_gold
            reward_events.append(BattleGoldRewardEvent(amount=total_gold, total_gold=state.gold))

        if total_exp > 0:
            participants = self._active_party_ids(state)
            if participants:
                base = total_exp // len(participants)
                remainder = total_exp % len(participants)
                for member_id in participants:
                    share = base
                    if member_id == state.player.id:
                        share += remainder
                    if share > 0:
                        reward_events.extend(self._award_exp(state, member_id, share))

        reward_events.extend(self._roll_loot(defeated, state))
        reward_events.extend(self._apply_floor_one_side_quest_rewards(defeated, state))
        if self._quest_service and defeated:
            defeated_tags = [tuple(getattr(enemy_def, "tags", ())) for _, enemy_def in defeated]
            self._quest_service.record_battle_victory(state, defeated_tags)
            self._quest_service.refresh_collect_objectives(state)
        self.restore_party_resources(state, restore_hp=False, restore_mp=True)
        state.flags["flag_last_battle_defeat"] = False
        if len(reward_events) == 1:
            return []
        return reward_events

    def _apply_floor_one_side_quest_rewards(
        self, defeated: List[tuple[Combatant, object]], state: GameState
    ) -> List[BattleEvent]:
        """Handle Floor One side quest progress and rewards using flags only."""
        events: List[BattleEvent] = []

        # Dana side quest: collect 3 wolf teeth (tracked via inventory).
        if state.flags.get("flag_sq_dana_accepted") and not state.flags.get("flag_sq_dana_completed"):
            teeth = state.inventory.items.get("wolf_tooth", 0)
            if teeth >= 3:
                state.flags["flag_sq_dana_ready"] = True

        # Cerel side quest: kill counts for goblin grunts and half-orcs.
        if state.flags.get("flag_sq_cerel_accepted") and not state.flags.get("flag_sq_cerel_completed"):
            goblin_kills = 0
            orc_kills = 0
            for _enemy, enemy_def in defeated:
                if getattr(enemy_def, "id", "") == "goblin_grunt":
                    goblin_kills += 1
                if getattr(enemy_def, "id", "") == "half_orc_raider":
                    orc_kills += 1
            if goblin_kills:
                self._increment_flag_counter(state, "flag_kill_goblin_grunt", 10, goblin_kills)
            if orc_kills:
                self._increment_flag_counter(state, "flag_kill_half_orc", 5, orc_kills)

            goblin_count = self._flag_counter_value(state, "flag_kill_goblin_grunt", 10)
            orc_count = self._flag_counter_value(state, "flag_kill_half_orc", 5)
            if goblin_count >= 10 and orc_count >= 5:
                state.flags["flag_sq_cerel_ready"] = True

        return events

    @staticmethod
    def _flag_counter_value(state: GameState, prefix: str, maximum: int) -> int:
        return sum(1 for idx in range(1, maximum + 1) if state.flags.get(f"{prefix}_{idx}"))

    @staticmethod
    def _increment_flag_counter(
        state: GameState, prefix: str, maximum: int, increment: int = 1
    ) -> None:
        current = 0
        while current < maximum and state.flags.get(f"{prefix}_{current + 1}"):
            current += 1
        new_value = min(maximum, current + max(0, increment))
        for idx in range(current + 1, new_value + 1):
            state.flags[f"{prefix}_{idx}"] = True


    def _active_party_ids(self, state: GameState) -> List[str]:
        ids: List[str] = []
        if state.player:
            ids.append(state.player.id)
        ids.extend(state.party_members)
        return ids

    def _award_exp(self, state: GameState, member_id: str, amount: int) -> List[BattleEvent]:
        if amount <= 0:
            return []
        events: List[BattleEvent] = []
        current_level = state.member_levels.get(member_id, 1)
        current_exp = state.member_exp.get(member_id, 0)
        current_exp += amount
        leveled: List[int] = []
        threshold = self._xp_to_next_level(current_level)
        while current_exp >= threshold:
            current_exp -= threshold
            current_level += 1
            leveled.append(current_level)
            threshold = self._xp_to_next_level(current_level)
        state.member_levels[member_id] = current_level
        state.member_exp[member_id] = current_exp
        member_name = self._resolve_member_name(state, member_id)
        events.append(
            BattleExpRewardEvent(
                member_id=member_id,
                member_name=member_name,
                amount=amount,
                new_level=current_level,
            )
        )
        for level in leveled:
            events.append(BattleLevelUpEvent(member_id=member_id, member_name=member_name, new_level=level))
        if leveled:
            if state.player and member_id == state.player.id:
                self._recalculate_player_stats(state)
            self._restore_member_resources(state, member_id, restore_hp=True, restore_mp=True)
        return events

    @staticmethod
    def _xp_to_next_level(level: int) -> int:
        return 10 + (level - 1) * 5

    def _roll_loot(self, defeated: List[tuple[Combatant, object]], state: GameState) -> List[BattleEvent]:
        loot_events: List[BattleEvent] = []
        for combatant, _enemy_def in defeated:
            tags = set(combatant.tags)
            for table in self._loot_tables():
                if not self._loot_table_matches(table, tags):
                    continue
                for drop in table.drops:
                    roll = state.rng.random()
                    if roll > drop.chance:
                        continue
                    quantity = drop.min_qty if drop.min_qty == drop.max_qty else state.rng.randint(drop.min_qty, drop.max_qty)
                    if quantity <= 0:
                        continue
                    state.inventory.add_item(drop.item_id, quantity)
                    loot_events.append(
                        LootAcquiredEvent(
                            item_id=drop.item_id,
                            item_name=self._get_item_name(drop.item_id),
                            quantity=quantity,
                        )
                    )
        return loot_events

    def _loot_tables(self) -> List[LootTableDef]:
        if self._loot_tables_cache is None:
            self._loot_tables_cache = list(self._loot_tables_repo.all())
        return self._loot_tables_cache

    @staticmethod
    def _loot_table_matches(table: LootTableDef, enemy_tags: set[str]) -> bool:
        required = set(table.required_tags)
        forbidden = set(table.forbidden_tags)
        if required and not required.issubset(enemy_tags):
            return False
        if forbidden and forbidden & enemy_tags:
            return False
        return True

    def _get_item_name(self, item_id: str) -> str:
        try:
            return self._items_repo.get(item_id).name
        except KeyError:
            return item_id

    def _resolve_member_name(self, state: GameState, member_id: str) -> str:
        if state.player and member_id == state.player.id:
            return state.player.name
        try:
            member = self._party_members_repo.get(member_id)
            return member.name
        except KeyError:
            return member_id

    def restore_party_resources(self, state: GameState, *, restore_hp: bool, restore_mp: bool) -> None:
        """Reset current resources for the player (and future party hooks) after battles."""
        for member_id in self._active_party_ids(state):
            self._restore_member_resources(state, member_id, restore_hp=restore_hp, restore_mp=restore_mp)

    def _recalculate_player_stats(self, state: GameState) -> None:
        if not state.player:
            return
        equipment = state.equipment.get(state.player.id)
        weapon_ids = self._weapon_ids_from_equipment(equipment)
        armour_ids = self._armour_ids_from_equipment(equipment)
        base_stats = BaseStats(
            max_hp=state.player.base_stats.max_hp,
            max_mp=state.player.base_stats.max_mp,
            attack=self._calculate_attack(weapon_ids, state.player.base_stats.attack),
            defense=self._calculate_defense(armour_ids, state.player.base_stats.defense),
            speed=state.player.base_stats.speed,
        )
        state.player.base_stats = base_stats
        state.player.stats = apply_attribute_scaling(
            base_stats,
            state.player.attributes,
            current_hp=state.player.stats.hp,
            current_mp=state.player.stats.mp,
        )

    def party_has_knowledge(self, state: GameState, enemy_tags: Tuple[str, ...]) -> bool:
        """
        Check if any member of the current party has knowledge entries matching the enemy tags.
        
        Returns True if at least one active party member knows about enemies with these tags.
        """
        enemy_tag_set = set(enemy_tags)
        for member_id in self._active_party_ids(state):
            entries = self._knowledge_repo.get_entries(member_id)
            for entry in entries:
                if set(entry.enemy_tags) & enemy_tag_set:
                    return True
        return False

    def _restore_member_resources(
        self,
        state: GameState,
        member_id: str,
        *,
        restore_hp: bool,
        restore_mp: bool,
    ) -> None:
        if state.player and member_id == state.player.id:
            if restore_hp:
                state.player.stats.hp = state.player.stats.max_hp
            if restore_mp:
                state.player.stats.mp = state.player.stats.max_mp

    @staticmethod
    def _describe_debuff_text(debuff_type: str, amount: int) -> str:
        label = "ATK" if debuff_type == "attack_down" else "DEF"
        return f"{label} -{amount} (until end of next round)."

    def _expire_enemy_debuffs(self, battle_state: BattleState) -> List[BattleEvent]:
        events: List[BattleEvent] = []
        for enemy in battle_state.enemies:
            if not enemy.debuffs:
                continue
            remaining: List[ActiveDebuff] = []
            for debuff in enemy.debuffs:
                if debuff.expires_at_round <= battle_state.round_index:
                    if enemy.is_alive:
                        events.append(
                            DebuffExpiredEvent(
                                target_id=enemy.instance_id,
                                target_name=enemy.display_name,
                                debuff_type=debuff.debuff_type,
                            )
                        )
                else:
                    remaining.append(debuff)
            enemy.debuffs = remaining
        return events


