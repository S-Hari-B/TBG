# Knowledge System (V1 Design)

This document defines how enemy and world knowledge works in TBG.

Knowledge is a **game mechanic**, not an AI feature.

---

## Core Principles

* Knowledge is deterministic and data-driven
* Facts are stored in `data/definitions/knowledge.json` and surfaced exactly as defined
* Party members have predefined knowledge entries
* The local LLM is presentation-only and optional
* Knowledge never alters combat outcomes directly

---

## Hidden Information

By default, enemy information is hidden from the player.

Hidden fields may include:

* HP
* Energy
* Speed
* Abilities
* Behavioral traits

Hidden values are displayed as `???` unless revealed.

A temporary debug mode may display HP for development purposes only.

---

## Knowledge Sources

Knowledge can come from:

* Party members
* Player experience (future feature)
* Story events (future feature)

Each party member has a **local knowledge database** defined in data.

Example:

* Emma knows:

  * Goblins (up to level 3)
  * Basic goblin behavior
  * Approximate stat ranges

---

## Party Talk

Party Talk is available:

* In the game menu
* During combat

Party Talk allows the player to query a party member for information.

### Query Resolution

When Party Talk is used:

1. Identify current enemies and their tags
2. Check the party member’s knowledge entries
3. Determine which facts are eligible to be revealed
4. Return structured knowledge results

If no matching knowledge exists, the party member reports uncertainty.

### V1 Battle Stub

* Battle Party Talk is available as a combat action in the CLI.
* The action consumes the acting character’s turn.
* The CLI prints deterministic text assembled from the structured knowledge entry (HP ranges, speed hints, behaviors).
* Enemy UI elements remain hidden (`???`) even after talking in v1—the text output is purely informational.
* Dev-only debug flag: set `TBG_DEBUG=1` to show raw enemy HP while testing; keep it unset for normal play.

---

## LLM Integration (Optional)

If enabled:

* The LLM receives structured knowledge output
* The LLM rephrases facts in character
* The LLM cannot invent or infer new information

If disabled:

* Structured knowledge is displayed directly

The underlying facts are identical in both cases. (Ticket-005 keeps the LLM path disabled; Party Talk prints the deterministic JSON text verbatim.)

---

## Future Expansion (Non-V1)

* Knowledge unlocking through repeated encounters
* Partial stat reveals before full information
* Enemy-specific tactics and warnings
* World lore knowledge affecting story choices
