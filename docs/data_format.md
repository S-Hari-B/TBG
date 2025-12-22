Title: Data Definitions

All definition files live under `data/definitions/` and are plain JSON objects that map an ID to a payload. IDs are lowercase snake_case strings. Each repository enforces strict schemas, so unknown or missing fields will fail during load.

## Shared Conventions

- Top-level JSON object: `{ "<id>": { ...payload... }, ... }`
- IDs must be strings
- All numeric fields are integers
- No optional fields yet; each payload must contain exactly the required keys

## items.json

Payload fields:
- `name` (string)
- `description` (string)
- `type` (string, e.g., `"consumable"`)
- `effects` (list of effect objects)
- `value` (int gold value)

Effect object:
- `kind` (string, e.g., `"heal_hp"`)
- `amount` (int)

Example:
```json
"hp_potion": {
  "name": "HP Potion",
  "description": "Restores 30 HP.",
  "type": "consumable",
  "effects": [{ "kind": "heal_hp", "amount": 30 }],
  "value": 25
}
```

## weapons.json

Payload fields: `name` (string), `attack` (int), `value` (int).

## armour.json

Payload fields: `name` (string), `defense` (int), `value` (int).

## enemies.json

Payload fields:
- `name` (string)
- `max_hp`, `attack`, `defense`, `xp`, `gold` (ints)

## classes.json

Payload fields:
- `name` (string)
- `base_hp`, `base_mp` (ints)
- `starting_weapon` (string weapon id)
- `starting_armour` (string armour id)

`starting_weapon` and `starting_armour` must reference IDs that exist in the weapon and armour repositories. The Classes repository performs this validation when loading.


