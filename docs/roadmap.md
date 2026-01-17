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

## DONE: Ticket 005 – Tutorial Battles + Party Talk Stub

* Story-driven battles now execute inside the CLI with deterministic turn order
* Basic Attack is the only combat action; Party Talk consumes a turn and prints structured knowledge text
* Enemy HP remains hidden (`???`) in the UI
* Emma’s goblin knowledge is available via Party Talk during the ambush battle

---

## DONE: Ticket-006 – Weapon-Tag Skills + Guard Stub

* Added skills.json and SkillRepository (Power Slash, Brace, Quick Stab, Skull Thump, Firebolt, Ember Wave).
* Skills are gated by equipped weapon/shield tags and consume MP; targeting supports single, multi (up to 3), and self.
* Shield skill “Brace” adds a one-hit guard buffer; staff users can now cast Firebolt/Ember Wave in battle.
* CLI exposes “Use Skill”, Party Talk remains text-only, and enemy HP is still hidden unless `TBG_DEBUG=1`.

---

## DONE: Ticket-007 – CLI Readability + Camp Interlude

* CLI presentation now uses consistent section headings/separators and hides story node IDs unless `TBG_DEBUG=1`.
* Party Talk pulls live enemy max HP plus deterministic fuzz (tag-gated) instead of static lore ranges.
* Added a post-ambush “camp” node that routes into the game menu so players can talk with Emma before continuing to `forest_aftermath`.

## DONE: Ticket-008 – Inventory & Equipment System

* Added shared party inventory with deterministic equip/unequip flows and per-member loadouts (two weapon slots + four armour slots).
* Weapons now enforce slot_cost (1H vs 2H) and armour specifies slot metadata; data definitions and validation updated accordingly.
* Game menu exposes an Inventory / Equipment option that lets players inspect party members and swap gear before resuming the story.

## DONE: Ticket-009 – Battle Rewards, Loot Tables, and Content Expansion

* Victories now grant deterministic gold, EXP splits, and loot rolls driven by tag-based drop tables; level-ups emit explicit events and Emma joins at level 3.
* Added `loot_tables.json`, goblin horn drops, optional potion rewards, a spear weapon line, new spear skills, and five additional enemies (wolf, boar, bandit scout, spore slime, goblin archer) for future encounters.
* Battle UI improvements: identical enemies gain numbered suffixes, debug HP is shown beside the `???` placeholder instead of event spam, and reward blocks render under a dedicated heading.

## DONE: Ticket-014 – Battle CLI Layout & Readability Pass

* Battle turns now render inside 60-character ASCII panels: `====` separators, boxed TURN headers, and a dual-column ALLIES vs ENEMIES snapshot that marks the active combatant and always shows ally MP.
* Player-only menus (Actions, Skills, Target, Party Talk) share the same boxed treatment, while invalid input retries no longer reprint the battlefield state.
* Each actor turn concludes with a single boxed RESULTS panel so multi-hit skills, failures, and AI actions stay grouped; debug HP visibility remains gated behind `TBG_DEBUG`.
* Added CLI-focused tests covering state panel cadence, results panel counts, menu gating, numbering consistency, and debug output.

---

## NEXT: Ticket-005.1 – UI Intel Reveal + Knowledge Tracking

Goal:

* Surface Party Talk knowledge inside the battle UI while keeping hidden stats for unrevealed foes.
* Begin wiring player-side knowledge tracking so intel persists beyond a single conversation.

Scope:

1. Extend battle UI to reveal stats (HP, speed hints, behaviors) after relevant Party Talk.
2. Persist player knowledge flags in `GameState` so repeated encounters remember previous intel.
3. Keep determinism—knowledge unlocks must be data-driven and testable.

Required tests:

* Knowledge reveal is deterministic and only triggers after matching Party Talk
* Persisted intel is loaded for repeated battles
* Hidden information stays concealed when no knowledge is available

Docs that define this slice:

* docs/v1_vertical_slice.md
* docs/knowledge_system.md

---

---

## LATER: Ticket-008 – Status Effects & Ability Expansion

Goal:

* Introduce simple status effects (burn/poison/guard break) tied to skills.
* Expand AI targeting hooks beyond random selection.
* Unit tests covering status application, expiration, and deterministic processing order.

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