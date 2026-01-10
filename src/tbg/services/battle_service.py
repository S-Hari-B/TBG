"""Battle service handling deterministic combat."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

from tbg.core.rng import RNG
from tbg.data.repositories import (
    ArmourRepository,
    EnemiesRepository,
    ItemsRepository,
    KnowledgeRepository,
    LootTablesRepository,
    PartyMembersRepository,
    SkillsRepository,
    WeaponsRepository,
)
from tbg.domain.battle_models import BattleCombatantView, BattleState, Combatant
from tbg.domain.defs import KnowledgeEntry, LootTableDef, SkillDef
from tbg.domain.entities import Stats
from tbg.domain.inventory import ARMOUR_SLOTS, MemberEquipment
from tbg.domain.state import GameState
from tbg.services.errors import FactoryError
from tbg.services.factories import create_enemy_instance, make_instance_id


@dataclass(slots=True)
class BattleView:
    """Presentation view for the current battle state."""

    battle_id: str
    allies: List[BattleCombatantView]
    enemies: List[BattleCombatantView]
    current_actor_id: str | None


@dataclass(slots=True)
class BattleEvent:
    """Base battle event."""


@dataclass(slots=True)
class BattleStartedEvent(BattleEvent):
    battle_id: str
    enemy_names: List[str]


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

        enemies: List[Combatant] = []
        for _id in enemy_ids:
            enemy_instance = create_enemy_instance(_id, enemies_repo=self._enemies_repo, rng=state.rng)
            enemies.append(
                Combatant(
                    instance_id=enemy_instance.id,
                    display_name=enemy_instance.name,
                    side="enemies",
                    stats=enemy_instance.stats,
                    tags=enemy_instance.tags,
                    weapon_tags=(),
                    source_id=enemy_instance.enemy_id,
                )
            )

        self._disambiguate_enemy_names(enemies)
        allies = [self._player_to_combatant(state)]
        for member_id in state.party_members:
            allies.append(self._party_member_to_combatant(member_id, state))

        battle_id = make_instance_id("battle", state.rng)
        battle_state = BattleState(battle_id=battle_id, allies=allies, enemies=enemies)
        self._rebuild_turn_queue(battle_state)
        if battle_state.turn_queue:
            battle_state.current_actor_id = battle_state.turn_queue[0]

        events = [BattleStartedEvent(battle_id=battle_id, enemy_names=[enemy.display_name for enemy in enemies])]
        return battle_state, events

    def get_battle_view(self, battle_state: BattleState) -> BattleView:
        """Return structured information for rendering."""
        return BattleView(
            battle_id=battle_state.battle_id,
            allies=[self._to_view(ally, hide_hp=False) for ally in battle_state.allies],
            enemies=[self._to_view(enemy, hide_hp=True) for enemy in battle_state.enemies],
            current_actor_id=battle_state.current_actor_id,
        )

    # -----------------------
    # Player Actions
    # -----------------------
    def basic_attack(self, battle_state: BattleState, attacker_id: str, target_id: str) -> List[BattleEvent]:
        attacker = self._get_combatant(battle_state, attacker_id)
        target = self._get_combatant(battle_state, target_id)
        damage = self._resolve_damage(attacker, target, bonus_power=0, minimum=1)

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
        if not target.is_alive:
            events.append(CombatantDefeatedEvent(combatant_id=target.instance_id, combatant_name=target.display_name))

        maybe_resolved = self._update_victory(battle_state)
        if maybe_resolved:
            events.append(maybe_resolved)
        else:
            self._advance_turn(battle_state, attacker.instance_id)
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
                damage = self._resolve_damage(attacker, target, bonus_power=skill.base_power, minimum=1)
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
                if not target.is_alive:
                    events.append(
                        CombatantDefeatedEvent(combatant_id=target.instance_id, combatant_name=target.display_name)
                    )
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
            self._advance_turn(battle_state, attacker.instance_id)
        return events

    def party_talk(self, battle_state: BattleState, speaker_id: str, rng: RNG) -> List[BattleEvent]:
        speaker = self._get_combatant(battle_state, speaker_id)
        source_id = speaker.source_id or speaker.instance_id
        text = self._build_party_talk_text(source_id, speaker.display_name, battle_state, rng)
        events = [PartyTalkEvent(speaker_id=speaker.instance_id, speaker_name=speaker.display_name, text=text)]
        self._advance_turn(battle_state, speaker.instance_id)
        return events

    # -----------------------
    # Enemy AI
    # -----------------------
    def run_enemy_turn(self, battle_state: BattleState, rng: RNG) -> List[BattleEvent]:
        actor = self._get_combatant(battle_state, battle_state.current_actor_id or "")
        living_allies = [ally for ally in battle_state.allies if ally.is_alive]
        if not living_allies:
            return self._finalize_defeat(battle_state)
        target_index = rng.randint(0, len(living_allies) - 1)
        events = self.basic_attack(battle_state, actor.instance_id, living_allies[target_index].instance_id)
        return events

    def run_ally_ai_turn(self, battle_state: BattleState, actor_id: str, rng: RNG) -> List[BattleEvent]:
        actor = self._get_combatant(battle_state, actor_id)
        living_enemies = [enemy for enemy in battle_state.enemies if enemy.is_alive]
        if not living_enemies:
            return []

        available_skills = self.get_available_skills(battle_state, actor_id)
        firebolt_skill = next((skill for skill in available_skills if skill.id == "skill_firebolt"), None)
        if (
            firebolt_skill
            and actor.stats.mp >= firebolt_skill.mp_cost
            and rng.randint(0, 1) == 0
        ):
            target = living_enemies[rng.randint(0, len(living_enemies) - 1)]
            return self.use_skill(battle_state, actor_id, firebolt_skill.id, [target.instance_id])

        target = living_enemies[rng.randint(0, len(living_enemies) - 1)]
        return self.basic_attack(battle_state, actor_id, target.instance_id)

    # -----------------------
    # Helpers
    # -----------------------
    def _player_to_combatant(self, state: GameState) -> Combatant:
        assert state.player is not None
        equipment = state.equipment.get(state.player.id)
        weapon_ids = self._weapon_ids_from_equipment(equipment)
        armour_ids = self._armour_ids_from_equipment(equipment)
        state.player.stats.attack = self._calculate_attack(weapon_ids, state.player.stats.attack)
        state.player.stats.defense = self._calculate_defense(armour_ids, state.player.stats.defense)
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
        stats = Stats(
            max_hp=member_def.base_hp,
            hp=member_def.base_hp,
            max_mp=member_def.base_mp,
            mp=member_def.base_mp,
            attack=self._calculate_attack(weapon_ids, base_attack),
            defense=self._calculate_defense(armour_ids, base_defense),
            speed=member_def.speed,
        )
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

    def _rebuild_turn_queue(self, battle_state: BattleState) -> None:
        living = [c for c in self._iter_combatants(battle_state) if c.is_alive]
        living.sort(key=lambda c: (-c.stats.speed, c.instance_id))
        battle_state.turn_queue = [c.instance_id for c in living]
        if not living:
            battle_state.current_actor_id = None

    def _advance_turn(self, battle_state: BattleState, last_actor_id: str) -> None:
        self._rebuild_turn_queue(battle_state)
        queue = battle_state.turn_queue
        if not queue:
            battle_state.current_actor_id = None
            return
        if last_actor_id in queue:
            idx = queue.index(last_actor_id)
            battle_state.current_actor_id = queue[(idx + 1) % len(queue)]
        else:
            battle_state.current_actor_id = queue[0]

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

    def _resolve_damage(self, attacker: Combatant, target: Combatant, *, bonus_power: int, minimum: int) -> int:
        base_damage = max(minimum, attacker.stats.attack + bonus_power - target.stats.defense)
        damage = base_damage
        if target.guard_reduction > 0:
            absorbed = min(damage, target.guard_reduction)
            damage -= absorbed
            target.guard_reduction = 0
        damage = max(0, damage)
        target.stats.hp = max(0, target.stats.hp - damage)
        return damage

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
        if len(reward_events) == 1:
            return []
        return reward_events

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


