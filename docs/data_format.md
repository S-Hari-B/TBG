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

Weapons can be one-handed or two-handed via `slot_cost`.
Shields are weapons.

Fields (v1):

* id: string
* name: string
* description: string
* tags: list[string]
* base_attack: int
* slot_cost: int (1 or 2)
* default_basic_attack_id: string (ability id)
* bonus_max_energy: int (added to actor base max_energy)
* value_gold: int

Example:

```json
{
  "id": "iron_sword",
  "name": "Iron Sword",
  "description": "A sturdy one-handed sword.",
  "tags": ["sword", "slash"],
  "base_attack": 8,
  "slot_cost": 1,
  "default_basic_attack_id": "basic_slash",
  "bonus_max_energy": 0,
  "value_gold": 50
}
```

Shield example:

```json
{
  "id": "wooden_shield",
  "name": "Wooden Shield",
  "description": "Basic protection, surprisingly decent.",
  "tags": ["shield", "blunt"],
  "base_attack": 1,
  "slot_cost": 1,
  "default_basic_attack_id": "basic_shield_bash",
  "bonus_max_energy": 0,
  "value_gold": 20
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
