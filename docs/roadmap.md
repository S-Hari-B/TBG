# Roadmap (V1)

This roadmap is organised around deliverable vertical slices.
Each slice should be playable, deterministic, and tested.

Status legend:

* DONE: implemented and tested
* NEXT: the next slice to implement
* LATER: planned after NEXT

---

## DONE: Tickets 1–3 (Foundation + Runtime Core)

* Project scaffold, repo structure, pytest setup
* Data layer repositories and loaders
* Runtime entities + factories wiring definitions to domain objects

---

## NEXT: Slice A – Tutorial Vertical Slice (Story + Party + Multi-Enemy Battle)

Goal:

* A player can start a new game, choose a class, progress through the intro story, fight battles, recruit Emma, and complete the forest ambush sequence.

Scope:

1. Class selection flow

* Present class options on New Game
* Apply starting stats, gear, items from classes.json

2. Story navigation (basic)

* Load story nodes
* Display node text and choices
* Apply node effects
* Advance to next node

3. Battles triggered by story

* Story effect can start battle
* Battle supports party (1–2 members) versus multiple enemies

4. Rewards application

* Apply EXP and gold rewards from defeated enemies
* Minimal level-up behavior can be stubbed or implemented (decide during slice)

5. Party member recruitment

* Story effect adds Emma as a party member

6. Party Talk (stub, deterministic)

* Party Talk exists in battle menu
* Returns structured facts from deterministic knowledge entries
* No LLM required for v1

Required tests:

* Story node resolution and effect application is deterministic
* Battle start from story effect works
* Multi-enemy battle initiative is deterministic
* Party member add works
* Party Talk returns expected facts for known tags

Docs that define this slice:

* docs/v1_vertical_slice.md
* docs/knowledge_system.md

---

## LATER: Slice B – Weapon-Tag Abilities

Goal:

* Abilities filtered by equipped weapon tags
* Energy costs and targeting
* Unit tests for gating and energy consumption

---

## LATER: Slice C – Inventory and Items In/Out of Combat

Goal:

* Inventory view in CLI
* Use items in and out of battle
* Unit tests for consumption and effects

Note:

* If inventory is already implemented, this slice becomes “expand and polish” rather than “create”.

---

## LATER: Slice D – Knowledge Growth (Player Learning)

Goal:

* Player knowledge database that unlocks info as enemies are encountered/defeated
* Keeps Party Talk valuable but not mandatory
* Deterministic unlock rules (counts, flags, milestones)

---

## LATER: Loot and Rarity (V1.1)

Goal:

* Drop tables
* Rarity roll and stat modifiers
* Unique items defined explicitly

---

## FUTURE: LLM Party Talk

Goal:

* Natural language queries to party members
* LLM produces characterful responses from structured knowledge facts
* Optional and never alters deterministic gameplay