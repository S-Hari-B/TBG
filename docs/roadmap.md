Title: Roadmap

Phase 0: Foundation

Docs complete (overview, architecture, gameplay, data formats, standards, roadmap)

Repo skeleton, folder structure, pytest setup

Minimal CLI menu and New Game seed handling (no combat yet)

Phase 1: Data layer

JSON loaders and repository

Sample definitions for items, weapons, armour, abilities, enemies, classes, story nodes

Unit tests for repository loading and lookups

Phase 2: Inventory slice

Inventory service (add/remove/consume)

Items usable out of combat

Unit tests for inventory behavior

CLI inventory view

Phase 3: Combat slice v1

Battle start and battle loop (party vs 1 enemy)

Initiative system (speed, tie d20)

Basic attack derived from weapon

Victory/defeat flow

Unit tests for initiative and damage application

Phase 4: Story slice v1

Story graph navigation

Story effects (start battle, give items, flags)

Stub party talk provider wired into story screens

Phase 5: Weapon-tag abilities

Ability list filtered by equipped weapon tags

Energy costs

Unit tests for ability gating

Phase 6: Loot and rarity (v1.1)

Drop tables

Rarity roll and stat modifiers

Unique weapons as explicit definitions