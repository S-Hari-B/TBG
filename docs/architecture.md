Title: Architecture and Module Responsibilities

High-level structure
The codebase is split into layers with strict responsibilities:

presentation (CLI only)

Renders text to the user

Reads and validates user input

Calls services to perform actions

Never computes combat outcomes or edits domain objects directly

services (orchestration)

Runs “use cases” like start game, start battle, apply action, advance story

Loads definitions via repositories

Constructs domain objects and calls domain logic

Owns GameState (overall run state)

Returns structured results and events for presentation to render

domain (game rules)

Pure game rules and state transitions

Entities (actors, party members, enemies)

Combat rules, actions, effects

No printing, no file I/O, no input(), no global randomness

data (definitions and loading)

JSON loaders and repositories

Validates and returns definitions

No combat rules, no printing

core (shared utilities)

RNG wrapper and seed handling

Result types and errors

Small helpers only

ai (optional seam)

Interface for party talk generation

Stub implementation in v1

Later: local LLM + RAG implementation behind the same interface

Determinism and RNG policy

The game uses exactly one RNG instance, created from the game seed at New Game.

Domain logic never calls Python’s random module directly.

Any random event must use the injected RNG, and should emit an event describing the roll where relevant (ex: initiative tie-break roll).

Event-driven output
Domain logic returns Events, not printed strings.
Presentation renders those events into text.

Example: a weapon attack produces events such as:

TurnStarted(actor_id)

AttackDeclared(attacker_id, target_id, move_id)

DamageDealt(attacker_id, target_id, amount)

ActorDefeated(actor_id)

Party and equipment architecture
Party

Party is a collection with max size 4.

Party members can be added or removed via story effects (data-driven).

Base stats vs derived stats
Actors store base stats and equipment references.
Combat uses derived stats computed from equipment.

Base stats stored on Actor:

max_hp, hp

max_energy, energy

speed

level, exp

gold (primarily on Player, but can be a field on Player specifically)

Derived stats computed from equipped gear:

attack (from equipped weapon)

defense (from equipped armour)

Equipment slots (v1)

weapon slot (one weapon)

body armour slot (one armour piece)

Later slots (future): head, hands, legs, accessory.

Story system
Story is represented as a graph of story nodes in JSON.
Story nodes can:

display text

offer choices

apply effects (set flag, give item, start battle, add/remove party member)

route to the next node