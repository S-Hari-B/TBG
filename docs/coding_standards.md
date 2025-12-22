Title: Coding Standards and Agent Rules

General

Keep code simple, explicit, readable. No clever abstractions.

One ticket at a time. Only implement the requested scope.

No large refactors without explicit approval.

Add unit tests for any core logic introduced or changed.

Layer rules

presentation layer prints and reads input only. It must not contain game rules.

domain layer must not print, read input, or do file I/O.

data layer loads definitions only. It must not contain combat logic.

services orchestrate domain and data and return structured results and events.

Determinism

All randomness must use the single RNG wrapper created from the game seed.

Never use random.random() or random.randint() directly.

Any tie-break roll or important random choice should emit an event.

Data-driven rules

Items, weapons, armour, abilities, enemies, story nodes are loaded from JSON definitions.

Use string IDs to reference definitions.

Do not hardcode content in Python unless explicitly asked.

Testing

Prefer unit tests for domain logic: initiative ordering, damage rules, inventory consume, ability gating.

Tests must be deterministic by using fixed seeds and the RNG wrapper.