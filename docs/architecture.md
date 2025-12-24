# Architecture and Responsibilities (V1)

TBG is structured with strict layering to keep core rules deterministic, testable, and independent from the CLI.

Layers:

## presentation (CLI)

* Renders text to the user
* Reads and validates user input
* Calls services to perform actions
* Never computes combat outcomes or modifies domain objects directly

## services (orchestration)

* Runs use cases (start game, advance story, start battle, apply action)
* Loads definitions via repositories
* Constructs domain entities using factories
* Owns GameState (overall runtime state)
* Returns structured results and events for presentation to render

## domain (game rules)

* Pure game rules and state transitions
* Entities: actors, party members, enemies, inventory state
* Combat rules, actions, effects, initiative
* No printing, no file I/O, no input(), no global randomness

## data (definitions and loading)

* JSON loaders and repositories
* Validates and returns definitions
* No combat rules, no printing

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
