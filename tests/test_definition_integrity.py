from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import pytest

from tbg.data import paths
from tbg.data.json_loader import load_json


@pytest.fixture(scope="module")
def definitions_dir() -> Path:
    """Return the canonical definitions directory."""
    return paths.get_definitions_path()


@pytest.mark.parametrize(
    "filename",
    [
        "weapons.json",
        "armour.json",
        "items.json",
        "classes.json",
        "enemies.json",
        "story.json",
        "abilities.json",
        "skills.json",
        "loot_tables.json",
        "floors.json",
        "locations.json",
        "quests.json",
        "shops.json",
    ],
)
def test_definition_files_are_valid_json(definitions_dir: Path, filename: str) -> None:
    """Every definition file should be parsable JSON."""
    file_path = definitions_dir / filename
    if not file_path.exists():
        pytest.skip(f"{filename} is not present.")
    data = load_json(file_path)
    assert isinstance(
        data, (dict, list)
    ), f"{filename} must contain an object or list; found {type(data).__name__}"


def test_definition_integrity_and_references(definitions_dir: Path) -> None:
    """Load all definition files and validate schema + cross references."""
    weapons = _validate_weapons(definitions_dir)
    armour = _validate_armour(definitions_dir)
    items = _validate_items(definitions_dir)
    skills = _validate_skills(definitions_dir)
    classes = _validate_classes(definitions_dir, weapons, armour, items)
    enemies = _validate_enemies(definitions_dir, weapons, armour)
    _validate_party_members(definitions_dir, weapons, armour)
    _validate_summons(definitions_dir)
    _validate_knowledge(definitions_dir)
    _validate_loot_tables(definitions_dir, items)
    story_node_ids = _validate_story(definitions_dir, classes, enemies)
    _validate_abilities(definitions_dir)
    _validate_shops(definitions_dir, items, weapons, armour)
    _validate_quests(definitions_dir, item_ids=items, area_ids=set(), story_node_ids=story_node_ids)
    assert skills  # ensure skills file not empty


def _validate_weapons(definitions_dir: Path) -> set[str]:
    data = _load_required_dict(definitions_dir, "weapons.json")
    ids: set[str] = set()
    for weapon_id, payload in data.items():
        _require_str(weapon_id, "weapon id")
        mapping = _require_mapping(payload, f"weapon '{weapon_id}'")
        _assert_allowed_fields(
            mapping,
            required={"name", "attack", "value"},
            optional={"tags", "slot_cost", "default_basic_attack_id", "energy_bonus"},
            context=f"weapon '{weapon_id}'",
        )
        _require_str(mapping["name"], f"weapon '{weapon_id}' name")
        _require_int(mapping["attack"], f"weapon '{weapon_id}' attack")
        _require_int(mapping["value"], f"weapon '{weapon_id}' value")

        if "tags" in mapping:
            _require_str_list(mapping["tags"], f"weapon '{weapon_id}' tags")
        if "slot_cost" in mapping:
            _require_int(mapping["slot_cost"], f"weapon '{weapon_id}' slot_cost")
        if "default_basic_attack_id" in mapping:
            _require_str(
                mapping["default_basic_attack_id"],
                f"weapon '{weapon_id}' default_basic_attack_id",
            )
        if "energy_bonus" in mapping:
            _require_int(mapping["energy_bonus"], f"weapon '{weapon_id}' energy_bonus")

        ids.add(weapon_id)
    return ids


def _validate_armour(definitions_dir: Path) -> set[str]:
    data = _load_required_dict(definitions_dir, "armour.json")
    ids: set[str] = set()
    for armour_id, payload in data.items():
        _require_str(armour_id, "armour id")
        mapping = _require_mapping(payload, f"armour '{armour_id}'")
        _assert_allowed_fields(
            mapping,
            required={"name", "slot", "defense", "value"},
            optional={"tags", "hp_bonus"},
            context=f"armour '{armour_id}'",
        )
        _require_str(mapping["name"], f"armour '{armour_id}' name")
        slot = _require_str(mapping["slot"], f"armour '{armour_id}' slot")
        assert slot in {"head", "body", "hands", "boots"}, f"armour '{armour_id}' has invalid slot '{slot}'"
        _require_int(mapping["defense"], f"armour '{armour_id}' defense")
        _require_int(mapping["value"], f"armour '{armour_id}' value")
        if "tags" in mapping:
            _require_str_list(mapping["tags"], f"armour '{armour_id}' tags")
        if "hp_bonus" in mapping:
            _require_int(mapping["hp_bonus"], f"armour '{armour_id}' hp_bonus")
        ids.add(armour_id)
    return ids


def _validate_items(definitions_dir: Path) -> set[str]:
    data = _load_required_dict(definitions_dir, "items.json")
    ids: set[str] = set()
    for item_id, payload in data.items():
        _require_str(item_id, "item id")
        mapping = _require_mapping(payload, f"item '{item_id}'")
        _assert_allowed_fields(
            mapping,
            required={"name", "kind", "value"},
            optional={
                "heal_hp",
                "heal_mp",
                "restore_energy",
                "targeting",
                "debuff_attack_flat",
                "debuff_defense_flat",
            },
            context=f"item '{item_id}'",
        )
        _require_str(mapping["name"], f"item '{item_id}' name")
        _require_str(mapping["kind"], f"item '{item_id}' kind")
        _require_int(mapping["value"], f"item '{item_id}' value")
        for field in ("heal_hp", "heal_mp", "restore_energy"):
            if field in mapping:
                _require_int(mapping[field], f"item '{item_id}' {field}")
        if "targeting" in mapping:
            targeting = _require_str(mapping["targeting"], f"item '{item_id}' targeting")
            assert targeting in {"self", "ally", "enemy", "any"}
        attack_down = _require_int(mapping.get("debuff_attack_flat", 0), f"item '{item_id}' debuff_attack_flat")
        defense_down = _require_int(mapping.get("debuff_defense_flat", 0), f"item '{item_id}' debuff_defense_flat")
        assert attack_down >= 0 and defense_down >= 0
        if attack_down and defense_down:
            raise AssertionError(f"item '{item_id}' cannot have both attack and defense debuffs")
        ids.add(item_id)
    return ids


def _validate_skills(definitions_dir: Path) -> set[str]:
    data = _load_required_dict(definitions_dir, "skills.json")
    ids: set[str] = set()
    for skill_id, payload in data.items():
        _require_str(skill_id, "skill id")
        mapping = _require_mapping(payload, f"skill '{skill_id}'")
        _assert_allowed_fields(
            mapping,
            required={
                "name",
                "description",
                "tags",
                "required_weapon_tags",
                "target_mode",
                "max_targets",
                "mp_cost",
                "base_power",
                "effect_type",
                "gold_value",
            },
            optional=set(),
            context=f"skill '{skill_id}'",
        )
        _require_str(mapping["name"], f"skill '{skill_id}' name")
        _require_str(mapping["description"], f"skill '{skill_id}' description")
        _require_str_list(mapping["tags"], f"skill '{skill_id}' tags")
        _require_str_list(mapping["required_weapon_tags"], f"skill '{skill_id}' required_weapon_tags")
        assert mapping["target_mode"] in {"single_enemy", "multi_enemy", "self"}
        assert mapping["effect_type"] in {"damage", "guard"}
        _require_int(mapping["max_targets"], f"skill '{skill_id}' max_targets")
        _require_int(mapping["mp_cost"], f"skill '{skill_id}' mp_cost")
        _require_int(mapping["base_power"], f"skill '{skill_id}' base_power")
        _require_int(mapping["gold_value"], f"skill '{skill_id}' gold_value")
        ids.add(skill_id)
    return ids


def _validate_shops(
    definitions_dir: Path,
    item_ids: set[str],
    weapon_ids: set[str],
    armour_ids: set[str],
) -> set[str]:
    data = _load_required_dict(definitions_dir, "shops.json")
    container = _require_mapping(data.get("shops"), "shops.json.shops")
    ids: set[str] = set()
    for shop_id, payload in container.items():
        _require_str(shop_id, "shop id")
        mapping = _require_mapping(payload, f"shop '{shop_id}'")
        _assert_allowed_fields(
            mapping,
            required={"id", "name", "shop_type", "tags", "stock_pool"},
            optional={"stock_size"},
            context=f"shop '{shop_id}'",
        )
        shop_id_value = _require_str(mapping["id"], f"shop '{shop_id}' id")
        assert shop_id_value == shop_id, f"shop '{shop_id}' id must match key"
        _require_str(mapping["name"], f"shop '{shop_id}' name")
        shop_type = _require_str(mapping["shop_type"], f"shop '{shop_id}' shop_type")
        assert shop_type in {"item", "weapon", "armour"}
        _require_str_list(mapping["tags"], f"shop '{shop_id}' tags")
        stock_pool = _require_list(mapping["stock_pool"], f"shop '{shop_id}' stock_pool")
        seen_ids: set[str] = set()
        if "stock_size" in mapping:
            stock_size = _require_int(mapping["stock_size"], f"shop '{shop_id}' stock_size")
            assert stock_size > 0
        for index, entry in enumerate(stock_pool):
            entry_map = _require_mapping(entry, f"shop '{shop_id}' stock_pool[{index}]")
            _assert_allowed_fields(
                entry_map,
                required={"id", "qty"},
                optional=set(),
                context=f"shop '{shop_id}' stock_pool[{index}]",
            )
            entry_id = _require_str(entry_map["id"], f"shop '{shop_id}' stock_pool[{index}].id")
            qty = _require_int(entry_map["qty"], f"shop '{shop_id}' stock_pool[{index}].qty")
            assert qty > 0
            assert entry_id not in seen_ids, f"shop '{shop_id}' stock_pool contains duplicates"
            seen_ids.add(entry_id)
            if shop_type == "item":
                assert entry_id in item_ids
            elif shop_type == "weapon":
                assert entry_id in weapon_ids
            elif shop_type == "armour":
                assert entry_id in armour_ids
        ids.add(shop_id)
    return ids


def _validate_classes(
    definitions_dir: Path,
    weapon_ids: set[str],
    armour_ids: set[str],
    item_ids: set[str],
) -> set[str]:
    data = _load_required_dict(definitions_dir, "classes.json")
    ids: set[str] = set()
    for class_id, payload in data.items():
        _require_str(class_id, "class id")
        mapping = _require_mapping(payload, f"class '{class_id}'")
        _assert_allowed_fields(
            mapping,
            required={
                "name",
                "base_hp",
                "base_mp",
                "speed",
                "starting_weapon",
                "starting_armour",
                "starting_attributes",
            },
            optional={
                "starting_weapons",
                "starting_items",
                "starting_abilities",
                "starting_level",
                "known_summons",
                "default_equipped_summons",
            },
            context=f"class '{class_id}'",
        )
        _require_str(mapping["name"], f"class '{class_id}' name")
        _require_int(mapping["base_hp"], f"class '{class_id}' base_hp")
        _require_int(mapping["base_mp"], f"class '{class_id}' base_mp")
        _require_int(mapping["speed"], f"class '{class_id}' speed")
        _require_attributes_mapping(
            mapping["starting_attributes"], f"class '{class_id}' starting_attributes"
        )
        starting_weapon = _require_str(
            mapping["starting_weapon"], f"class '{class_id}' starting_weapon"
        )
        if "known_summons" in mapping:
            _require_str_list(mapping["known_summons"], f"class '{class_id}' known_summons")
        if "default_equipped_summons" in mapping:
            _require_str_list(
                mapping["default_equipped_summons"],
                f"class '{class_id}' default_equipped_summons",
            )
        assert (
            starting_weapon in weapon_ids
        ), f"class '{class_id}' references missing weapon '{starting_weapon}'"

        starting_weapons = []
        if "starting_weapons" in mapping:
            starting_weapons = _require_str_list(
                mapping["starting_weapons"], f"class '{class_id}' starting_weapons"
            )
            for extra_weapon in starting_weapons:
                assert (
                    extra_weapon in weapon_ids
                ), f"class '{class_id}' starting_weapons includes unknown weapon '{extra_weapon}'"
        else:
            starting_weapons = [starting_weapon]
        if starting_weapon not in starting_weapons:
            starting_weapons.insert(0, starting_weapon)

        armour_slots: dict[str, str] = {}
        raw_armour = mapping["starting_armour"]
        if isinstance(raw_armour, str):
            armour_id = _require_str(raw_armour, f"class '{class_id}' starting_armour")
            assert (
                armour_id in armour_ids
            ), f"class '{class_id}' references missing armour '{armour_id}' in body slot"
            armour_slots["body"] = armour_id
        else:
            slots_map = _require_mapping(raw_armour, f"class '{class_id}' starting_armour")
            for slot_name, armour_id in slots_map.items():
                slot = _require_str(slot_name, f"class '{class_id}' starting_armour slot")
                assert slot in {"head", "body", "hands", "boots"}
                armour_id_str = _require_str(armour_id, f"class '{class_id}' starting_armour slot {slot}")
                assert (
                    armour_id_str in armour_ids
                ), f"class '{class_id}' references missing armour '{armour_id_str}' in slot '{slot}'"
                armour_slots[slot] = armour_id_str
        assert "body" in armour_slots, f"class '{class_id}' must include a body armour slot"

        if "starting_items" in mapping:
            items_mapping = _require_mapping(
                mapping["starting_items"], f"class '{class_id}' starting_items"
            )
            for item_id, amount in items_mapping.items():
                _require_int(amount, f"class '{class_id}' starting_items count")
                assert (
                    item_id in item_ids
                ), f"class '{class_id}' references missing item '{item_id}'"

        _require_int(mapping.get("starting_level", 1), f"class '{class_id}' starting_level")

        if "starting_abilities" in mapping:
            _require_str_list(
                mapping["starting_abilities"], f"class '{class_id}' starting_abilities"
            )

        ids.add(class_id)
    return ids


def _validate_enemies(
    definitions_dir: Path,
    weapon_ids: set[str],
    armour_ids: set[str],
) -> set[str]:
    data = _load_required_dict(definitions_dir, "enemies.json")
    ids: set[str] = set()
    group_members: dict[str, list[str]] = {}
    for enemy_id, payload in data.items():
        _require_str(enemy_id, "enemy id")
        mapping = _require_mapping(payload, f"enemy '{enemy_id}'")
        if "enemy_ids" in mapping:
            _assert_allowed_fields(
                mapping,
                required={"name", "enemy_ids"},
                optional={"tags"},
                context=f"enemy group '{enemy_id}'",
            )
            _require_str(mapping["name"], f"enemy group '{enemy_id}' name")
            member_ids = _require_str_list(mapping["enemy_ids"], f"enemy group '{enemy_id}' ids")
            if "tags" in mapping:
                _require_str_list(mapping["tags"], f"enemy group '{enemy_id}' tags")
            group_members[enemy_id] = member_ids
        else:
            _assert_allowed_fields(
                mapping,
                required={
                    "name",
                    "hp",
                    "mp",
                    "attack",
                    "defense",
                    "speed",
                    "rewards_exp",
                    "rewards_gold",
                },
                optional={"tags", "equipment"},
                context=f"enemy '{enemy_id}'",
            )
            _require_str(mapping["name"], f"enemy '{enemy_id}' name")
            _require_int(mapping["hp"], f"enemy '{enemy_id}' hp")
            _require_int(mapping["mp"], f"enemy '{enemy_id}' mp")
            _require_int(mapping["attack"], f"enemy '{enemy_id}' attack")
            _require_int(mapping["defense"], f"enemy '{enemy_id}' defense")
            _require_int(mapping["speed"], f"enemy '{enemy_id}' speed")
            _require_int(mapping["rewards_exp"], f"enemy '{enemy_id}' rewards_exp")
            _require_int(mapping["rewards_gold"], f"enemy '{enemy_id}' rewards_gold")
            if "tags" in mapping:
                _require_str_list(mapping["tags"], f"enemy '{enemy_id}' tags")
            if "equipment" in mapping:
                equipment = _require_mapping(
                    mapping["equipment"], f"enemy '{enemy_id}' equipment"
                )
                if "weapons" in equipment:
                    _require_str_list(
                        equipment["weapons"], f"enemy '{enemy_id}' equipment.weapons"
                    )
                    for weapon in equipment["weapons"]:
                        assert (
                            weapon in weapon_ids
                        ), f"enemy '{enemy_id}' references missing weapon '{weapon}'"
                if "armour" in equipment:
                    armour_id = _require_str(
                        equipment["armour"], f"enemy '{enemy_id}' equipment.armour"
                    )
                    assert (
                        armour_id in armour_ids
                    ), f"enemy '{enemy_id}' references missing armour '{armour_id}'"
        ids.add(enemy_id)
    single_and_group_ids = set(data.keys())
    for group_id, members in group_members.items():
        for member in members:
            assert (
                member in single_and_group_ids
            ), f"enemy group '{group_id}' references missing enemy '{member}'"
    return ids


def _validate_story(
    definitions_dir: Path,
    class_ids: set[str],
    enemy_ids: set[str],
) -> set[str]:
    data = _load_story_chapters(definitions_dir)
    for node_id, payload in data.items():
        _require_str(node_id, "story node id")
        mapping = _require_mapping(payload, f"story node '{node_id}'")
        assert "text" in mapping, f"story node '{node_id}' missing text"
        _require_str(mapping["text"], f"story node '{node_id}' text")
        if "next" in mapping:
            next_id = _require_str(mapping["next"], f"story node '{node_id}' next")
            assert next_id in data, f"story node '{node_id}' next references '{next_id}' which does not exist"
        if "choices" in mapping:
            choices = mapping["choices"]
            assert isinstance(
                choices, list
            ), f"story node '{node_id}' choices must be a list"
            for choice in choices:
                choice_map = _require_mapping(choice, f"story node '{node_id}' choice")
                _require_str(choice_map.get("label"), f"story node '{node_id}' choice label")
                if "next" in choice_map:
                    next_id = _require_str(
                        choice_map["next"], f"story node '{node_id}' choice next"
                    )
                    assert (
                        next_id in data
                    ), f"story node '{node_id}' choice next references '{next_id}' which does not exist"
                if "effects" in choice_map:
                    _validate_story_effects(
                        choice_map["effects"], node_id, class_ids, enemy_ids, data
                    )
        if "effects" in mapping:
            _validate_story_effects(mapping["effects"], node_id, class_ids, enemy_ids, data)
    return set(data.keys())


def _validate_story_effects(
    effects: Any,
    node_id: str,
    class_ids: set[str],
    enemy_ids: set[str],
    story_nodes: dict[str, Any],
) -> None:
    assert isinstance(effects, list), f"story node '{node_id}' effects must be a list"
    for effect in effects:
        effect_map = _require_mapping(effect, f"story node '{node_id}' effect")
        effect_type = _require_str(effect_map.get("type"), f"story node '{node_id}' effect type")
        if effect_type == "set_class":
            class_id = _require_str(
                effect_map.get("class_id"), f"story node '{node_id}' set_class.class_id"
            )
            assert (
                class_id in class_ids
            ), f"story node '{node_id}' sets unknown class '{class_id}'"
        elif effect_type == "start_battle":
            enemy_id = _require_str(
                effect_map.get("enemy_id"), f"story node '{node_id}' start_battle.enemy_id"
            )
            assert (
                enemy_id in enemy_ids
            ), f"story node '{node_id}' references missing enemy '{enemy_id}'"
        elif effect_type == "give_gold":
            _require_int(effect_map.get("amount"), f"story node '{node_id}' give_gold.amount")
        elif effect_type == "give_exp":
            _require_int(effect_map.get("amount"), f"story node '{node_id}' give_exp.amount")
        elif effect_type == "give_party_exp":
            _require_int(effect_map.get("amount"), f"story node '{node_id}' give_party_exp.amount")
        elif effect_type == "add_party_member":
            _require_str(
                effect_map.get("member_id"), f"story node '{node_id}' add_party_member.member_id"
            )
        elif effect_type == "goto":
            next_node = _require_str(
                effect_map.get("next"), f"story node '{node_id}' goto.next"
            )
            assert (
                next_node in story_nodes
            ), f"story node '{node_id}' goto references missing node '{next_node}'"
        elif effect_type == "set_flag":
            _require_str(effect_map.get("flag_id"), f"story node '{node_id}' set_flag.flag_id")
            value = effect_map.get("value", True)
            assert isinstance(value, bool), f"story node '{node_id}' set_flag.value must be boolean if provided"
        elif effect_type == "remove_item":
            _require_str(effect_map.get("item_id"), f"story node '{node_id}' remove_item.item_id")
            quantity = effect_map.get("quantity", 1)
            _require_int(quantity, f"story node '{node_id}' remove_item.quantity")
        elif effect_type == "branch_on_flag":
            _require_str(effect_map.get("flag_id"), f"story node '{node_id}' branch_on_flag.flag_id")
            expected = effect_map.get("expected", True)
            assert isinstance(expected, bool), (
                f"story node '{node_id}' branch_on_flag.expected must be boolean if provided"
            )
            next_on_true = _require_str(
                effect_map.get("next_on_true"), f"story node '{node_id}' branch_on_flag.next_on_true"
            )
            next_on_false = _require_str(
                effect_map.get("next_on_false"), f"story node '{node_id}' branch_on_flag.next_on_false"
            )
            assert (
                next_on_true in story_nodes
            ), f"story node '{node_id}' branch_on_flag.next_on_true references missing node '{next_on_true}'"
            assert (
                next_on_false in story_nodes
            ), f"story node '{node_id}' branch_on_flag.next_on_false references missing node '{next_on_false}'"
        else:
            # Unknown effect types are allowed for forward compatibility, but must at least be strings.
            _require_str(effect_type, f"story node '{node_id}' effect type")


def _validate_abilities(definitions_dir: Path) -> None:
    path = definitions_dir / "abilities.json"
    if not path.exists():
        pytest.skip("abilities.json is not present.")
    data = load_json(path)
    assert isinstance(data, dict), "abilities.json must contain an object"
    for ability_id, payload in data.items():
        _require_str(ability_id, "ability id")
        mapping = _require_mapping(payload, f"ability '{ability_id}'")
        _assert_allowed_fields(
            mapping,
            required={
                "name",
                "required_weapon_tags",
                "energy_cost",
                "target",
                "effect",
            },
            optional=set(),
            context=f"ability '{ability_id}'",
        )
        _require_str(mapping["name"], f"ability '{ability_id}' name")
        _require_str_list(
            mapping["required_weapon_tags"], f"ability '{ability_id}' required_weapon_tags"
        )
        _require_int(mapping["energy_cost"], f"ability '{ability_id}' energy_cost")
        _require_str(mapping["target"], f"ability '{ability_id}' target")
        effect = _require_mapping(mapping["effect"], f"ability '{ability_id}' effect")
        _require_str(effect.get("type"), f"ability '{ability_id}' effect.type")
        if "power" in effect:
            _require_number(effect["power"], f"ability '{ability_id}' effect.power")



def _validate_quests(
    definitions_dir: Path,
    *,
    item_ids: set[str],
    area_ids: set[str],
    story_node_ids: set[str],
) -> set[str]:
    data = _load_required_dict(definitions_dir, "quests.json")
    quests = _require_mapping(data.get("quests"), "quests.json.quests")
    quest_ids: set[str] = set()
    for quest_id, payload in quests.items():
        _require_str(quest_id, "quest id")
        mapping = _require_mapping(payload, f"quest '{quest_id}'")
        quest_id_value = _require_str(mapping.get("quest_id"), f"quest '{quest_id}' quest_id")
        assert quest_id_value == quest_id, f"quest '{quest_id}' quest_id must match key"
        _require_str(mapping.get("name"), f"quest '{quest_id}' name")
        prereqs = mapping.get("prereqs")
        if prereqs is not None:
            prereq_map = _require_mapping(prereqs, f"quest '{quest_id}' prereqs")
            _require_str_list(prereq_map.get("required_flags", []), f"quest '{quest_id}' required_flags")
            _require_str_list(prereq_map.get("forbidden_flags", []), f"quest '{quest_id}' forbidden_flags")
        objectives = mapping.get("objectives")
        assert isinstance(objectives, list) and objectives, f"quest '{quest_id}' objectives must be a list."
        for index, objective in enumerate(objectives):
            obj_map = _require_mapping(objective, f"quest '{quest_id}' objectives[{index}]")
            obj_type = _require_str(obj_map.get("type"), f"quest '{quest_id}' objectives[{index}].type")
            _require_str(obj_map.get("label"), f"quest '{quest_id}' objectives[{index}].label")
            quantity = obj_map.get("quantity", 1)
            assert isinstance(quantity, int) and quantity > 0, (
                f"quest '{quest_id}' objectives[{index}].quantity must be positive."
            )
            if obj_type == "kill_tag":
                _require_str(obj_map.get("tag"), f"quest '{quest_id}' objectives[{index}].tag")
            elif obj_type == "collect_item":
                item_id = _require_str(obj_map.get("item_id"), f"quest '{quest_id}' objectives[{index}].item_id")
                assert item_id in item_ids, f"quest '{quest_id}' objectives[{index}] unknown item '{item_id}'."
            elif obj_type == "visit_area":
                area_id = _require_str(obj_map.get("area_id"), f"quest '{quest_id}' objectives[{index}].area_id")
                if area_ids:
                    assert area_id in area_ids, (
                        f"quest '{quest_id}' objectives[{index}] unknown area '{area_id}'."
                    )
            else:
                raise AssertionError(
                    f"quest '{quest_id}' objectives[{index}].type must be kill_tag, collect_item, or visit_area."
                )
        turn_in = mapping.get("turn_in")
        if turn_in is not None:
            turn_in_map = _require_mapping(turn_in, f"quest '{quest_id}' turn_in")
            node_id = _require_str(turn_in_map.get("node_id"), f"quest '{quest_id}' turn_in.node_id")
            assert node_id in story_node_ids, (
                f"quest '{quest_id}' turn_in node '{node_id}' not found in story definitions"
            )
            npc_id = turn_in_map.get("npc_id")
            if npc_id is not None:
                _require_str(npc_id, f"quest '{quest_id}' turn_in.npc_id")
        rewards = _require_mapping(mapping.get("rewards"), f"quest '{quest_id}' rewards")
        if "gold" in rewards:
            _require_int(rewards["gold"], f"quest '{quest_id}' rewards.gold")
        if "party_exp" in rewards:
            _require_int(rewards["party_exp"], f"quest '{quest_id}' rewards.party_exp")
        items = rewards.get("items", [])
        assert isinstance(items, list), f"quest '{quest_id}' rewards.items must be a list."
        for index, entry in enumerate(items):
            entry_map = _require_mapping(entry, f"quest '{quest_id}' rewards.items[{index}]")
            item_id = _require_str(entry_map.get("item_id"), f"quest '{quest_id}' rewards.items[{index}].item_id")
            assert item_id in item_ids, f"quest '{quest_id}' rewards.items[{index}] unknown item '{item_id}'."
            _require_int(entry_map.get("quantity"), f"quest '{quest_id}' rewards.items[{index}].quantity")
        flags = rewards.get("set_flags", {})
        flags_map = _require_mapping(flags, f"quest '{quest_id}' rewards.set_flags")
        for flag_id, flag_value in flags_map.items():
            assert isinstance(flag_id, str), f"quest '{quest_id}' rewards.set_flags keys must be strings."
            assert isinstance(flag_value, bool), f"quest '{quest_id}' rewards.set_flags values must be boolean."
        _require_str_list(mapping.get("accept_flags", []), f"quest '{quest_id}' accept_flags")
        _require_str_list(mapping.get("complete_flags", []), f"quest '{quest_id}' complete_flags")
        quest_ids.add(quest_id)
    return quest_ids


def _load_required_dict(definitions_dir: Path, filename: str) -> dict[str, Any]:
    path = definitions_dir / filename
    assert path.exists(), f"{filename} is missing."
    data = load_json(path)
    assert isinstance(data, dict), f"{filename} must contain an object."
    return data


def _load_story_chapters(definitions_dir: Path) -> dict[str, Any]:
    story_dir = definitions_dir / "story"
    index_path = story_dir / "index.json"
    assert index_path.exists(), "story/index.json is missing."
    index_data = load_json(index_path)
    assert isinstance(index_data, dict), "story/index.json must contain an object."
    chapters = index_data.get("chapters")
    assert isinstance(chapters, list) and chapters, "story/index.json must define a non-empty 'chapters' list."
    combined: dict[str, Any] = {}
    chapters_dir = story_dir / "chapters"
    for entry in chapters:
        chapter_name = _require_str(entry, "story/index.json chapter entry")
        chapter_path = chapters_dir / chapter_name
        assert chapter_path.exists(), f"Story chapter '{chapter_name}' is missing."
        chapter_data = load_json(chapter_path)
        assert isinstance(chapter_data, dict), f"chapter '{chapter_name}' must contain an object."
        for node_id, payload in chapter_data.items():
            _require_str(node_id, "story node id")
            assert (
                node_id not in combined
            ), f"Duplicate story node id '{node_id}' detected between chapters."
            combined[node_id] = payload
    return combined


def _require_mapping(value: Any, context: str) -> dict[str, Any]:
    assert isinstance(value, dict), f"{context} must be an object/dict."
    return value


def _assert_allowed_fields(
    mapping: dict[str, Any],
    *,
    required: Iterable[str],
    optional: Iterable[str],
    context: str,
) -> None:
    required_set = set(required)
    optional_set = set(optional)
    actual = set(mapping.keys())
    missing = required_set - actual
    unknown = actual - required_set - optional_set
    assert not missing, f"{context} missing required fields: {sorted(missing)}"
    assert (
        not unknown
    ), f"{context} has unknown fields: {sorted(unknown)}"


def _require_str(value: Any, context: str) -> str:
    assert isinstance(value, str), f"{context} must be a string."
    return value


def _require_int(value: Any, context: str) -> int:
    assert isinstance(value, int) and not isinstance(value, bool), f"{context} must be an int."
    return value


def _require_str_list(value: Any, context: str) -> list[str]:
    assert isinstance(value, list), f"{context} must be a list."
    result: list[str] = []
    for entry in value:
        result.append(_require_str(entry, context))
    return result


def _require_attributes_mapping(value: Any, context: str) -> dict[str, int]:
    mapping = _require_mapping(value, context)
    expected = {"STR", "DEX", "INT", "VIT", "BOND"}
    actual = set(mapping.keys())
    missing = expected - actual
    extra = actual - expected
    assert not missing, f"{context} missing keys: {sorted(missing)}"
    assert not extra, f"{context} has unknown keys: {sorted(extra)}"
    values: dict[str, int] = {}
    for key in expected:
        raw = mapping.get(key)
        value_int = _require_int(raw, f"{context}.{key}")
        assert value_int >= 0, f"{context}.{key} must be non-negative."
        values[key] = value_int
    return values


def _validate_loot_tables(definitions_dir: Path, item_ids: set[str]) -> None:
    path = definitions_dir / "loot_tables.json"
    if not path.exists():
        return
    data = load_json(path)
    assert isinstance(data, list), "loot_tables.json must contain a list."
    seen_ids: set[str] = set()
    for index, entry in enumerate(data):
        context = f"loot_tables[{index}]"
        mapping = _require_mapping(entry, context)
        table_id = _require_str(mapping.get("id"), f"{context}.id")
        assert table_id not in seen_ids, f"{context}.id '{table_id}' is duplicated"
        seen_ids.add(table_id)
        _require_str_list(mapping.get("required_enemy_tags", []), f"{context}.required_enemy_tags")
        _require_str_list(mapping.get("forbidden_enemy_tags", []), f"{context}.forbidden_enemy_tags")
        drops = _require_list(mapping.get("drops"), f"{context}.drops")
        for drop_index, drop in enumerate(drops):
            drop_ctx = f"{context}.drops[{drop_index}]"
            drop_map = _require_mapping(drop, drop_ctx)
            item_id = _require_str(drop_map.get("item_id"), f"{drop_ctx}.item_id")
            assert item_id in item_ids, f"{drop_ctx}.item_id '{item_id}' not found in items.json"
            chance = _require_float(drop_map.get("chance", 0.0), f"{drop_ctx}.chance")
            assert 0.0 <= chance <= 1.0, f"{drop_ctx}.chance must be between 0 and 1"
            min_qty = _require_int(drop_map.get("min_qty", 1), f"{drop_ctx}.min_qty")
            max_qty = _require_int(drop_map.get("max_qty", min_qty), f"{drop_ctx}.max_qty")
            assert min_qty > 0 and max_qty >= min_qty, f"{drop_ctx} quantity range invalid"


def _require_list(value: Any, context: str) -> list[Any]:
    assert isinstance(value, list), f"{context} must be a list."
    return value


def _require_float(value: Any, context: str) -> float:
    assert isinstance(value, (int, float)) and not isinstance(value, bool), f"{context} must be a number."
    return float(value)


def _require_number(value: Any, context: str) -> float:
    assert isinstance(value, (int, float)) and not isinstance(value, bool), f"{context} must be a number."
    return float(value)


def _validate_party_members(
    definitions_dir: Path,
    weapon_ids: set[str],
    armour_ids: set[str],
) -> set[str]:
    path = definitions_dir / "party_members.json"
    if not path.exists():
        return set()
    data = load_json(path)
    assert isinstance(data, dict), "party_members.json must contain an object."
    member_ids: set[str] = set()
    for member_id, payload in data.items():
        _require_str(member_id, "party member id")
        mapping = _require_mapping(payload, f"party member '{member_id}'")
        _require_str(mapping.get("name"), f"party member '{member_id}' name")
        base_stats = _require_mapping(mapping.get("base_stats"), f"party member '{member_id}' base_stats")
        _require_int(base_stats.get("max_hp"), f"party member '{member_id}' base_stats.max_hp")
        _require_int(base_stats.get("max_mp"), f"party member '{member_id}' base_stats.max_mp")
        _require_int(base_stats.get("speed"), f"party member '{member_id}' base_stats.speed")
        _require_int(mapping.get("starting_level"), f"party member '{member_id}' starting_level")
        equipment = _require_mapping(mapping.get("equipment"), f"party member '{member_id}' equipment")
        weapons = _require_str_list(
            equipment.get("weapons", []), f"party member '{member_id}' equipment.weapons"
        )
        for weapon_id in weapons:
            assert weapon_id in weapon_ids, f"party member '{member_id}' references unknown weapon '{weapon_id}'"
        armour_id = equipment.get("armour")
        if armour_id is not None:
            armour_id = _require_str(armour_id, f"party member '{member_id}' equipment.armour")
            assert armour_id in armour_ids, f"party member '{member_id}' references unknown armour '{armour_id}'"
        armour_slots = equipment.get("armour_slots", {})
        armour_slots_map = _require_mapping(
            armour_slots, f"party member '{member_id}' equipment.armour_slots"
        )
        for slot, slot_armour_id in armour_slots_map.items():
            _require_str(slot, f"party member '{member_id}' equipment.armour_slots slot")
            slot_armour_id = _require_str(
                slot_armour_id, f"party member '{member_id}' equipment.armour_slots.{slot}"
            )
            assert (
                slot_armour_id in armour_ids
            ), f"party member '{member_id}' references unknown armour '{slot_armour_id}'"
        member_ids.add(member_id)
    return member_ids


def _validate_summons(definitions_dir: Path) -> set[str]:
    path = definitions_dir / "summons.json"
    if not path.exists():
        return set()
    data = load_json(path)
    assert isinstance(data, dict), "summons.json must contain an object."
    summon_ids: set[str] = set()
    for summon_id, payload in data.items():
        _require_str(summon_id, "summon id")
        mapping = _require_mapping(payload, f"summon '{summon_id}'")
        _require_str(mapping.get("name"), f"summon '{summon_id}' name")
        _require_int(mapping.get("max_hp"), f"summon '{summon_id}' max_hp")
        _require_int(mapping.get("max_mp"), f"summon '{summon_id}' max_mp")
        _require_int(mapping.get("attack"), f"summon '{summon_id}' attack")
        _require_int(mapping.get("defense"), f"summon '{summon_id}' defense")
        _require_int(mapping.get("speed"), f"summon '{summon_id}' speed")
        _require_int(mapping.get("bond_cost"), f"summon '{summon_id}' bond_cost")
        if "bond_scaling" in mapping:
            scaling = _require_mapping(mapping.get("bond_scaling"), f"summon '{summon_id}' bond_scaling")
            _require_number(scaling.get("hp_per_bond"), f"summon '{summon_id}' bond_scaling.hp_per_bond")
            _require_number(scaling.get("atk_per_bond"), f"summon '{summon_id}' bond_scaling.atk_per_bond")
            _require_number(scaling.get("def_per_bond"), f"summon '{summon_id}' bond_scaling.def_per_bond")
            _require_number(scaling.get("init_per_bond"), f"summon '{summon_id}' bond_scaling.init_per_bond")
        summon_ids.add(summon_id)
    return summon_ids


def _validate_knowledge(definitions_dir: Path) -> None:
    path = definitions_dir / "knowledge.json"
    if not path.exists():
        return
    data = load_json(path)
    assert isinstance(data, dict), "knowledge.json must contain an object."
    for member_id, payload in data.items():
        _require_str(member_id, "knowledge member id")
        mapping = _require_mapping(payload, f"knowledge '{member_id}'")
        entries = _require_list(mapping.get("known_enemies", []), f"knowledge '{member_id}' known_enemies")
        for index, entry in enumerate(entries):
            entry_map = _require_mapping(entry, f"knowledge '{member_id}' entry[{index}]")
            _require_str_list(entry_map.get("enemy_tags", []), f"knowledge '{member_id}' entry[{index}].enemy_tags")
            revealed = _require_mapping(
                entry_map.get("revealed_fields", {}), f"knowledge '{member_id}' entry[{index}].revealed_fields"
            )
            if "hp_range" in revealed:
                hp_range = _require_list(revealed.get("hp_range"), f"knowledge '{member_id}' entry[{index}].hp_range")
                assert len(hp_range) == 2, f"knowledge '{member_id}' entry[{index}].hp_range must have 2 values"
                _require_int(hp_range[0], f"knowledge '{member_id}' entry[{index}].hp_range[0]")
                _require_int(hp_range[1], f"knowledge '{member_id}' entry[{index}].hp_range[1]")


