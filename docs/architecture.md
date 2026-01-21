# Architecture and Responsibilities (V1)

TBG is structured with strict layering to keep core rules deterministic, testable, and independent from the CLI.

Layers:

## presentation (CLI)

* Renders text to the user
* Reads and validates user input
* Calls services **or controllers** to perform actions
* Owns slot-based save file I/O through a tiny adapter (`SaveSlotStore`) that reads/writes `data/saves/slot_X.json`; serialization logic remains in the services layer
* Never computes combat outcomes or modifies domain objects directly
* Debug-only instrumentation (seed/node/location headers, Location Debug menu, extra load slot metadata) lives exclusively in this layer so lower layers stay pure
  * Owns the boxed battle renderer: 60-character ASCII panels for turn headers, battlefield snapshots, per-turn results, and player-only menus. Services only expose structured `BattleView` snapshots/events, keeping layout concerns isolated to the CLI. Long text in boxed panels (RESULTS, Party Talk) is word-wrapped at render time to preserve readability without breaking the fixed 60-char borders.
  * The battle state panel is width-aware in the CLI and expands columns when the terminal allows; debug-only enemy scaling details are rendered as wrapped second lines.
* **Battle rendering is tied to decision points, not input loops**: The state panel renders once per player turn, regardless of invalid input retries. See `battle_controller.md`.

## services (orchestration)

* Runs use cases (start game, advance story, start battle, apply action)
* Loads definitions via repositories
* Constructs domain entities using factories
* Owns GameState (overall runtime state)
* Initializes base attributes from definitions, persists them through SaveService, and keeps them purely informational until future scaling work lands
* Returns structured results and events for presentation to render
* Implements persistence orchestration (`SaveService`) to serialize/deserialize `GameState` + RNG snapshots, validate ids against current definitions, and guard against schema/version drift
* Maintains auxiliary services such as `AreaServiceV2` (floor-based location state, travel events, entry-story hooks), `QuestService` (quest acceptance/progress/turn-in), `ShopService` (deterministic shop stock + transactions), and `SaveService` (v2 save format validated against `locations.json`) so the CLI stays declarative and story remains data-driven
* **Controllers**: UI-agnostic orchestration layer (e.g., `BattleController`) that wraps services and exposes structured state + actions. Controllers do NOT print, format, or prompt—they only progress state and return events. See `battle_controller.md` for details.

## domain (game rules)

* Pure game rules and state transitions
* Entities: actors, party members, enemies, inventory state
* Combat rules, actions, effects, initiative
* No printing, no file I/O, no input(), no global randomness
* Attribute scaling lives in a domain helper that turns base stats + attributes into derived combat stats
* Base stats are computed in services from class baselines + equipment, then passed into the domain helper for final stats
* Enemy stat scaling lives in a domain helper and is applied in BattleService using floor/area levels from repositories

## data (definitions and loading)

* JSON loaders and repositories
* Validates and returns definitions
* No combat rules, no printing
* Includes the location repositories (`FloorsRepository`, `LocationsRepository`) which enforce unique ids, valid travel connections, and entry-story references back into the story definitions
* `StoryRepository` reads `story/index.json`, loads the referenced chapter files in order, merges every node, and rejects duplicate ids or broken `next`/choice references. Legacy content (nodes from old story versions that must remain for save compatibility) is separated into dedicated `_legacy_redirects.json` chapter files to keep the main tutorial chapter clean while ensuring old saves don't crash.

## core (shared utilities)

* RNG wrapper and seed handling
* Result types and errors
* Small helpers only

## ai (optional seam)

* Interface for Party Talk response generation
* Stub implementation in v1
* Later: local LLM + RAG behind same interface
* AI must not change facts or gameplay outcomes

---

## Determinism and RNG Policy

* The game uses exactly one RNG instance, created from the game seed at New Game.
* Domain logic never calls Python’s random module directly.
* Any random event must use the injected RNG.
* Important random choices should emit events describing the roll (example: initiative tie-break d20).

---

## Event-Driven Output

Domain logic emits Events, not printed strings.
Presentation renders those events into text.

Example combat events:

* TurnStarted(actor_id)
* AttackDeclared(attacker_id, target_id, ability_id)
* DamageDealt(attacker_id, target_id, amount)
* ActorDefeated(actor_id)

---

## Save Format (V2)

Save files now use `save_version: 2` and are validated against `locations.json`. Older save formats are intentionally unsupported during the alpha refactor; load attempts should surface a short “Save format changed (alpha)” message in the CLI.

## Party and Equipment

### Party

* Max party size is 4.
* Party members are added or removed via story effects (data-driven).
* Party members are strategic assets due to the Knowledge system (Party Talk).

### Base stats vs derived stats

Actors store base stats and equipment references.
Combat uses derived stats computed from equipment.

Base stats:

* max_hp, hp
* max_energy, energy
* speed
* level, exp
* gold (typically on Player)

Derived stats:

* attack: derived from equipped weapons
* defense: derived from equipped armour
* max_energy modifier: can be modified by equipped weapon bonuses

### Equipment Slots (v1)

* Weapon slots: 2 total
* Each weapon has a slot_cost (1 or 2)
* Two-handed weapons consume 2 slots
* Shields are weapons and consume 1 slot
* Body armour slot: 1 piece

---

## Story System

Story is represented as a graph of story nodes in JSON.

Story nodes can:

* display text
* offer choices
* apply effects (flags, rewards, party changes, battles)
* route to the next node

Story effects are processed by services, not presentation.

### Story ↔ Battle Control Flow

* `StoryService` processes node/choice effects. When an effect starts a battle it emits a `BattleRequested` event and records the pending next node inside `GameState`.
* The CLI listens for `BattleRequested`, pauses story advancement, and asks `BattleService` to run the encounter (player actions, enemy turns, Party Talk, etc.).
* When `BattleService` reports the battle is over, the CLI calls `StoryService.resume_after_battle()` so the queued node(s) continue processing using the same `GameState`.
* This handshake keeps the story graph deterministic and ensures allied party composition only changes when the corresponding story effect (e.g., `add_party_member`) fires.

---

## Knowledge and Party Talk

Knowledge is a deterministic mechanic:

* Enemy stats can be hidden by default (displayed as ???)
* Party members have predefined knowledge entries (data-driven)
* Party Talk queries a party member’s knowledge and returns structured results

Optional LLM integration:

* Receives structured facts only
* Rephrases in character
* Must not invent new information or alter what is revealed
