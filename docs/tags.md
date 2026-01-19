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
| spear  | Polearms (Piercing Thrust, Sweeping Polearm) |

Secondary tags (e.g., `slash`, `blunt`, `fire`) can be combined with the primary tags for future resistances and knowledge hooks.

## Enemy Tags

| Tag     | Notes                                 |
|---------|---------------------------------------|
| goblin  | Goblin foes (Emma’s knowledge entry)  |
| humanoid| Used for general lore/knowledge hooks |
| beast   | Wolves, boars, other animals          |
| wolf    | Wolf-specific drops and quest hooks   |
| orc     | Half-orc foes, heavier melee enemies  |
| bandit  | Human raiders (future story beats)    |
| slime   | Slime creatures                        |
| ooze    | Variant of slime enemies               |

## Area / Location Tags

| Tag        | Notes                                                  |
|------------|--------------------------------------------------------|
| safe       | Areas without random encounters                        |
| town       | Settlement hubs (shops, NPCs)                          |
| hub        | Travel hubs with multiple connections                  |
| plains     | Open grasslands and farmland                           |
| cave       | Underground tunnel networks                            |
| open       | Open farming areas with repeatable battles             |
| story      | Story-critical areas with forced encounters            |
| gate       | Transition points between floors                       |
| boss       | Boss/guardian locations (usually locked)               |
| locked     | Visible but inaccessible locations                     |
| ruins      | Ancient/abandoned structures                           |
| optional   | Side content, not required for main progression        |
| floor_zero | Tutorial/starting floor content                        |
| floor_one  | First main floor content                               |
| legacy     | Deprecated locations preserved for save compatibility  |

## Usage Summary

* `required_weapon_tags` in `skills.json` must match the tags supplied by equipped weapons/shields. The warrior starter kit exposes both `sword` and `shield`, while the mage’s staff exposes `staff`.
* Knowledge entries reference enemy tags so Party Talk can return deterministic intel lines.
* Area tags feed future Travel gating/balance logic; keep them lowercase and document any new tags added to `areas.json`.
* Shop availability is matched against area tags; shop definitions declare their own tags and are offered when they intersect the current location tags.
* Keep tags data-driven—introduce new tags by documenting them here first so all data files stay aligned.


