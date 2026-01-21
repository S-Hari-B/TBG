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
* targeting: string (optional, defaults to `"self"`)
* debuff_attack_flat: int (optional; mutually exclusive with `debuff_defense_flat`)
* debuff_defense_flat: int (optional; mutually exclusive with `debuff_attack_flat`)

Effect object fields (v1):

* type: string ("heal_hp" | "restore_energy")
* amount: int

Targeting controls who can be chosen when the item is used during battle. Supported values:

* `self` – item may only be used on the acting character.
* `ally` – any living party member (including the player) can be targeted.
* `enemy` – currently used by debuff consumables; applying one targets a single living enemy.
* `any` – future-proofing for items that can target either side; currently blocked.

Existing data omitting this field automatically defaults to `self` for save compatibility.

Debuff fields are optional and only valid for enemy-targeting consumables. Exactly one of `debuff_attack_flat`
or `debuff_defense_flat` may be provided, and values are clamped to non-negative integers. Attack and defense debuffs
reduce the target's effective stats by a flat amount for the remainder of the current round and the entirety of the
next round, expiring automatically at the start of the following round with a visible battle event (suppressed when the
enemy is already defeated).

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
Attributes now feed derived combat stats (see docs/gameplay.md).

Fields:

* `name`: string
* `base_hp`: int
* `base_mp`: int
* `speed`: int
* `starting_attributes`: object with `STR`, `DEX`, `INT`, `VIT`, `BOND` (ints, non-negative)
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
  "starting_attributes": {
    "STR": 8,
    "DEX": 4,
    "INT": 2,
    "VIT": 6,
    "BOND": 0
  },
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
Attributes now feed derived combat stats (see docs/gameplay.md).

* `name`: string
* `starting_level`: int (Emma is 3)
* `tags`: list[string]
* `base_stats`: { `max_hp`, `max_mp`, `speed` }
* `starting_attributes`: object with `STR`, `DEX`, `INT`, `VIT`, `BOND` (ints, non-negative)
* `equipment`: { `weapons`: list[string], `armour_slots`: { slot: armour_id } }

---

## Party Inventory (runtime state)

`GameState` tracks a shared `inventory` object containing `weapons`, `armour`, and `items` maps (id → quantity). Each party member also has an `equipment` entry containing two `weapon_slots` and four `armour_slots` (`head`, `body`, `hands`, `boots`). The inventory/equipment UI manipulates these structures directly, and unequipping always returns the item to the shared pool.

---

## Floors (`floors.json`)

`floors.json` defines floor metadata for AreaServiceV2.

Top-level layout: object keyed by floor id.

Fields per floor:

* `name`: string
* `level`: int (>= 0)
* `starting_location_id`: string (must exist in `locations.json`)
* `boss_location_id`: optional string
* `next_floor_id`: optional string
* `notes`: optional string (designer-facing)

---

## Locations (`locations.json`)

`locations.json` defines floor-based locations for AreaServiceV2 and is the runtime source of truth for travel.

Top-level layout: object keyed by location id.

Fields per location:

* `name`: string
* `description`: string (required, may be empty)
* `floor_id`: string (must exist in `floors.json`)
* `type`: string enum (`town`, `open`, `side`, `story`, `secret`, `boss`, `gate`)
* `area_level`: optional int (>= 0). When present, overrides the floor’s level for enemy stat scaling.
* `tags`: list[string] — lowercase, non-empty
* `entry_story_node_id`: string or null
* `npcs_present`: optional list of `{ "npc_id": string, "talk_node_id": string|null, "quest_hub_node_id": string|null }`
* `connections`: list of `{ "to": "<location_id>", "label": "<menu label>", "progresses_story": bool, "requires_quest_active"?: string, "hide_if_quest_completed"?: string, "hide_if_quest_turned_in"?: string, "show_if_flag_true"?: string, "hide_if_flag_true"?: string }`. `progresses_story` defaults to `false`.

The connection gating fields mirror the v1 area rules and are enforced by AreaServiceV2.

---

## Quests (`quests.json`)

`quests.json` stores quest definitions as a JSON object with a single `quests` map. Each quest entry includes:

* `quest_id`: string (must match the map key)
* `name`: string
* `prereqs`: optional `{ "required_flags": [string], "forbidden_flags": [string] }`
* `objectives`: list of objective definitions:
  * `kill_tag { "tag": string, "quantity": int, "label": string }`
  * `collect_item { "item_id": string, "quantity": int, "label": string }`
  * `visit_area { "area_id": string, "quantity": int, "label": string }`
* `turn_in`: optional `{ "node_id": string, "npc_id"?: string }` (story node to route into for turn-in)
* `rewards`: `{ "gold": int, "party_exp": int, "items": [ { "item_id": string, "quantity": int } ], "set_flags": { flag_id: bool } }`
* `accept_flags`: optional list of legacy flags to set when the quest is accepted
* `complete_flags`: optional list of legacy flags to set when the quest objectives are completed

Repositories validate referenced item ids, area ids, and turn-in story node ids so quests remain data-driven and deterministic.

---

## Shops (`shops.json`)

`shops.json` stores deterministic shop definitions as a JSON object with a single `shops` map. Each shop entry includes:

* `id`: string (must match the map key)
* `name`: string
* `shop_type`: `"item" | "weapon" | "armour"`
* `tags`: list[string] – shop is available when the current location tags intersect this list
* `stock_pool`: list of `{ "id": string, "qty": int }` entries – ids and per-visit stock quantities
* `stock_size`: optional int (default 10)

Stock selection is deterministic: each shop uses `location_visits[location_id] % num_pages` to pick the stock page from `stock_pool`. Each entry’s `qty` sets the finite supply for the current visit; quantities reset when the player leaves and returns. Repositories validate stock ids against the relevant definition file (`items.json`, `weapons.json`, `armour.json`).

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

## Story Chapters (`story/index.json` + `story/chapters/*.json`)

Story content now lives under `data/definitions/story/`. The structure is:

```
story/
  index.json
  chapters/
    chapter_00_tutorial.json
    ...
```

`index.json` contains an ordered `"chapters"` list. StoryRepository loads each chapter file in that order, merges every node into a single dictionary, and raises validation errors when a chapter is missing, a node id is duplicated, or any `next`/choice reference points to an unknown node.

Each chapter file is a JSON object keyed by node id:

```json
{
  "node_id": { "...": "..." },
  "another_node": { "...": "..." }
}
```

Node schema (per entry) matches the previous single-file layout:

* `id`: implied by the object key; must be globally unique across all chapters.
* `text`: string (required)
* `effects`: optional list[effect] applied immediately on enter
* `choices`: optional list[choice]
* `next`: optional string (default continuation when no choices are present)

Choice schema:

* `label`: string
* `next`: string (required until branching rules exist)
* `effects`: optional list[effect] run before jumping to `next`

Effect types supported in v1:

* `set_class { "class_id": string }`
* `start_battle { "enemy_id": string }`
* `add_party_member { "member_id": string }`
* `give_gold { "amount": int }`
* `give_exp { "amount": int }`
* `give_party_exp { "amount": int }` – awards EXP across the active party (same split as battle rewards)
* `enter_game_menu { "message"?: string }` – halts flow and pushes the player to Camp Menu before resuming at `next`
* `set_flag { "flag_id": string, "value"?: bool }` – stores/overrides boolean flags in `GameState.flags`
* `remove_item { "item_id": string, "quantity"?: int }` – removes items from shared inventory (fails if insufficient)
* `branch_on_flag { "flag_id": string, "expected"?: bool, "next_on_true": string, "next_on_false": string }` – conditional branch by flag state
* `quest { "action": "accept" | "turn_in", "quest_id": string }` – delegates quest acceptance or turn-in to `QuestService`

Because the repository enforces chapter order, story progression stays deterministic even as additional chapters ship later.

Note:

* Area `entry_story_node_id` fields reference node ids defined inside these chapter files.
* The vertical slice intro story nodes should align with docs/v1_vertical_slice.md.

---

## Save Files (`data/saves/slot_X.json`)

Manual saves are plain JSON written to `data/saves/slot_1.json` through `slot_3.json` and contain four top-level keys:

* `save_version`: integer schema version (v1 = `1`). Loaders refuse mismatched versions.
* `metadata`: presentation summary used when rendering the slot picker (player name, current node id, current location id, mode, gold, seed, ISO timestamp).
* `rng`: deterministic RNG snapshot (`{"version": 3, "state": [...], "gauss": null}`).
* `state`: serialized `GameState` (seed, mode, story node ids, current location id, visited locations, entry-story flags, visit counts, pending narration, party roster, inventory/equipment, member levels/exp, base attributes, flags, camp message, checkpoint metadata, quest progress, and the player object).

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
    "flags": {"tutorial_complete": true, "flag_last_battle_defeat": false},
    "party_members": ["emma"],
    "player_attributes": {"STR": 8, "DEX": 4, "INT": 2, "VIT": 6, "BOND": 0},
    "party_member_attributes": {"emma": {"STR": 2, "DEX": 4, "INT": 10, "VIT": 4, "BOND": 0}},
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
    "location_visits": {"village_outskirts": 0},
    "shop_stock_remaining": {
      "village_outskirts": {
        "threshold_inn_item_shop": {"potion_hp_small": 7}
      }
    },
    "shop_stock_visit_index": {"village_outskirts": {"threshold_inn_item_shop": 0}},
    "story_checkpoint_node_id": "forest_ambush",
    "story_checkpoint_location_id": "village_outskirts",
    "story_checkpoint_thread_id": "main_story",
    "quests_active": {
      "cerel_kill_hunt": {
        "objectives": [
          {"current": 4, "completed": false},
          {"current": 2, "completed": false}
        ]
      }
    },
    "quests_completed": [],
    "quests_turned_in": [],
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

Additional state fields:

* `story_checkpoint_node_id`: string | null — the most recent story node that should be replayed if the player was defeated. When non-null, Camp Menu’s “Continue story” rewinds to that node instead of skipping ahead.
* `story_checkpoint_location_id`: string | null — the area id the player must return to before replaying the checkpoint encounter. Continue auto-warps to this location when needed.
* `story_checkpoint_thread_id`: string | null — identifier describing which checkpoint thread is active (`"main_story"` today; quests can introduce additional threads later). Thread ids keep different checkpoint categories from interfering with one another.
* `location_visits`: map of area id → int — deterministic visit counts used for systems like shop stock rotation.
* `shop_stock_remaining`: map of location id → shop id → item id → remaining qty for the current visit.
* `shop_stock_visit_index`: map of location id → shop id → visit count used to determine when to restock.
* `quests_active`: map of quest id → `{ "objectives": [ { "current": int, "completed": bool } ] }`
* `quests_completed`: list[string] — quest ids that have completed objectives
* `quests_turned_in`: list[string] — quest ids that have been turned in for rewards

---

## Knowledge (Planned)

Knowledge is a deterministic mechanic. The optional LLM is presentation-only.
See docs/knowledge_system.md for rules.

A future `knowledge.json` may define:

* party_member_id
* known_enemy_tags
* level_caps
* revealed_fields (hp_range, speed_hint, weaknesses, abilities, etc.)
