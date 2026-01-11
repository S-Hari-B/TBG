V1 Vertical Slice – Tutorial Campaign

This document defines the first playable vertical slice of TBG v1.
Its purpose is to introduce core mechanics, story flow, combat, party formation, and the knowledge system in a controlled, minimal scope.

The slice is intentionally small and designed to be replayable and deterministic.

Overview

Entry point: New Game → Class Selection

Location: Forest road outside the starting village

Party size progression: 1 → 2

Enemy types: Goblins

Core mechanics introduced:

Equipment-driven power

Turn-based combat

Party formation

Hidden enemy information

Party Talk (knowledge-based)

Class Selection (Game Start)

Class selection determines starting equipment and items only.
Classes do not gate progression, skills, or long-term growth.

All starting gear is Common quality.

Warrior

Weapon: One-handed sword (1 slot)

Weapon: Shield (1 slot)

Armour: Heavy body armour

Role: High defense, steady damage

Rogue

Weapon: Dagger (1 slot)

Weapon: Dagger (1 slot)

Inventory: Shortbow (2-slot weapon)

Armour: Medium body armour

Role: High speed, flexible engagement

Mage

Weapon: Fire staff (2 slots)

Armour: Light body armour

Starting abilities:

Single-target fire spell

Multi-target fire spell

Role: High energy, ability-focused damage

Commoner (Hard Mode)

Weapon: Club (1 slot)

Armour: Light body armour

Role: Low stats, challenge run

Story Flow

Ordered sequence (Slice A):

1. `intro_decree` – the royal summons arrives and sets `flag_decree_received`.
2. `intro_departure` – the hero commits to the road (`flag_left_village`).
3. `class_select`
4. `forest_intro`
5. `forest_scream`
6. `emma_encounter` → battle vs `goblin_grunt` (player only)
7. `emma_join` → Emma formally joins the party (`flag_met_emma`)
8. `forest_ambush` → battle vs `goblin_pack_3` (player + Emma)
9. `post_ambush_menu` → short rest/menu interlude (player can Party Talk before continuing)
10. `forest_aftermath` → awards a small gold stipend, re-enters camp, and nudges the player to Travel before advancing
11. Optional `forest_deeper_entry` → `forest_deeper_path` → `forest_deeper_tracks` → (wolf or bandit battle) → `forest_deeper_clearing` (`flag_cleared_forest_path`)
12. `demo_slice_complete` → final “End of slice” narration after the player leaves camp

Node: intro_decree

Purpose: establish the King’s request and the larger JRPG hook.

Effects:

* `set_flag`: `flag_decree_received`

Next: intro_departure

Node: intro_departure

Text: The player prepares to leave as other volunteers march toward the capital.

Effects:

* `set_flag`: `flag_left_village`

Next: class_select

Node: class_select

Player selects starting class

Effects:

Apply starting stats

Equip starting gear

Add starting items

Next: forest_intro

Node: forest_intro

Text: Player leaves the village and enters a forest path toward the capital

No combat

Next: forest_scream

Node: forest_scream

Text: A scream echoes from deeper in the forest

Choice:

Investigate → emma_encounter

Ignore → future alternate route (not implemented in v1)

Node: emma_encounter

Scene description:

Player finds a wounded adventurer surrounded by three goblin corpses

One goblin remains alive

Combat:

Party: Player

Enemy: 1 Goblin

Mechanics introduced:

Basic combat
Basic Attack and weapon-tag skills (Power Slash, Brace if tags match)

Enemy stats hidden (shown as ???)

Next: emma_join

Node: emma_join

Dialogue exchange between player and Emma

Emma explains she was overwhelmed, not defeated

Effects:

Add party member: Emma

Next: forest_ambush

Node: forest_ambush

Combat:

Party: Player + Emma

Enemies: 3 Goblins

Mechanics introduced:

Party-based combat

Initiative with multiple actors

Party Talk (knowledge reveal)
Party Talk consumes the active character's turn and prints deterministic knowledge text

Emma can reveal information about goblins via Party Talk
Staff-user skills (Firebolt single-target, Ember Wave up to 3) unlock when Emma has the MP to spend.
Victory rewards: defeating the goblin pack yields enough EXP for the Hero to reach Level 2, grants Emma her share (without changing her level 3 baseline), and always drops a `goblin_horn` plus a deterministic chance at bonus supplies.

Next: post_ambush_menu

Node: post_ambush_menu

Purpose: Provide a rest/checkpoint beat where the player can re-enter the camp/game menu, talk with party members, then resume the story.

Effects:

* `enter_game_menu` – halts story flow and drops into the camp menu
* Menu lets the player: Continue Story (resumes pending node), Inventory / Equipment (manage the shared party loadout), Party Talk (Emma has new deterministic flavour lines), Quit to Main Menu

Next: forest_aftermath

Node: forest_aftermath

Dialogue and short banter about the King's timetable and the restless forest.

Rewards:

* Gold (small stipend)

Effects:

* `enter_game_menu` – immediately returns the player to the Camp Menu with explicit instructions to try the Travel option (village ↔ deep forest) before proceeding.

Next: demo_slice_complete

Node: forest_deeper_entry / path / tracks (Travel-triggered optional sequence)

* Entry text warns about dangerous wildlife and bandit activity.
* `forest_deeper_tracks` presents a choice:
  * Follow the clawed tracks → `forest_deeper_follow` → battle vs `wolf`.
  * Avoid the tracks / stay on the road → `forest_deeper_road` → battle vs `bandit_scout`.
* Both paths converge on `forest_deeper_clearing`, which sets `flag_cleared_forest_path`, triggers another Camp Menu interlude, and foreshadows Chapter 01 on the King's highway.

Node: demo_slice_complete

Node: demo_slice_complete

Purpose: Provide the final “End of demo slice” narration once the player chooses Continue from camp.

Text reminds the player they have reached the current edge of content and that they can continue replaying encounters or travelling between `village_outskirts`, `village`, and `forest_deeper` for testing.

Design Notes

Enemy stats are hidden by default
Battles now run directly inside the CLI with deterministic turn order and offer Basic Attack, Use Skill (weapon-tag gated), and Party Talk actions.
Party Talk currently prints structured knowledge text directly (UI intel reveal remains future work and enemy HP stays `???`).
Information is revealed only through Party Talk
Additional enemies (wolves, bandits, slimes, goblin archers) plus the spear weapon line exist in the data to support future encounters even though Slice A focuses on goblins.

This slice establishes party members as strategic assets, not just combat units