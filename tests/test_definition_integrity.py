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
        "areas.json",
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
    _validate_loot_tables(definitions_dir, items)
    story_node_ids = _validate_story(definitions_dir, classes, enemies)
    _validate_abilities(definitions_dir)
    _validate_areas(definitions_dir, story_node_ids)
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
            optional={"heal_hp", "heal_mp", "restore_energy"},
            context=f"item '{item_id}'",
        )
        _require_str(mapping["name"], f"item '{item_id}' name")
        _require_str(mapping["kind"], f"item '{item_id}' kind")
        _require_int(mapping["value"], f"item '{item_id}' value")
        for field in ("heal_hp", "heal_mp", "restore_energy"):
            if field in mapping:
                _require_int(mapping[field], f"item '{item_id}' {field}")
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
            },
            optional={"starting_weapons", "starting_items", "starting_abilities", "starting_level"},
            context=f"class '{class_id}'",
        )
        _require_str(mapping["name"], f"class '{class_id}' name")
        _require_int(mapping["base_hp"], f"class '{class_id}' base_hp")
        _require_int(mapping["base_mp"], f"class '{class_id}' base_mp")
        _require_int(mapping["speed"], f"class '{class_id}' speed")
        starting_weapon = _require_str(
            mapping["starting_weapon"], f"class '{class_id}' starting_weapon"
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


def _validate_areas(definitions_dir: Path, story_node_ids: set[str]) -> set[str]:
    path = definitions_dir / "areas.json"
    assert path.exists(), "areas.json is missing."
    data = load_json(path)
    assert isinstance(data, dict), "areas.json must contain an object."
    entries = data.get("areas")
    assert isinstance(entries, list), "areas.json.areas must be a list."
    staged: dict[str, dict[str, object]] = {}
    for entry in entries:
        mapping = _require_mapping(entry, "area entry")
        area_id = _require_str(mapping.get("id"), "area id")
        assert area_id not in staged, f"Duplicate area id '{area_id}'."
        staged[area_id] = mapping
    for area_id, mapping in staged.items():
        _require_str(mapping.get("name"), f"area '{area_id}' name")
        _require_str(mapping.get("description"), f"area '{area_id}' description")
        tags = _require_str_list(mapping.get("tags"), f"area '{area_id}' tags")
        assert tags, f"area '{area_id}' must declare at least one tag."
        assert all(tag == tag.lower() for tag in tags), f"area '{area_id}' tags must be lowercase."
        connections = mapping.get("connections")
        assert isinstance(connections, list), f"area '{area_id}' connections must be a list."
        for index, connection in enumerate(connections):
            conn_map = _require_mapping(connection, f"area '{area_id}' connections[{index}]")
            to_id = _require_str(conn_map.get("to"), f"area '{area_id}' connections[{index}].to")
            assert to_id in staged, f"area '{area_id}' references unknown destination '{to_id}'."
            _require_str(conn_map.get("label"), f"area '{area_id}' connections[{index}].label")
        entry_story = mapping.get("entry_story_node_id")
        if entry_story is not None:
            entry_story_id = _require_str(entry_story, f"area '{area_id}' entry_story_node_id")
            assert entry_story_id in story_node_ids, (
                f"area '{area_id}' entry_story_node_id '{entry_story_id}' not found in story definitions"
            )
    return set(staged.keys())


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


def _validate_loot_tables(definitions_dir: Path, item_ids: set[str]) -> None:
    path = definitions_dir / "loot_tables.json"
    if not path.exists():
        return
    data = load_json(path)
    assert isinstance(data, list), "loot_tables.json must contain a list."
    for index, entry in enumerate(data):
        context = f"loot_tables[{index}]"
        mapping = _require_mapping(entry, context)
        _require_str(mapping.get("id"), f"{context}.id")
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


