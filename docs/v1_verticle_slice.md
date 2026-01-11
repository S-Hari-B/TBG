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

1. `class_select`
2. `forest_intro`
3. `forest_scream`
4. `emma_encounter` → battle vs `goblin_grunt` (player only)
5. `emma_join` → Emma formally joins the party
6. `forest_ambush` → battle vs `goblin_pack_3` (player + Emma)
7. `post_ambush_menu` → short rest/menu interlude (player can Party Talk before continuing)
8. `forest_aftermath` → auto returns to camp so players can test Travel around `village_outskirts`
9. `demo_slice_complete` → final “End of slice” narration after the player leaves camp

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

Dialogue and short banter

Rewards:

EXP

Gold

Effects:

* `enter_game_menu` – immediately returns the player to the Camp Menu with explicit instructions to try the new Travel option before proceeding.

Next: demo_slice_complete

Node: demo_slice_complete

Purpose: Provide the final “End of demo slice” narration once the player chooses Continue from camp.

Text reminds the player they have reached the current edge of content and that they can continue replaying encounters or travelling between `village_outskirts`, `village`, and `forest_deeper` for testing.

Design Notes

Enemy stats are hidden by default
Battles now run directly inside the CLI with deterministic turn order and offer Basic Attack, Use Skill (weapon-tag gated), and Party Talk actions.
Party Talk currently prints structured knowledge text directly (UI intel reveal remains future work and enemy HP stays `???`).
Information is revealed only through Party Talk
Additional enemies (wolves, boars, bandits, slimes, goblin archers) plus the spear weapon line exist in the data to support future encounters even though Slice A focuses on goblins.

This slice establishes party members as strategic assets, not just combat units