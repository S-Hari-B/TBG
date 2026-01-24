"""Serialization helpers for manual save/load."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Sequence

from tbg.core.rng import RNG, RNGStatePayload
from tbg.core.types import GameMode
from tbg.data.repositories import (
    ArmourRepository,
    ClassesRepository,
    ItemsRepository,
    LocationsRepository,
    PartyMembersRepository,
    QuestsRepository,
    StoryRepository,
    WeaponsRepository,
)
from tbg.domain.attribute_scaling import apply_attribute_scaling
from tbg.domain.entities import Attributes, BaseStats, Player, Stats
from tbg.domain.inventory import ARMOUR_SLOTS, MemberEquipment, PartyInventory
from tbg.domain.quest_state import QuestObjectiveProgress, QuestProgress
from tbg.domain.state import GameState
from tbg.services.errors import SaveLoadError
DEFAULT_STARTING_LOCATION_ID = "threshold_inn"


SavePayload = Dict[str, Any]
_VALID_MODES: tuple[GameMode, ...] = ("main_menu", "story", "camp_menu", "battle")


class SaveService:
    """Converts runtime state to/from a validated, versioned payload."""

    SAVE_VERSION = 2

    def __init__(
        self,
        *,
        story_repo: StoryRepository,
        classes_repo: ClassesRepository,
        weapons_repo: WeaponsRepository,
        armour_repo: ArmourRepository,
        items_repo: ItemsRepository,
        party_members_repo: PartyMembersRepository,
        locations_repo: LocationsRepository,
        quests_repo: QuestsRepository | None = None,
    ) -> None:
        self._story_repo = story_repo
        self._classes_repo = classes_repo
        self._weapons_repo = weapons_repo
        self._armour_repo = armour_repo
        self._items_repo = items_repo
        self._party_members_repo = party_members_repo
        self._locations_repo = locations_repo
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
            raise SaveLoadError("Save format changed (alpha). Please start a new game.")
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
            current_location_id = DEFAULT_STARTING_LOCATION_ID
        else:
            current_location_id = self._require_str(
                current_location_id_raw, "state.current_location_id"
            )
        self._validate_location_id(current_location_id)

        state = GameState(seed=seed, rng=rng, mode=mode, current_node_id=current_node_id)
        state.player_name = self._require_str(state_payload.get("player_name"), "state.player_name")
        state.player_attribute_points_spent = self._coerce_non_negative_int(
            state_payload.get("player_attribute_points_spent"),
            "state.player_attribute_points_spent",
            default=0,
        )
        state.player_attribute_points_debug_bonus = self._coerce_non_negative_int(
            state_payload.get("player_attribute_points_debug_bonus"),
            "state.player_attribute_points_debug_bonus",
            default=0,
        )
        state.gold = self._require_int(state_payload.get("gold"), "state.gold")
        state.exp = self._require_int(state_payload.get("exp"), "state.exp")
        state.flags = self._coerce_bool_dict(state_payload.get("flags"), "state.flags")
        state.party_members = self._coerce_party_members(state_payload.get("party_members"))
        player_attributes = self._coerce_optional_attributes(
            state_payload.get("player_attributes"), "state.player_attributes"
        )
        state.pending_story_node_id = self._coerce_optional_str(
            state_payload.get("pending_story_node_id"), "state.pending_story_node_id"
        )
        if state.pending_story_node_id:
            self._validate_story_node(state.pending_story_node_id)
        state.pending_narration = self._coerce_narration(state_payload.get("pending_narration"))
        state.inventory = self._coerce_inventory(state_payload.get("inventory"))
        state.member_levels = self._coerce_int_dict(state_payload.get("member_levels"), "state.member_levels")
        state.member_exp = self._coerce_int_dict(state_payload.get("member_exp"), "state.member_exp")
        player_payload = state_payload.get("player")
        state.owned_summons = self._coerce_owned_summons(
            state_payload.get("owned_summons"), player_payload
        )
        state.party_member_summon_loadouts = self._coerce_party_member_summon_loadouts(
            state_payload.get("party_member_summon_loadouts"), state.party_members
        )
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
        state.location_visits = self._coerce_location_visits(
            state_payload.get("location_visits"), current_location_id
        )
        state.shop_stock_remaining = self._coerce_shop_stock_remaining(
            state_payload.get("shop_stock_remaining")
        )
        state.shop_stock_visit_index = self._coerce_shop_stock_visit_index(
            state_payload.get("shop_stock_visit_index")
        )
        state.quests_active = self._coerce_quests_active(state_payload.get("quests_active"))
        state.quests_completed = self._coerce_str_list(
            state_payload.get("quests_completed"), "state.quests_completed"
        )
        state.quests_turned_in = self._coerce_str_list(
            state_payload.get("quests_turned_in"), "state.quests_turned_in"
        )

        if player_payload is not None:
            state.player = self._coerce_player(player_payload, attributes=player_attributes)

        state.equipment = self._coerce_equipment(state_payload.get("equipment"), state)
        state.party_member_attributes = self._coerce_party_member_attributes(
            state_payload.get("party_member_attributes"), state.party_members
        )
        if state.player:
            self._recalculate_player_stats(state)

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
            "player_attribute_points_spent": state.player_attribute_points_spent,
            "player_attribute_points_debug_bonus": state.player_attribute_points_debug_bonus,
            "gold": state.gold,
            "exp": state.exp,
            "flags": dict(state.flags),
            "party_members": list(state.party_members),
            "player_attributes": self._serialize_attributes(state.player.attributes) if state.player else None,
            "party_member_attributes": {
                member_id: self._serialize_attributes(attributes)
                for member_id, attributes in state.party_member_attributes.items()
            },
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
            "owned_summons": dict(state.owned_summons),
            "party_member_summon_loadouts": {
                member_id: list(loadout)
                for member_id, loadout in state.party_member_summon_loadouts.items()
            },
            "camp_message": state.camp_message,
            "player": self._serialize_player(state.player) if state.player else None,
            "visited_locations": list(state.visited_locations),
            "location_entry_seen": dict(state.location_entry_seen),
            "location_visits": dict(state.location_visits),
            "shop_stock_remaining": dict(state.shop_stock_remaining),
            "shop_stock_visit_index": dict(state.shop_stock_visit_index),
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
            "equipped_summons": list(player.equipped_summons),
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

    @staticmethod
    def _serialize_attributes(attributes: Attributes) -> Dict[str, int]:
        return {
            "STR": attributes.STR,
            "DEX": attributes.DEX,
            "INT": attributes.INT,
            "VIT": attributes.VIT,
            "BOND": attributes.BOND,
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

    def _coerce_non_negative_int(self, value: Any, context: str, *, default: int) -> int:
        if value is None:
            return default
        value_int = self._require_int(value, context)
        if value_int < 0:
            raise SaveLoadError(f"{context} must be a non-negative integer.")
        return value_int

    def _coerce_optional_str(self, value: Any, context: str) -> str | None:
        if value is None:
            return None
        return self._require_str(value, context)

    def _coerce_optional_attributes(self, value: Any, context: str) -> Attributes | None:
        if value is None:
            return None
        return self._coerce_attributes(value, context)

    def _coerce_owned_summons(self, value: Any, player_payload: Any) -> Dict[str, int]:
        if value is None:
            return self._default_owned_summons(player_payload)
        mapping = self._require_dict(value, "state.owned_summons")
        result: Dict[str, int] = {}
        for summon_id, count in mapping.items():
            summon_key = self._require_str(summon_id, "state.owned_summons key")
            qty = self._require_int(count, f"state.owned_summons[{summon_key}]")
            if qty < 0:
                raise SaveLoadError("state.owned_summons values must be non-negative.")
            result[summon_key] = qty
        return result

    def _coerce_party_member_summon_loadouts(
        self, value: Any, party_members: List[str]
    ) -> Dict[str, List[str]]:
        if value is None:
            return {}
        mapping = self._require_dict(value, "state.party_member_summon_loadouts")
        result: Dict[str, List[str]] = {}
        known_members = set(party_members)
        extra_members = set(mapping.keys()) - known_members
        if extra_members:
            raise SaveLoadError(
                f"state.party_member_summon_loadouts references unknown members: {sorted(extra_members)}."
            )
        for member_id, entries in mapping.items():
            member_key = self._require_str(member_id, "state.party_member_summon_loadouts key")
            if not isinstance(entries, list):
                raise SaveLoadError(
                    f"state.party_member_summon_loadouts[{member_key}] must be a list."
                )
            loadout: List[str] = []
            for entry in entries:
                summon_id = self._require_str(
                    entry, f"state.party_member_summon_loadouts[{member_key}] entry"
                )
                loadout.append(summon_id)
            result[member_key] = loadout
        return result

    def _default_owned_summons(self, player_payload: Any) -> Dict[str, int]:
        if player_payload is None:
            return {}
        mapping = self._require_dict(player_payload, "state.player")
        class_id = self._require_str(mapping.get("class_id"), "state.player.class_id")
        try:
            class_def = self._classes_repo.get(class_id)
        except KeyError as exc:
            raise SaveLoadError(
                f"Save incompatible with current definitions: class '{class_id}' missing."
            ) from exc
        return self._build_initial_owned_summons(
            class_def.known_summons, class_def.default_equipped_summons
        )

    @staticmethod
    def _build_initial_owned_summons(
        known_summons: Sequence[str],
        default_equipped: Sequence[str],
    ) -> Dict[str, int]:
        owned: Dict[str, int] = {}
        for summon_id in default_equipped:
            owned[summon_id] = owned.get(summon_id, 0) + 1
        for summon_id in known_summons:
            owned[summon_id] = max(owned.get(summon_id, 0), 1)
        return owned

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

    def _coerce_attributes(self, value: Any, context: str) -> Attributes:
        mapping = self._require_dict(value, context)
        expected = {"STR", "DEX", "INT", "VIT", "BOND"}
        actual = set(mapping.keys())
        if actual != expected:
            missing = expected - actual
            extra = actual - expected
            msg_parts: list[str] = []
            if missing:
                msg_parts.append(f"missing keys: {sorted(missing)}")
            if extra:
                msg_parts.append(f"unknown keys: {sorted(extra)}")
            raise SaveLoadError(f"{context} has schema issues ({'; '.join(msg_parts)}).")
        values: dict[str, int] = {}
        for key in expected:
            value_int = self._require_int(mapping.get(key), f"{context}.{key}")
            if value_int < 0:
                raise SaveLoadError(f"{context}.{key} must be a non-negative integer.")
            values[key] = value_int
        return Attributes(
            STR=values["STR"],
            DEX=values["DEX"],
            INT=values["INT"],
            VIT=values["VIT"],
            BOND=values["BOND"],
        )

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
            self._validate_location_id(location_id)
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
            self._validate_location_id(location_id)
            if not isinstance(entry, bool):
                raise SaveLoadError(f"state.location_entry_seen[{location_id}] must be a boolean.")
            result[location_id] = entry
        if current_location_id not in result:
            result[current_location_id] = True
        return result

    def _coerce_location_visits(
        self, value: Any, current_location_id: str
    ) -> Dict[str, int]:
        if value is None:
            return {current_location_id: 0}
        mapping = self._require_dict(value, "state.location_visits")
        result: Dict[str, int] = {}
        for key, entry in mapping.items():
            location_id = self._require_str(key, "state.location_visits key")
            self._validate_location_id(location_id)
            count = self._require_int(entry, f"state.location_visits[{location_id}]")
            if count < 0:
                raise SaveLoadError("state.location_visits values must be non-negative.")
            result[location_id] = count
        if current_location_id not in result:
            result[current_location_id] = 0
        return result

    def _coerce_shop_stock_remaining(
        self, value: Any
    ) -> Dict[str, Dict[str, Dict[str, int]]]:
        if value is None:
            return {}
        mapping = self._require_dict(value, "state.shop_stock_remaining")
        output: Dict[str, Dict[str, Dict[str, int]]] = {}
        for location_id, shop_map in mapping.items():
            location_key = self._require_str(location_id, "state.shop_stock_remaining key")
            shop_mapping = self._require_dict(shop_map, f"state.shop_stock_remaining[{location_key}]")
            output[location_key] = {}
            for shop_id, stock_map in shop_mapping.items():
                shop_key = self._require_str(shop_id, f"state.shop_stock_remaining[{location_key}] shop key")
                item_mapping = self._require_dict(
                    stock_map, f"state.shop_stock_remaining[{location_key}][{shop_key}]"
                )
                output[location_key][shop_key] = {}
                for item_id, remaining in item_mapping.items():
                    item_key = self._require_str(
                        item_id,
                        f"state.shop_stock_remaining[{location_key}][{shop_key}] item key",
                    )
                    qty = self._require_int(
                        remaining,
                        f"state.shop_stock_remaining[{location_key}][{shop_key}][{item_key}]",
                    )
                    if qty < 0:
                        raise SaveLoadError("shop_stock_remaining quantities must be non-negative.")
                    output[location_key][shop_key][item_key] = qty
        return output

    def _coerce_shop_stock_visit_index(
        self, value: Any
    ) -> Dict[str, Dict[str, int]]:
        if value is None:
            return {}
        mapping = self._require_dict(value, "state.shop_stock_visit_index")
        output: Dict[str, Dict[str, int]] = {}
        for location_id, shop_map in mapping.items():
            location_key = self._require_str(location_id, "state.shop_stock_visit_index key")
            shop_mapping = self._require_dict(shop_map, f"state.shop_stock_visit_index[{location_key}]")
            output[location_key] = {}
            for shop_id, visit in shop_mapping.items():
                shop_key = self._require_str(shop_id, f"state.shop_stock_visit_index[{location_key}] shop key")
                visit_value = self._require_int(
                    visit,
                    f"state.shop_stock_visit_index[{location_key}][{shop_key}]",
                )
                if visit_value < 0:
                    raise SaveLoadError("shop_stock_visit_index values must be non-negative.")
                output[location_key][shop_key] = visit_value
        return output

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

    def _coerce_party_member_attributes(
        self,
        value: Any,
        party_members: List[str],
    ) -> Dict[str, Attributes]:
        if value is None:
            payload: Dict[str, Any] = {}
        else:
            payload = self._require_dict(value, "state.party_member_attributes")
        known_members = set(party_members)
        extra_members = set(payload.keys()) - known_members
        if extra_members:
            raise SaveLoadError(
                f"state.party_member_attributes references unknown members: {sorted(extra_members)}."
            )
        attributes: Dict[str, Attributes] = {}
        for member_id in party_members:
            if member_id in payload:
                attributes[member_id] = self._coerce_attributes(
                    payload.get(member_id),
                    f"state.party_member_attributes.{member_id}",
                )
                continue
            try:
                member_def = self._party_members_repo.get(member_id)
            except KeyError as exc:
                raise SaveLoadError(
                    f"Save incompatible with current definitions: party member '{member_id}' missing."
                ) from exc
            attributes[member_id] = Attributes(
                STR=member_def.starting_attributes.STR,
                DEX=member_def.starting_attributes.DEX,
                INT=member_def.starting_attributes.INT,
                VIT=member_def.starting_attributes.VIT,
                BOND=member_def.starting_attributes.BOND,
            )
        return attributes

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

    def _coerce_player(self, value: Any, *, attributes: Attributes | None) -> Player:
        mapping = self._require_dict(value, "state.player")
        player_id = self._require_str(mapping.get("id"), "state.player.id")
        name = self._require_str(mapping.get("name"), "state.player.name")
        class_id = self._require_str(mapping.get("class_id"), "state.player.class_id")
        equipped_summons = self._coerce_str_list(
            mapping.get("equipped_summons"),
            "state.player.equipped_summons",
        )
        try:
            class_def = self._classes_repo.get(class_id)
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
        if attributes is None:
            attributes = Attributes(
                STR=class_def.starting_attributes.STR,
                DEX=class_def.starting_attributes.DEX,
                INT=class_def.starting_attributes.INT,
                VIT=class_def.starting_attributes.VIT,
                BOND=class_def.starting_attributes.BOND,
            )
        base_stats = BaseStats(
            max_hp=class_def.base_hp,
            max_mp=class_def.base_mp,
            attack=stats.attack,
            defense=stats.defense,
            speed=class_def.speed,
        )
        return Player(
            id=player_id,
            name=name,
            class_id=class_id,
            stats=stats,
            attributes=attributes,
            base_stats=base_stats,
            equipped_summons=equipped_summons,
        )

    def _recalculate_player_stats(self, state: GameState) -> None:
        if not state.player:
            return
        try:
            class_def = self._classes_repo.get(state.player.class_id)
        except KeyError as exc:
            raise SaveLoadError(
                f"Save incompatible with current definitions: class '{state.player.class_id}' missing."
            ) from exc
        equipment = state.equipment.get(state.player.id)
        weapon_ids = []
        armour_ids = []
        if equipment:
            weapon_ids = [weapon_id for weapon_id in equipment.weapon_slots if weapon_id]
            for slot in ARMOUR_SLOTS:
                armour_id = equipment.armour_slots.get(slot)
                if armour_id:
                    armour_ids.append(armour_id)
        try:
            fallback_attack = self._weapons_repo.get(class_def.starting_weapon_id).attack
        except KeyError:
            fallback_attack = state.player.base_stats.attack
        try:
            fallback_defense = self._armour_repo.get(class_def.starting_armour_id).defense
        except KeyError:
            fallback_defense = state.player.base_stats.defense
        base_attack = self._calculate_attack_from_weapons(weapon_ids, fallback_attack)
        base_defense = self._calculate_defense_from_armour(armour_ids, fallback_defense)
        base_stats = Stats(
            max_hp=class_def.base_hp,
            hp=state.player.stats.hp,
            max_mp=class_def.base_mp,
            mp=state.player.stats.mp,
            attack=base_attack,
            defense=base_defense,
            speed=class_def.speed,
        )
        state.player.base_stats = BaseStats(
            max_hp=base_stats.max_hp,
            max_mp=base_stats.max_mp,
            attack=base_stats.attack,
            defense=base_stats.defense,
            speed=base_stats.speed,
        )
        state.player.stats = apply_attribute_scaling(
            state.player.base_stats,
            state.player.attributes,
            current_hp=state.player.stats.hp,
            current_mp=state.player.stats.mp,
        )

    def _calculate_attack_from_weapons(self, weapon_ids: List[str], fallback: int) -> int:
        for weapon_id in weapon_ids:
            try:
                weapon_def = self._weapons_repo.get(weapon_id)
            except KeyError:
                continue
            return max(1, weapon_def.attack)
        return max(1, fallback)

    def _calculate_defense_from_armour(self, armour_ids: List[str], fallback: int) -> int:
        total = 0
        for armour_id in armour_ids:
            try:
                armour_def = self._armour_repo.get(armour_id)
            except KeyError:
                continue
            total += armour_def.defense
        return total if total > 0 else max(0, fallback)

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

    def _validate_location_id(self, location_id: str) -> None:
        try:
            self._locations_repo.get(location_id)
        except KeyError as exc:
            raise SaveLoadError(
                f"Save references unknown location: {location_id}"
            ) from exc

    @staticmethod
    def _require_dict(value: Any, context: str) -> Dict[str, Any]:
        if not isinstance(value, Mapping):
            raise SaveLoadError(f"{context} must be an object.")
        return dict(value)
