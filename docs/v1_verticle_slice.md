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

Emma can reveal information about goblins via Party Talk

Next: forest_aftermath

Node: forest_aftermath

Dialogue and short banter

Rewards:

EXP

Gold

Slice ends here

Design Notes

Enemy stats are hidden by default

Information is revealed only through Party Talk

This slice establishes party members as strategic assets, not just combat units