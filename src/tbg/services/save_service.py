"""Serialization helpers for manual save/load."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping

from tbg.core.rng import RNG, RNGStatePayload
from tbg.core.types import GameMode
from tbg.data.repositories import (
    ArmourRepository,
    AreasRepository,
    ClassesRepository,
    ItemsRepository,
    PartyMembersRepository,
    QuestsRepository,
    StoryRepository,
    WeaponsRepository,
)
from tbg.domain.entities import Player, Stats
from tbg.domain.inventory import ARMOUR_SLOTS, MemberEquipment, PartyInventory
from tbg.domain.quest_state import QuestObjectiveProgress, QuestProgress
from tbg.domain.state import GameState
from tbg.services.errors import SaveLoadError
from tbg.services.area_service import DEFAULT_STARTING_AREA_ID


SavePayload = Dict[str, Any]
_VALID_MODES: tuple[GameMode, ...] = ("main_menu", "story", "camp_menu", "battle")


class SaveService:
    """Converts runtime state to/from a validated, versioned payload."""

    SAVE_VERSION = 1

    def __init__(
        self,
        *,
        story_repo: StoryRepository,
        classes_repo: ClassesRepository,
        weapons_repo: WeaponsRepository,
        armour_repo: ArmourRepository,
        items_repo: ItemsRepository,
        party_members_repo: PartyMembersRepository,
        areas_repo: AreasRepository,
        quests_repo: QuestsRepository | None = None,
    ) -> None:
        self._story_repo = story_repo
        self._classes_repo = classes_repo
        self._weapons_repo = weapons_repo
        self._armour_repo = armour_repo
        self._items_repo = items_repo
        self._party_members_repo = party_members_repo
        self._areas_repo = areas_repo
        self._quests_repo = quests_repo

    def serialize(self, state: GameState) -> SavePayload:
        """Return a JSON-serializable payload for disk persistence."""
        payload: SavePayload = {
            "save_version": self.SAVE_VERSION,
            "metadata": self._build_metadata(state),
            "rng": state.rng.export_state(),
            "state": self._serialize_state(state),
        }
        return payload

    def deserialize(self, payload: Mapping[str, Any]) -> GameState:
        """Rehydrate a GameState + RNG from a persisted payload."""
        if not isinstance(payload, Mapping):
            raise SaveLoadError("Save data must be a JSON object.")
        version = payload.get("save_version")
        if version != self.SAVE_VERSION:
            raise SaveLoadError(f"Unsupported save version: {version}")
        rng_payload = payload.get("rng")
        state_payload = payload.get("state")
        if not isinstance(rng_payload, Mapping) or not isinstance(state_payload, Mapping):
            raise SaveLoadError("Save data is missing required sections.")

        seed = self._require_int(state_payload.get("seed"), "state.seed")
        rng = RNG(seed)
        try:
            rng.restore_state(self._coerce_rng_payload(rng_payload))
        except ValueError as exc:
            raise SaveLoadError(f"Invalid RNG state: {exc}") from exc

        mode = self._require_mode(state_payload.get("mode"))
        current_node_id = self._require_str(state_payload.get("current_node_id"), "state.current_node_id")
        self._validate_story_node(current_node_id)
        current_location_id_raw = state_payload.get("current_location_id")
        if current_location_id_raw is None:
            current_location_id = DEFAULT_STARTING_AREA_ID
        else:
            current_location_id = self._require_str(
                current_location_id_raw, "state.current_location_id"
            )
        self._validate_area_id(current_location_id)

        state = GameState(seed=seed, rng=rng, mode=mode, current_node_id=current_node_id)
        state.player_name = self._require_str(state_payload.get("player_name"), "state.player_name")
        state.gold = self._require_int(state_payload.get("gold"), "state.gold")
        state.exp = self._require_int(state_payload.get("exp"), "state.exp")
        state.flags = self._coerce_bool_dict(state_payload.get("flags"), "state.flags")
        state.party_members = self._coerce_party_members(state_payload.get("party_members"))
        state.pending_story_node_id = self._coerce_optional_str(
            state_payload.get("pending_story_node_id"), "state.pending_story_node_id"
        )
        if state.pending_story_node_id:
            self._validate_story_node(state.pending_story_node_id)
        state.pending_narration = self._coerce_narration(state_payload.get("pending_narration"))
        state.inventory = self._coerce_inventory(state_payload.get("inventory"))
        state.member_levels = self._coerce_int_dict(state_payload.get("member_levels"), "state.member_levels")
        state.member_exp = self._coerce_int_dict(state_payload.get("member_exp"), "state.member_exp")
        state.camp_message = self._coerce_optional_str(state_payload.get("camp_message"), "state.camp_message")
        state.story_checkpoint_node_id = self._coerce_optional_str(
            state_payload.get("story_checkpoint_node_id"), "state.story_checkpoint_node_id"
        )
        state.story_checkpoint_location_id = self._coerce_optional_str(
            state_payload.get("story_checkpoint_location_id"), "state.story_checkpoint_location_id"
        )
        checkpoint_thread = state_payload.get("story_checkpoint_thread_id")
        if checkpoint_thread is None:
            state.story_checkpoint_thread_id = "main_story" if state.story_checkpoint_node_id else None
        else:
            state.story_checkpoint_thread_id = self._coerce_optional_str(
                checkpoint_thread, "state.story_checkpoint_thread_id"
            )
        state.current_location_id = current_location_id
        state.visited_locations = self._coerce_visited_locations(
            state_payload.get("visited_locations"), current_location_id
        )
        state.location_entry_seen = self._coerce_location_entry_flags(
            state_payload.get("location_entry_seen"), current_location_id
        )
        state.quests_active = self._coerce_quests_active(state_payload.get("quests_active"))
        state.quests_completed = self._coerce_str_list(
            state_payload.get("quests_completed"), "state.quests_completed"
        )
        state.quests_turned_in = self._coerce_str_list(
            state_payload.get("quests_turned_in"), "state.quests_turned_in"
        )

        player_payload = state_payload.get("player")
        if player_payload is not None:
            state.player = self._coerce_player(player_payload)

        state.equipment = self._coerce_equipment(state_payload.get("equipment"), state)

        self._validate_progress_consistency(state)
        self._validate_quest_state(state)

        return state

    def _build_metadata(self, state: GameState) -> Dict[str, Any]:
        return {
            "player_name": state.player_name,
            "current_node_id": state.current_node_id,
            "current_location_id": state.current_location_id,
            "mode": state.mode,
            "gold": state.gold,
            "seed": state.seed,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }

    def _serialize_state(self, state: GameState) -> Dict[str, Any]:
        equipment_payload = {
            member_id: {
                "weapon_slots": list(member_equipment.weapon_slots),
                "armour_slots": dict(member_equipment.armour_slots),
            }
            for member_id, member_equipment in state.equipment.items()
        }
        pending_narration = [
            {"node_id": node_id, "text": text} for node_id, text in state.pending_narration
        ]
        return {
            "seed": state.seed,
            "mode": state.mode,
            "current_node_id": state.current_node_id,
            "current_location_id": state.current_location_id,
            "player_name": state.player_name,
            "gold": state.gold,
            "exp": state.exp,
            "flags": dict(state.flags),
            "party_members": list(state.party_members),
            "pending_story_node_id": state.pending_story_node_id,
            "pending_narration": pending_narration,
            "inventory": {
                "weapons": dict(state.inventory.weapons),
                "armour": dict(state.inventory.armour),
                "items": dict(state.inventory.items),
            },
            "equipment": equipment_payload,
            "member_levels": dict(state.member_levels),
            "member_exp": dict(state.member_exp),
            "camp_message": state.camp_message,
            "player": self._serialize_player(state.player) if state.player else None,
            "visited_locations": list(state.visited_locations),
            "location_entry_seen": dict(state.location_entry_seen),
            "story_checkpoint_node_id": state.story_checkpoint_node_id,
            "story_checkpoint_location_id": state.story_checkpoint_location_id,
            "story_checkpoint_thread_id": state.story_checkpoint_thread_id,
            "quests_active": self._serialize_quests_active(state),
            "quests_completed": list(state.quests_completed),
            "quests_turned_in": list(state.quests_turned_in),
        }

    @staticmethod
    def _serialize_player(player: Player) -> Dict[str, Any]:
        return {
            "id": player.id,
            "name": player.name,
            "class_id": player.class_id,
            "stats": {
                "max_hp": player.stats.max_hp,
                "hp": player.stats.hp,
                "max_mp": player.stats.max_mp,
                "mp": player.stats.mp,
                "attack": player.stats.attack,
                "defense": player.stats.defense,
                "speed": player.stats.speed,
            },
        }

    def _coerce_rng_payload(self, payload: Mapping[str, Any]) -> RNGStatePayload:
        version = self._require_int(payload.get("version"), "rng.version")
        state_values = payload.get("state")
        if not isinstance(state_values, list):
            raise SaveLoadError("Invalid RNG state payload.")
        gauss = payload.get("gauss")
        return {"version": version, "state": state_values, "gauss": gauss}

    def _require_mode(self, value: Any) -> GameMode:
        if value not in _VALID_MODES:
            raise SaveLoadError(f"Invalid mode value: {value}")
        return value

    @staticmethod
    def _require_str(value: Any, context: str) -> str:
        if not isinstance(value, str):
            raise SaveLoadError(f"{context} must be a string.")
        return value

    @staticmethod
    def _require_int(value: Any, context: str) -> int:
        if not isinstance(value, int):
            raise SaveLoadError(f"{context} must be an integer.")
        return value

    def _coerce_optional_str(self, value: Any, context: str) -> str | None:
        if value is None:
            return None
        return self._require_str(value, context)

    def _coerce_bool_dict(self, value: Any, context: str) -> Dict[str, bool]:
        mapping = self._require_dict(value, context)
        result: Dict[str, bool] = {}
        for key, entry in mapping.items():
            if not isinstance(key, str):
                raise SaveLoadError(f"{context} keys must be strings.")
            if not isinstance(entry, bool):
                raise SaveLoadError(f"{context}.{key} must be a boolean.")
            result[key] = entry
        return result

    def _coerce_int_dict(self, value: Any, context: str) -> Dict[str, int]:
        mapping = self._require_dict(value, context)
        result: Dict[str, int] = {}
        for key, entry in mapping.items():
            if not isinstance(key, str):
                raise SaveLoadError(f"{context} keys must be strings.")
            if not isinstance(entry, int):
                raise SaveLoadError(f"{context}.{key} must be an integer.")
            result[key] = entry
        return result

    def _coerce_str_list(self, value: Any, context: str) -> List[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise SaveLoadError(f"{context} must be a list.")
        result: List[str] = []
        for entry in value:
            if not isinstance(entry, str):
                raise SaveLoadError(f"{context} entries must be strings.")
            result.append(entry)
        return result

    def _coerce_party_members(self, value: Any) -> List[str]:
        if not isinstance(value, list):
            raise SaveLoadError("state.party_members must be a list.")
        members: List[str] = []
        for entry in value:
            member_id = self._require_str(entry, "state.party_members[]")
            try:
                self._party_members_repo.get(member_id)
            except KeyError as exc:
                raise SaveLoadError(f"Save incompatible with current definitions: party member '{member_id}' missing.") from exc
            members.append(member_id)
        return members

    def _coerce_visited_locations(self, value: Any, current_location_id: str) -> List[str]:
        if value is None:
            return [current_location_id]
        if not isinstance(value, list):
            raise SaveLoadError("state.visited_locations must be a list.")
        visited: List[str] = []
        for entry in value:
            location_id = self._require_str(entry, "state.visited_locations[]")
            self._validate_area_id(location_id)
            if location_id not in visited:
                visited.append(location_id)
        if not visited:
            visited.append(current_location_id)
        if current_location_id not in visited:
            visited.append(current_location_id)
        return visited

    def _coerce_location_entry_flags(
        self, value: Any, current_location_id: str
    ) -> Dict[str, bool]:
        if value is None:
            return {current_location_id: True}
        mapping = self._require_dict(value, "state.location_entry_seen")
        result: Dict[str, bool] = {}
        for key, entry in mapping.items():
            location_id = self._require_str(key, "state.location_entry_seen key")
            self._validate_area_id(location_id)
            if not isinstance(entry, bool):
                raise SaveLoadError(f"state.location_entry_seen[{location_id}] must be a boolean.")
            result[location_id] = entry
        if current_location_id not in result:
            result[current_location_id] = True
        return result

    def _coerce_narration(self, value: Any) -> List[tuple[str, str]]:
        if not isinstance(value, list):
            raise SaveLoadError("state.pending_narration must be a list.")
        narration: List[tuple[str, str]] = []
        for entry in value:
            if not isinstance(entry, Mapping):
                raise SaveLoadError("Each pending narration entry must be an object.")
            node_id = self._require_str(entry.get("node_id"), "pending_narration.node_id")
            text = self._require_str(entry.get("text"), "pending_narration.text")
            self._validate_story_node(node_id)
            narration.append((node_id, text))
        return narration

    def _coerce_inventory(self, value: Any) -> PartyInventory:
        inventory_data = self._require_dict(value, "state.inventory")
        weapons = self._coerce_item_counts(inventory_data.get("weapons"), "state.inventory.weapons", self._weapons_repo.get)
        armour = self._coerce_item_counts(inventory_data.get("armour"), "state.inventory.armour", self._armour_repo.get)
        items = self._coerce_item_counts(inventory_data.get("items"), "state.inventory.items", self._items_repo.get)
        inventory = PartyInventory()
        inventory.weapons = weapons
        inventory.armour = armour
        inventory.items = items
        return inventory

    def _coerce_quests_active(self, value: Any) -> Dict[str, QuestProgress]:
        if value is None:
            return {}
        mapping = self._require_dict(value, "state.quests_active")
        result: Dict[str, QuestProgress] = {}
        for quest_id, payload in mapping.items():
            if not isinstance(quest_id, str):
                raise SaveLoadError("state.quests_active keys must be strings.")
            if self._quests_repo:
                self._validate_quest_id(quest_id)
            progress_map = self._require_dict(payload, f"state.quests_active['{quest_id}']")
            objectives_data = progress_map.get("objectives", [])
            if not isinstance(objectives_data, list):
                raise SaveLoadError(f"state.quests_active['{quest_id}'].objectives must be a list.")
            objectives: List[QuestObjectiveProgress] = []
            for index, entry in enumerate(objectives_data):
                entry_map = self._require_dict(
                    entry, f"state.quests_active['{quest_id}'].objectives[{index}]"
                )
                current = self._require_int(
                    entry_map.get("current"),
                    f"state.quests_active['{quest_id}'].objectives[{index}].current",
                )
                completed = entry_map.get("completed")
                if not isinstance(completed, bool):
                    raise SaveLoadError(
                        f"state.quests_active['{quest_id}'].objectives[{index}].completed must be a boolean."
                    )
                objectives.append(QuestObjectiveProgress(current=current, completed=completed))
            result[quest_id] = QuestProgress(quest_id=quest_id, objectives=objectives)
        return result

    def _serialize_quests_active(self, state: GameState) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        for quest_id, progress in state.quests_active.items():
            payload[quest_id] = {
                "objectives": [
                    {"current": obj.current, "completed": obj.completed} for obj in progress.objectives
                ]
            }
        return payload

    def _coerce_item_counts(self, value: Any, context: str, validate_fn) -> Dict[str, int]:
        mapping = self._require_dict(value, context)
        result: Dict[str, int] = {}
        for key, entry in mapping.items():
            item_id = self._require_str(key, f"{context} key")
            quantity = self._require_int(entry, f"{context}[{item_id}]")
            if quantity < 0:
                raise SaveLoadError(f"{context}[{item_id}] cannot be negative.")
            try:
                validate_fn(item_id)
            except KeyError as exc:
                raise SaveLoadError(f"Save incompatible with current definitions: '{item_id}' missing.") from exc
            result[item_id] = quantity
        return result

    def _coerce_equipment(self, value: Any, state: GameState) -> Dict[str, MemberEquipment]:
        mapping = self._require_dict(value, "state.equipment")
        valid_member_ids = set(state.party_members)
        if state.player:
            valid_member_ids.add(state.player.id)
        equipment: Dict[str, MemberEquipment] = {}
        for member_id, entry in mapping.items():
            if not isinstance(member_id, str):
                raise SaveLoadError("Equipment member ids must be strings.")
            if member_id not in valid_member_ids:
                raise SaveLoadError(f"Equipment references unknown member '{member_id}'.")
            entry_mapping = self._require_dict(entry, f"state.equipment[{member_id}]")
            weapon_slots = entry_mapping.get("weapon_slots")
            armour_slots = entry_mapping.get("armour_slots")
            if not isinstance(weapon_slots, list) or len(weapon_slots) != 2:
                raise SaveLoadError(f"Equipment for '{member_id}' must define two weapon slots.")
            armour_mapping = self._require_dict(armour_slots, f"state.equipment[{member_id}].armour_slots")
            member_equipment = MemberEquipment()
            member_equipment.weapon_slots = [
                self._coerce_optional_weapon_id(slot_value, member_id, slot_index)
                for slot_index, slot_value in enumerate(weapon_slots)
            ]
            member_equipment.armour_slots = {
                slot: self._coerce_optional_armour_id(armour_mapping.get(slot), member_id, slot)
                for slot in ARMOUR_SLOTS
            }
            equipment[member_id] = member_equipment
        return equipment

    def _coerce_optional_weapon_id(self, value: Any, member_id: str, slot_index: int) -> str | None:
        if value is None:
            return None
        weapon_id = self._require_str(value, f"equipment[{member_id}].weapon_slots[{slot_index}]")
        try:
            self._weapons_repo.get(weapon_id)
        except KeyError as exc:
            raise SaveLoadError(
                f"Save incompatible with current definitions: weapon '{weapon_id}' missing."
            ) from exc
        return weapon_id

    def _coerce_optional_armour_id(self, value: Any, member_id: str, slot: str) -> str | None:
        if value is None:
            return None
        armour_id = self._require_str(value, f"equipment[{member_id}].armour_slots.{slot}")
        try:
            self._armour_repo.get(armour_id)
        except KeyError as exc:
            raise SaveLoadError(
                f"Save incompatible with current definitions: armour '{armour_id}' missing."
            ) from exc
        return armour_id

    def _coerce_player(self, value: Any) -> Player:
        mapping = self._require_dict(value, "state.player")
        player_id = self._require_str(mapping.get("id"), "state.player.id")
        name = self._require_str(mapping.get("name"), "state.player.name")
        class_id = self._require_str(mapping.get("class_id"), "state.player.class_id")
        try:
            self._classes_repo.get(class_id)
        except KeyError as exc:
            raise SaveLoadError(
                f"Save incompatible with current definitions: class '{class_id}' missing."
            ) from exc
        stats_mapping = self._require_dict(mapping.get("stats"), "state.player.stats")
        stats = Stats(
            max_hp=self._require_int(stats_mapping.get("max_hp"), "state.player.stats.max_hp"),
            hp=self._require_int(stats_mapping.get("hp"), "state.player.stats.hp"),
            max_mp=self._require_int(stats_mapping.get("max_mp"), "state.player.stats.max_mp"),
            mp=self._require_int(stats_mapping.get("mp"), "state.player.stats.mp"),
            attack=self._require_int(stats_mapping.get("attack"), "state.player.stats.attack"),
            defense=self._require_int(stats_mapping.get("defense"), "state.player.stats.defense"),
            speed=self._require_int(stats_mapping.get("speed"), "state.player.stats.speed"),
        )
        return Player(id=player_id, name=name, class_id=class_id, stats=stats)

    def _validate_story_node(self, node_id: str) -> None:
        try:
            self._story_repo.get(node_id)
        except KeyError as exc:
            raise SaveLoadError(
                f"Save incompatible with current definitions: story node '{node_id}' missing."
            ) from exc

    def _validate_progress_consistency(self, state: GameState) -> None:
        member_ids = set(state.party_members)
        if state.player:
            member_ids.add(state.player.id)
        for member_id in state.member_levels.keys():
            if member_id not in member_ids:
                raise SaveLoadError(f"Member level references unknown id '{member_id}'.")
        for member_id in state.member_exp.keys():
            if member_id not in member_ids:
                raise SaveLoadError(f"Member EXP references unknown id '{member_id}'.")

        equipment_keys = set(state.equipment.keys())
        extra_equipment = equipment_keys - member_ids
        if extra_equipment:
            raise SaveLoadError(f"Equipment references unknown members: {sorted(extra_equipment)}.")

    def _validate_quest_state(self, state: GameState) -> None:
        if not self._quests_repo:
            return
        for quest_id in state.quests_active.keys():
            self._validate_quest_id(quest_id)
        for quest_id in state.quests_completed:
            self._validate_quest_id(quest_id)
        for quest_id in state.quests_turned_in:
            self._validate_quest_id(quest_id)

    def _validate_quest_id(self, quest_id: str) -> None:
        if not self._quests_repo:
            return
        try:
            self._quests_repo.get(quest_id)
        except KeyError as exc:
            raise SaveLoadError(
                f"Save incompatible with current definitions: quest '{quest_id}' missing."
            ) from exc

    def _validate_area_id(self, area_id: str) -> None:
        try:
            self._areas_repo.get(area_id)
        except KeyError as exc:
            raise SaveLoadError(
                f"Save incompatible with current definitions: area '{area_id}' missing."
            ) from exc

    @staticmethod
    def _require_dict(value: Any, context: str) -> Dict[str, Any]:
        if not isinstance(value, Mapping):
            raise SaveLoadError(f"{context} must be an object.")
        return dict(value)
