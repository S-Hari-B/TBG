# Data Formats (V1)

This document defines the JSON formats used under `data/definitions/`.

Design goals:

* Data-driven content: enemies, items, weapons, armour, abilities, classes, story nodes are defined in JSON.
* Deterministic gameplay: definitions contain no randomness. Randomness is handled by the single RNG in code.
* Strict loading: repositories validate schemas and reject unknown/missing required fields.

---

## Shared Conventions

* IDs are lowercase `snake_case` strings.
* Tags are lowercase `snake_case` strings.
* All definition files are JSON.
* Definitions reference each other by string IDs (example: enemy references weapon_id).
* Prefer explicit fields over clever inference.

Where practical, prefer these top-level layouts:

Option A (recommended): list of objects

```json
[
  { "id": "bronze_sword", "...": "..." },
  { "id": "iron_sword", "...": "..." }
]
```

Option B: map of id to payload (allowed if already used)

```json
{
  "bronze_sword": { "...": "..." },
  "iron_sword": { "...": "..." }
}
```

Pick one per file and keep it consistent within that file.

---

## Tags

Initial tag groups:

Weapon type tags:

* sword, dagger, axe, club, staff, bow, shield

Damage tags:

* slash, pierce, blunt, fire, ice, lightning

Item tags:

* consumable, healing, energy_restore

Monster tags:

* goblin, beast, undead, humanoid, dragon

Tags are used for:

* ability gating (required_weapon_tags)
* knowledge matching (party member knows tag-based entries)
* future expansions (weaknesses, resistances, drops)

---

## Weapons (`weapons.json`)

Weapons (including shields) are keyed by id:

```json
{
  "iron_sword": { ... },
  "wooden_shield": { ... }
}
```

Fields (v1 data):

* `name`: string
* `attack`: int
* `value`: int
* `tags`: list[string] – must include canonical weapon-type tags such as `"sword"`, `"shield"`, `"staff"`, `"dagger"`, `"club"` so that skills can gate on them.
* `slot_cost`: int (1 or 2)
* `default_basic_attack_id`: string (used by factories to map to the correct basic attack animation/sfx later)
* `energy_bonus`: int (bonus MP/energy; Slice A keeps these at 0 except the staff)

Example:

```json
"iron_sword": {
  "name": "Iron Sword",
  "attack": 8,
  "value": 50,
  "tags": ["sword", "slash"],
  "slot_cost": 1,
  "default_basic_attack_id": "basic_slash",
  "energy_bonus": 0
}
```

```json
"wooden_shield": {
  "name": "Wooden Shield",
  "attack": 1,
  "value": 20,
  "tags": ["shield", "blunt"],
  "slot_cost": 1,
  "default_basic_attack_id": "basic_shield_bash",
  "energy_bonus": 0
}
```

---

## Armour (`armour.json`)

Armour pieces explicitly declare which slot they occupy. Valid slots are `head`, `body`, `hands`, and `boots`.

Fields:

* `name`: string
* `slot`: string (`"head"`, `"body"`, `"hands"`, `"boots"`)
* `defense`: int
* `value`: int
* `tags`: list[string]
* `hp_bonus`: int

Example:

```json
"iron_war_helm": {
  "name": "Iron War Helm",
  "slot": "head",
  "defense": 2,
  "value": 35,
  "tags": ["heavy_armour"],
  "hp_bonus": 2
}
```

---

## Items (`items.json`)

Items in v1 are consumables.

Fields (v1):

* id: string
* name: string
* description: string
* tags: list[string]
* item_type: string (v1: "consumable")
* value_gold: int
* effects: list[effect]

Effect object fields (v1):

* type: string ("heal_hp" | "restore_energy")
* amount: int

Example:

```json
{
  "id": "potion_hp_small",
  "name": "Small HP Potion",
  "description": "Restores a small amount of HP.",
  "tags": ["consumable", "healing"],
  "item_type": "consumable",
  "value_gold": 10,
  "effects": [{ "type": "heal_hp", "amount": 25 }]
}
```

---

## Abilities (`abilities.json`)

Abilities represent both basic attacks and special skills.
They are gated by weapon tags.

Fields (v1):

* id: string
* name: string
* description: string
* required_weapon_tags: list[string] (empty means always usable)
* energy_cost: int
* target: string ("single_enemy" | "all_enemies" | "self" | "single_ally")
* effect: object

Effect types (v1):

* deal_damage: { "power": float, "damage_tag": string }
* heal_hp: { "amount": int }

Example:

```json
{
  "id": "basic_slash",
  "name": "Slash",
  "description": "A simple sword strike.",
  "required_weapon_tags": ["sword"],
  "energy_cost": 0,
  "target": "single_enemy",
  "effect": { "type": "deal_damage", "power": 1.0, "damage_tag": "slash" }
}
```

---

## Skills (`skills.json`)

Weapon-tag skills live in their own file (map keyed by id). Fields (v1):

* `name`: string
* `description`: string
* `tags`: list[string] (classification helpers such as `"skill"`, `"starter"`, `"staff"`)
* `required_weapon_tags`: list[string] – every tag listed must be present on the actor’s equipped weapon/shield tags for the skill to appear in the CLI.
* `target_mode`: `"single_enemy"` | `"multi_enemy"` | `"self"`
* `max_targets`: int (only used for `"multi_enemy"`, but stored for all skills for future expansion)
* `mp_cost`: int
* `base_power`: int (damage/guard scalar)
* `effect_type`: `"damage"` | `"guard"`
* `gold_value`: int (placeholder for economy and shops)

Example:

```json
"skill_firebolt": {
  "name": "Firebolt",
  "description": "Launch a focused bolt of fire.",
  "tags": ["skill", "starter", "staff", "fire"],
  "required_weapon_tags": ["staff"],
  "target_mode": "single_enemy",
  "max_targets": 1,
  "mp_cost": 4,
  "base_power": 5,
  "effect_type": "damage",
  "gold_value": 25
}
```

```json
"skill_brace": {
  "name": "Brace",
  "description": "Raise your shield to absorb the next blow.",
  "tags": ["skill", "starter", "shield"],
  "required_weapon_tags": ["shield"],
  "target_mode": "self",
  "max_targets": 1,
  "mp_cost": 2,
  "base_power": 5,
  "effect_type": "guard",
  "gold_value": 18
}
```

---

## Enemies (`enemies.json`)

Enemy combat identity is a mix of base stats, tags, and optional equipment overrides.

Fields (v1):

* `name`: string
* `hp`, `mp`, `attack`, `defense`, `speed`: ints
* `tags`: list[string]
* `equipment`: optional { `weapons`: list[string], `armour`: string }
* `rewards_exp`, `rewards_gold`: ints

Notes:

* weapon_ids supports 1 or 2 weapons (slot rules still enforced in code).
* The knowledge system may hide these stats from the player by default.

Example:

```json
{
  "name": "Goblin Grunt",
  "hp": 22,
  "mp": 0,
  "attack": 5,
  "defense": 2,
  "speed": 6,
  "rewards_exp": 8,
  "rewards_gold": 3,
  "tags": ["goblin", "humanoid"],
  "equipment": { "weapons": ["goblin_dagger"], "armour": "goblin_rags" }
}
```

---

## Classes (`classes.json`)

Classes determine starting loadouts and initial inventory. No long-term class lock-in.

Fields:

* `name`: string
* `base_hp`: int
* `base_mp`: int
* `speed`: int
* `starting_weapon`: string (primary weapon id)
* `starting_weapons`: list[string] – ordered list of weapons to attempt to equip. Two-handed items consume both slots; extra items that cannot be equipped are added to the shared inventory.
* `starting_armour`: object mapping slot (`head`, `body`, `hands`, `boots`) to armour ids
* `starting_items`: object mapping item ids to stack counts
* `starting_abilities`: optional list of ability ids
* `starting_level`: int (defaults to 1 if omitted; used for XP distribution and level-up pacing)

Example:

```json
"warrior": {
  "name": "Warrior",
  "base_hp": 40,
  "base_mp": 6,
  "speed": 4,
  "starting_weapon": "iron_sword",
  "starting_weapons": ["iron_sword", "wooden_shield"],
  "starting_armour": {
    "body": "heavy_iron_armour_common",
    "head": "iron_war_helm",
    "hands": "iron_gauntlets",
    "boots": "iron_greaves"
  },
  "starting_items": {
    "potion_hp_small": 2,
    "potion_energy_small": 1
  },
  "starting_level": 1
}
```

---

## Party Members (`party_members.json`)

Party members define recruitable allies such as Emma. Fields mirror the class definition but also declare the exact level a recruit joins at:

* `name`: string
* `starting_level`: int (Emma is 3)
* `tags`: list[string]
* `base_stats`: { `max_hp`, `max_mp`, `speed` }
* `equipment`: { `weapons`: list[string], `armour_slots`: { slot: armour_id } }

---

## Party Inventory (runtime state)

`GameState` tracks a shared `inventory` object containing `weapons`, `armour`, and `items` maps (id → quantity). Each party member also has an `equipment` entry containing two `weapon_slots` and four `armour_slots` (`head`, `body`, `hands`, `boots`). The inventory/equipment UI manipulates these structures directly, and unequipping always returns the item to the shared pool.

---

## Areas (`areas.json`)

`areas.json` drives the overworld “Travel” interface. The file stores an object with a single `"areas"` array. Each entry declares:

* `id`: string — lowercase unique id (e.g. `village_outskirts`)
* `name`: string
* `description`: string
* `tags`: list[string] — lowercase tags such as `village`, `outskirts`, `forest`, `safe`. These tags allow future encounter gating/balance rules.
* `connections`: list of `{ "to": "<area_id>", "label": "<menu label>" }`. Connections are directional; add reciprocal entries explicitly.
* `entry_story_node_id`: optional string referencing a node in `story.json`. If present, that node auto-plays exactly once the first time the player arrives at the area.

Repositories validate that:

* Area ids are unique.
* Connection targets reference existing areas.
* `entry_story_node_id` values exist in `story.json`.

At runtime the single `AreaService` loads these definitions, keeps `GameState.current_location_id` synchronized, and tracks `visited_locations` (ordered list) plus a `location_entry_seen` map used to guard entry hooks.

---

## Loot Tables (`loot_tables.json`)

Loot tables are stored as a list. Each entry contains:

* `id`: string
* `required_enemy_tags`: list[string] – all tags must be present on the defeated enemy
* `forbidden_enemy_tags`: optional list[string]
* `drops`: list of `{ "item_id": str, "chance": float (0-1), "min_qty": int, "max_qty": int }`

Example:

```json
{
  "id": "goblin_horn_drop",
  "required_enemy_tags": ["goblin"],
  "drops": [
    { "item_id": "goblin_horn", "chance": 1.0, "min_qty": 1, "max_qty": 1 },
    { "item_id": "potion_energy_small", "chance": 0.25, "min_qty": 1, "max_qty": 1 }
  ]
}
```

Tables are matched in-order and every drop rolls using the single shared RNG to keep battle rewards reproducible.

---

## Story (`story.json`)

Story is a graph of nodes. Nodes can show text, offer choices, and apply effects.

Node fields (v1):

* id: string
* speaker: optional string
* text: string
* choices: list[choice]
* effects: list[effect] (applied on enter)
* next: optional string (default next node)

Choice fields:

* label: string
* next: string
* conditions: optional list (future)
* effects: optional list[effect] (applied on choosing)

Effect types (v1):

* set_flag { flag: string, value: bool }
* give_item { item_id: string, quantity: int }
* give_gold { amount: int }
* start_battle { enemy_id: string | enemy_ids: list[string] }
* add_party_member { member_id: string }
* enter_game_menu { message?: string } – halts flow, pushes the player into the camp/game menu before continuing to the node’s `next`.

Note:

* The vertical slice intro story nodes should align with docs/v1_vertical_slice.md.

---

## Save Files (`data/saves/slot_X.json`)

Manual saves are plain JSON written to `data/saves/slot_1.json` through `slot_3.json` and contain four top-level keys:

* `save_version`: integer schema version (v1 = `1`). Loaders refuse mismatched versions.
* `metadata`: presentation summary used when rendering the slot picker (player name, current node id, current location id, mode, gold, seed, ISO timestamp).
* `rng`: deterministic RNG snapshot (`{"version": 3, "state": [...], "gauss": null}`).
* `state`: serialized `GameState` (seed, mode, story node ids, current location id, visited locations, entry-story flags, pending narration, party roster, inventory/equipment, member levels/exp, flags, camp message, and the player object).

Example (trimmed):

```json
{
  "save_version": 1,
  "metadata": {
    "player_name": "Hero",
    "current_node_id": "post_ambush_menu",
    "current_location_id": "village_outskirts",
    "mode": "camp_menu",
    "gold": 42,
    "seed": 123456,
    "saved_at": "2026-01-10T12:00:00+00:00"
  },
  "rng": {
    "version": 3,
    "state": [seeded MT19937 integers...],
    "gauss": null
  },
  "state": {
    "seed": 123456,
    "mode": "camp_menu",
    "current_node_id": "post_ambush_menu",
    "current_location_id": "village_outskirts",
    "player_name": "Hero",
    "gold": 42,
    "exp": 18,
    "flags": {"tutorial_complete": true},
    "party_members": ["emma"],
    "pending_story_node_id": "forest_aftermath",
    "pending_narration": [{"node_id": "post_ambush_menu", "text": "..."}],
    "inventory": {
      "weapons": {"iron_sword": 1},
      "armour": {"leather_vest": 1},
      "items": {"potion_hp_small": 2}
    },
    "equipment": {
      "player_x1": {
        "weapon_slots": ["iron_sword", null],
        "armour_slots": {"head": null, "body": "leather_vest", "hands": null, "boots": null}
      }
    },
    "member_levels": {"player_x1": 2, "emma": 3},
    "member_exp": {"player_x1": 15, "emma": 0},
    "camp_message": "You take a moment to rest, patch gear, and talk before pressing on.",
    "visited_locations": ["village_outskirts"],
    "location_entry_seen": {"village_outskirts": true},
    "player": {
      "id": "player_x1",
      "name": "Hero",
      "class_id": "warrior",
      "stats": {
        "max_hp": 40,
        "hp": 35,
        "max_mp": 6,
        "mp": 6,
        "attack": 8,
        "defense": 4,
        "speed": 4
      }
    }
  }
}
```

All ids inside `state` are validated against the current `data/definitions`. If any referenced weapon, armour, item, class, party member, or story node is missing, the load fails with `Save incompatible with current definitions`. Missing keys or malformed types also raise `SaveLoadError`. Because the RNG snapshot is restored verbatim, any random operation after loading produces the same outcome as it would have without saving.

---

## Knowledge (Planned)

Knowledge is a deterministic mechanic. The optional LLM is presentation-only.
See docs/knowledge_system.md for rules.

A future `knowledge.json` may define:

* party_member_id
* known_enemy_tags
* level_caps
* revealed_fields (hp_range, speed_hint, weaknesses, abilities, etc.)
