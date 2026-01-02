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

Armour is passive defense and modifiers.

Fields (v1):

* id: string
* name: string
* description: string
* slot: string (v1: "body")
* base_defense: int
* tags: list[string]
* bonus_max_hp: int
* value_gold: int

Example:

```json
{
  "id": "iron_armour_common",
  "name": "Iron Armour (Common)",
  "description": "Standard issue protection.",
  "slot": "body",
  "base_defense": 6,
  "tags": ["heavy_armour"],
  "bonus_max_hp": 10,
  "value_gold": 80
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

Enemy combat identity is a mix of base stats, equipment, and tags.

Fields (v1):

* id: string
* name: string
* level: int
* tags: list[string]
* base_stats: { max_hp: int, max_energy: int, speed: int }
* equipment: { weapon_ids: list[string], armour_id: string }
* rewards: { exp: int, gold: int }

Notes:

* weapon_ids supports 1 or 2 weapons (slot rules still enforced in code).
* The knowledge system may hide these stats from the player by default.

Example:

```json
{
  "id": "goblin_grunt",
  "name": "Goblin Grunt",
  "level": 1,
  "tags": ["goblin", "humanoid"],
  "base_stats": { "max_hp": 22, "max_energy": 0, "speed": 5 },
  "equipment": { "weapon_ids": ["rusty_dagger"], "armour_id": "leather_rags" },
  "rewards": { "exp": 6, "gold": 3 }
}
```

---

## Classes (`classes.json`)

Classes determine starting loadout only.
No long-term class lock-in.

Fields (v1):

* id: string
* name: string
* description: string
* starting_stats: { max_hp: int, max_energy: int, speed: int }
* starting_equipment:

  * weapon_ids: list[string]
  * armour_id: string
* starting_items: list[{ item_id: string, quantity: int }]

Example:

```json
{
  "id": "warrior",
  "name": "Warrior",
  "description": "Sword and shield, heavy armour, steady fundamentals.",
  "starting_stats": { "max_hp": 40, "max_energy": 6, "speed": 4 },
  "starting_equipment": {
    "weapon_ids": ["iron_sword", "wooden_shield"],
    "armour_id": "iron_armour_common"
  },
  "starting_items": [
    { "item_id": "potion_hp_small", "quantity": 2 },
    { "item_id": "potion_energy_small", "quantity": 1 }
  ]
}
```

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

## Knowledge (Planned)

Knowledge is a deterministic mechanic. The optional LLM is presentation-only.
See docs/knowledge_system.md for rules.

A future `knowledge.json` may define:

* party_member_id
* known_enemy_tags
* level_caps
* revealed_fields (hp_range, speed_hint, weaknesses, abilities, etc.)
