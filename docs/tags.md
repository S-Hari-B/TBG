# Tag Reference (V1)

Tags are short lowercase identifiers used across definitions for gating and lookup. Keep spellings consistent—repositories treat tags as case-sensitive strings.

## Weapon / Shield Tags

| Tag    | Notes                               |
|--------|-------------------------------------|
| sword  | One-handed swords (Power Slash)     |
| shield | Shield items (Brace guard skill)    |
| dagger | Light blades (Quick Stab)           |
| club   | Blunt weapons (Skull Thump)         |
| staff  | Focus items for mages (Firebolt/Ember Wave) |

Secondary tags (e.g., `slash`, `blunt`, `fire`) can be combined with the primary tags for future resistances and knowledge hooks.

## Enemy Tags

| Tag     | Notes                                 |
|---------|---------------------------------------|
| goblin  | Goblin foes (Emma’s knowledge entry)  |
| humanoid| Used for general lore/knowledge hooks |

## Usage Summary

* `required_weapon_tags` in `skills.json` must match the tags supplied by equipped weapons/shields. The warrior starter kit exposes both `sword` and `shield`, while the mage’s staff exposes `staff`.
* Knowledge entries reference enemy tags so Party Talk can return deterministic intel lines.
* Keep tags data-driven—introduce new tags by documenting them here first so all data files stay aligned.


