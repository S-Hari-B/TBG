# Chapter 00 Tutorial Outline (LitRPG Reframe)

## Purpose

Chapter 00 is a self-contained tutorial slice that introduces the core loop and rules of the world in a LitRPG framing: arrival, class choice, solo combat basics, party combat, side quests via flags, open exploration, and staging the Floor One guardian.

This document **replaces and expands** the previous Chapter 00 outline. Older sections are consolidated into this single authoritative design reference.

---

## Design goals

- Make systems feel diegetic: the world openly acknowledges levels, classes, floors, death, and preparation.
- Teach mechanics gradually through story beats and play, not system dumps.
- Use existing systems wherever possible (story nodes, flags, battles, camp menu, party talk, travel).
- Introduce quests and knowledge conceptually via narrative + flags (no quest journal UI yet).
- End with the player free to explore Floor One content while clearly foreshadowing the boss.

## Non-goals (for Chapter 00)

- No full quest journal UI.
- No full boss system implementation yet.
- No major class rebalance or new combat mechanics.
- Knowledge system may remain conceptual if already implemented.

---

## Core Structure Overview

Chapter 00 covers **Floor Zero → early Floor One**, establishing four content pillars that will repeat on future floors:

1. **Main Story Path** – forced encounters and progression gates.
2. **Side Quests** – optional objectives using flags only.
3. **Open Farming Areas** – repeatable battles with no story impact.
4. **Hubs** – safe locations with NPCs, services, and future expansion hooks.

---

## Story Beats and Teaching Intent

### Beat A: Arrival (Beach)

**Location:** Shoreline

- Player wakes on a beach with fragmented memory.
- Subtle system sensations are hinted, not explained.
- NPCs rescue the player and escort them to a nearby settlement.

**Teaches:** Tone, mystery, LitRPG framing.

---

### Beat B: Threshold Inn Orientation

**Location:** Threshold Inn (Floor Zero hub)

**NPCs:** Dana, Cerel

- Floors explained as bounded zones with a guardian gate.
- Death is explained as costly but non-final.
- Parties are framed as strategic choices, not requirements.

**Teaches:** World rules, hub safety, progression framing.

---

### Beat C: Class Overview (Pre-selection)

- In-world descriptions of all starting classes.
- Strengths, weaknesses, and party synergies are hinted.
- Classes framed as starting archetypes.

After overview, class selection occurs.

---

### Beat D: Solo Trial Battle

**Type:** Forced story battle (1v1)

- Controlled encounter outside the inn.
- Teaches: basic attack, skills, MP usage, turn order.
- Rewards exactly enough EXP to reach Level 2.

---

### Beat E: Level-Up Reflection

- NPCs acknowledge the level-up.
- Explain HP/MP refill on level-up and post-battle MP recovery.
- Emphasize preparation and pacing.

---

### Beat F: Companion Introduction and Choice

Player is offered four options:

1. Go solo
2. Emma only (Mage)
3. Niale only (Rogue)
4. Emma + Niale

- EXP split and party pros/cons explained.
- Choice immediately affects upcoming flow.

---

### Beat G: Party Tutorial Battle (Conditional)

- Occurs only if at least one companion is selected.
- Multi-enemy encounter to demonstrate party AI and AoE.
- Party Talk is unlocked and highlighted.

If solo:

- This battle is skipped.
- Knowledge system is explained narratively instead.

---

### Beat H: Plains Unlocked – First Exploration

**Location:** Open Plains

- Travel system fully opens.
- Two options:
  - Stay on the road (story direction)
  - Go off-road (open farming area)

**Open Area Rules:**

- Infinite repeatable encounters.
- Defeat has no story impact.
- HP/MP set to minimum 1.
- Half gold lost.

---

### Beat I: Side Quest 1 – Item Collection

**Quest Giver:** Dana

- Collect 3 Wolf Teeth.
- Reward: Gold + small EXP.
- Teaches item drops and optional progression.

---

### Beat J: Story Direction – Goblin Cave

- Dana explains Floor One progression requires entering the Goblin Cave.
- Player encouraged to prepare first.

---

### Beat K: Goblin Cave Entrance Hub

**Location:** Cave Entrance

**NPC:** Cerel

- Introduces kill-based side quests.
- Explains enemy knowledge unlocking via kills.

---

### Beat L: Side Quest 2 – Kill Quest

**Quest Giver:** Cerel

- Defeat 10 Goblin Grunts and 5 Half-Orcs.
- Teaches kill counters and enemy variety.

---

### Beat M: Cave Interior – Split Paths

#### Option A: Goblin Camp (Open Area)

- Repeatable farming
- Stronger enemies
- No story impact

#### Option B: Deeper Cave (Story Path)

- 1–2 forced encounters
- Defeat rewinds to cave entrance checkpoint

---

### Beat N: Floor Guardian Foreshadowing

- Boss chamber visible but locked.
- Bosses framed as distinct encounters.
- Actual fight deferred to later chapter.

---

### Beat O: Chapter End – Floor One Ready

- Player free to farm, quest, or prepare.
- Clear long-term goal: defeat the Floor Guardian.

---

## Defeat Handling Rules

- **Open areas:**
  - HP/MP set to 1 (minimum)
  - Lose half gold
  - No story rollback

- **Story battles:**
  - Rewind to last story checkpoint
  - Lose half gold

---

## Acceptance Criteria (Design-Level)

- Player experiences arrival → class → solo battle → level-up → companion choice → exploration → side quests → cave progression.
- Open areas never advance story flags.
- Side quests are optional and flag-driven.
- Chapter ends cleanly with Floor One staged but unresolved.
