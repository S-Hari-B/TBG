## Summons (Ticket 24a)

This document introduces the summon data format and the minimal domain metadata for summons.

### Purpose

- Add JSON-driven summon definitions.
- Add domain metadata so summons can be represented as battle combatants later.

### Non-goals

- No gameplay changes.
- No summon spawning or battle logic changes.
- No story or class changes.

### Summon Definitions

Summon definitions live in `data/definitions/summons.json` as a top-level object keyed by `summon_id`.

Required fields per summon:

- `name` (string)
- `max_hp` (int)
- `max_mp` (int)
- `attack` (int)
- `defense` (int)
- `speed` (int)
- `bond_cost` (int)

Optional fields:

- `tags` (list of strings)

Example:

```json
{
  "micro_raptor": {
    "name": "Micro Raptor",
    "max_hp": 20,
    "max_mp": 0,
    "attack": 6,
    "defense": 2,
    "speed": 7,
    "bond_cost": 5,
    "tags": ["beast", "raptor"]
  }
}
```

### Bond Cost

`bond_cost` represents a summon’s future bond requirement. Later tickets will use this to limit how many summons can be active at once.

### Battle Representation

Summons are intended to be represented as `Combatant` instances with an `owner_id` and `bond_cost` set. No spawning logic exists yet in 24a.

### Summon Instances in Battle

Summon injection exists as an internal BattleService helper. It creates a summon combatant, injects it into the ally list, rebuilds turn order, and emits a `SummonSpawnedEvent`.

`SummonSpawnedEvent` fields:

- `owner_id`
- `summon_id`
- `summon_instance_id`
- `summon_name`
- `bond_cost` (optional)

This helper is not exposed to player actions yet.

### Auto-Spawn at Battle Start (24d)

When a battle starts, the player’s equipped summons are auto-spawned as allies using BOND capacity:

- Capacity = player `BOND` points.
- Each summon consumes its `bond_cost`.
- Summons are processed in equipped order.
- **Rule:** stop when the first summon cannot fit in remaining capacity.

Summons are created fresh each battle at full HP/MP and do not persist after the battle ends.

### Fractional Bond Scaling (24e)

`bond_scaling` values may be integers or decimals. Scaling is deterministic and final stats are floored to integers when calculated.

### Known vs Equipped Summons

- **Known summons** are defined by the player’s class and stored in `classes.json`.
- **Equipped summons** are a player-managed loadout stored on the player state and persisted in saves.

### Managing Summons

Summon loadouts can be viewed and updated from:

- Camp/town menus (Summons option)
- Inventory / Equipment menu (Summons shortcut + equipped list)

This does not affect battles yet. Auto-spawn and bond capacity checks are introduced in later tickets.

### Save/Load Notes

`equipped_summons` is stored on the player in save data. Older saves without this field load with an empty list.
