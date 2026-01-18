# V1 Vertical Slice – Chapter 00 Tutorial

This document defines the first playable vertical slice of TBG v1: Chapter 00.

## Purpose

Introduce core mechanics, story flow, combat, party formation, companion choice, and basic quest concepts (flags only) in a controlled, replayable, deterministic tutorial chapter.

## Overview

- **Entry point**: New Game → Beach Arrival → Inn Orientation → Class Selection
- **Location**: Threshold Inn (Floor Zero)
- **Party size progression**: 1 → 2 (player chooses Emma OR Niale)
- **Enemy types**: Training scavengers (goblins serve as placeholders)
- **Core mechanics introduced**:
  - Equipment-driven power
  - Turn-based combat
  - Party formation & companion choice
  - Hidden enemy information
  - Party Talk (knowledge-based)
  - Proto-quest hooks (flags only, no journal)
  - Level-up progression
  - Checkpoint/retry system

## Class Selection

Class selection determines starting equipment and items only. Classes do not gate progression, skills, or long-term growth. All starting gear is Common quality.

### Warrior
- **Weapons**: One-handed sword (1 slot), Shield (1 slot)
- **Armour**: Heavy body armour
- **Role**: High defense, steady damage

### Rogue
- **Weapons**: Dagger (1 slot), Dagger (1 slot)
- **Inventory**: Shortbow (2-slot weapon)
- **Armour**: Medium body armour
- **Role**: High speed, flexible engagement

### Mage
- **Weapon**: Fire staff (2 slots)
- **Armour**: Light body armour
- **Starting abilities**: Single-target fire spell, Multi-target fire spell
- **Role**: High MP, ability-focused damage

### Commoner (Hard Mode)
- **Weapon**: Club (1 slot)
- **Armour**: Light body armour
- **Role**: Low stats, challenge run

## Story Flow (Chapter 00)

Ordered sequence:

1. **`arrival_beach_wake`** → Player wakes on beach, sets `flag_ch00_arrived`
2. **`arrival_beach_rescue`** → NPCs escort player to inn
3. **`inn_arrival`** → Introduction to Threshold Inn and Cerel
4. **`inn_orientation_cerel`** → Floors concept, safe zones, progression explained
5. **`inn_orientation_dana`** → Veteran insights, party trade-offs
6. **`class_overview`** → Class explanation before selection
7. **`class_select`** → Player chooses class, sets class flags
8. **`class_confirm`** → Acknowledgment of class choice
9. **`trial_setup`** → Cerel prepares solo trial
10. **`battle_trial_1v1`** → Battle vs 1 scavenger (player only), checkpointed
11. **`trial_victory_reflect`** → Level 2 achieved, MP/HP reset mechanics explained, sets `flag_trial_completed`
12. **`party_intro`** → Emma (Mage) and Niale (Rogue) introduced
13. **`companion_choice`** → Player chooses party configuration:
    - **Go solo** (no companions)
    - **Emma only** (Mage)
    - **Niale only** (Rogue)
    - **Both Emma and Niale** (full party)
14. **Solo path**: If player chooses solo, skips to `solo_path_skip_party_battle` → `solo_knowledge_intro` (narrative knowledge teaching without party battle)
15. **Party paths**: If player chooses any companion(s), proceeds to `companion_emma_join` / `companion_niale_join` / `companion_both_join`
16. **`battle_party_setup`** → Cerel prepares party battle (skipped on solo path)
16. **`battle_party_pack`** → Battle vs 3 scavengers (player + companion), checkpointed
17. **`party_after_battle`** → Victory acknowledgment, sets `flag_party_battle_completed`
18. **`knowledge_intro_party_talk`** → Party Talk mechanic introduced, sets `flag_knowledge_intro_seen`
19. **`protoquest_offer`** → Dana mentions optional ruins loot, sets `flag_protoquest_offered`
20. **Player Choice**:
    - **Accept** → `protoquest_accept` → sets `flag_protoquest_accepted`, opens ruins via Travel
    - **Decline** → `protoquest_decline` → skip to Floor One gate
21. **`floor1_open_handoff`** → Cerel's farewell, Floor One gate opens
22. **`ch00_complete`** → End of Chapter 00

### Optional Proto-Quest Branch

If player accepted proto-quest:

- Travel to **Shoreline Ruins**
- **`protoquest_ruins_entry`** → Entry node (auto-triggered on first visit)
- **`protoquest_battle`** → Battle vs scavenger
- **`protoquest_complete`** → Loot reward (10 gold), sets `flag_protoquest_completed`
- Return to inn, proceed to Floor One gate

## Companion Choice

At the `companion_choice` node, the player selects their party configuration:

1. **Go solo** (no companions) – Higher individual rewards, no Party Talk, narrative-only knowledge intro, party battle is skipped
2. **Emma only** (Mage, Level 3) – High MP, area damage (Firebolt, Fireburst)
3. **Niale only** (Rogue, Level 3) – High speed, mobility, single-target damage
4. **Both Emma and Niale** – Full party (3 members), 3-way EXP split, maximum tactical flexibility

The choice affects:
- Party composition for all subsequent battles
- EXP distribution (solo keeps 100%, party splits evenly)
- Access to Party Talk (solo players cannot use Party Talk)
- Party battle participation (solo skips the multi-enemy training fight)

Flags set based on choice:
- `flag_companion_none` (solo)
- `flag_companion_emma` (Emma only)
- `flag_companion_niale` (Niale only)
- `flag_companion_both` (both companions)

The non-chosen companion(s) remain "at the bar" for potential future recruitment.

## Areas (Floor Zero)

- **threshold_inn**: Safe hub, starting location
- **shoreline_ruins**: Optional proto-quest location (gated behind accepting quest)
- **floor_one_gate**: Transition point to future Floor One content

Legacy areas (village_outskirts, village, forest_deeper) preserved for save compatibility but not part of Chapter 00 flow.

## Flags Set in Chapter 00

- `flag_ch00_arrived`
- `flag_class_selected_warrior` / `_rogue` / `_mage` / `_commoner`
- `flag_trial_completed`
- `flag_companion_none` (solo path)
- `flag_companion_emma` (Emma only path)
- `flag_companion_niale` (Niale only path)
- `flag_companion_both` (both companions path)
- `flag_party_battle_completed` (set even if battle is skipped on solo path)
- `flag_knowledge_intro_seen`
- `flag_protoquest_offered`
- `flag_protoquest_accepted` (if accepted)
- `flag_protoquest_completed` (if completed)

## Combat Notes

- **Trial Battle**: Solo, 1v1, introduces basic attack and skills
- **Party Battle**: 1v3, introduces multi-actor turns, party coordination, Party Talk
- Both battles grant EXP; trial battle guarantees Level 2
- After every battle, MP resets to full (HP does not)
- Level-up: HP and MP snap to max immediately
- Checkpoints: Both battles set checkpoints; defeat rewinds to checkpoint with full HP/MP restore

## Design Goals Achieved

- **Diegetic systems**: NPCs acknowledge levels, classes, floors
- **Gradual teaching**: Solo combat → Party combat → Knowledge → Optional objectives
- **Meaningful choice**: Companion selection affects party composition
- **Quest scaffolding**: Proto-quest uses flags only, no journal required yet
- **Deterministic**: All outcomes repeatable with same seed

## Next Steps (Out of Scope for Chapter 00)

- Full quest journal UI
- Floor One exploration and content
- Boss encounters and floor progression gates
- Additional companions and party dynamics
