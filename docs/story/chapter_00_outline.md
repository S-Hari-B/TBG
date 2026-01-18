# Chapter 00 Tutorial Outline (LitRPG Reframe)

Purpose
Chapter 00 is a self-contained tutorial slice that introduces the core loop and “rules of the world” in a LitRPG framing: arrival, class choice, solo combat basics, party combat, proto-quest via flags, and opening Floor One exploration.

Design goals

Make systems feel diegetic (the world acknowledges levels, classes, floors).

Teach mechanics gradually through story beats, not dumps.

Use existing systems wherever possible (story nodes, flags, battles, camp menu, party talk).

Introduce quest and knowledge concepts via narrative + flags (no quest journal yet).

End with the player free to explore Floor One with a clear next objective (reach boss zone later).

Non-goals (for Chapter 00)

No full quest journal UI.

No fully implemented floor progression system beyond narrative framing.

No major class rebalance or new mechanics.

No new battle mechanics.

Knowledge system can remain “conceptual” unless already implemented.

Core beats and teaching intent

Beat A: Arrival (Beach)
Teaches: story flow, tone, mystery, “you are a new arrival”

Player wakes on a beach with fragmented memory.

A “system-like” sensation is hinted (no explicit UI popup needed).

NPCs find the player and escort them to an inn. This is just done as story text.

Beat B: Inn Orientation (Cerel + Dana)
Teaches: world rules, floors concept, safety hub concept

Cerel is an “integration” guide for arrivals.

Dana is a veteran who casually references floors, risk, parties, and knowledge.

Explain floors as bounded areas with towns and a “guardian/boss gate” to the next floor.

Beat C: Class Overview (pre-selection)
Teaches: class identity, permanence, role fantasy

Cerel explains that class choice is meaningful and difficult to change.

Player can ask for short in-world descriptions of each class.

After overview, class selection occurs (existing class select flow reused).

Beat D: Solo Trial Battle (1v1)
Teaches: basic attack, skills, targeting, items (conceptual)

Cerel sends the player to a controlled trial fight outside the inn. He will not join in the fight but will give information after it is done.

One weak monster (currently can remain goblin grunt or a renamed “trial” variant).

The fight should reward exactly enough EXP to level up to Level 2 (as current tuning does).

Beat E: Level Up Reflection
Teaches: progression loop, stats growing, pacing

Cerel/Dana acknowledges the level up.

Brief framing that leveling slows later and preparation matters. Explains how a level up will reset the players health and mana. Explains how after every battle mana will automattically reset.

Beat F: Party Introduction + Companion Choice
Teaches: party pros/cons, party roles, exp split as a tradeoff

Player is introduced to two potential companions:

Emma (Mage)

Niale (Rogue)

Player chooses one to join for now (choice matters, but the other may appear later).

Explain that party is safer and more flexible, but rewards may be shared.

Beat G: Party Battle (multi-enemy)
Teaches: multi-actor turns, AoE vs single-target, party talk unlocked

Small enemy pack fight designed to demonstrate companion behavior.

Immediately after fight (or during camp), the Party Talk option is highlighted in-story.

Beat H: Knowledge + Proto-Quest Hook (flags only)
Teaches: knowledge value, optional objectives, “quest-like” beats without quest UI

Companion mentions a valuable item rumor nearby (optional).

Player can choose:

pursue the optional objective

or continue toward the main route

Use flags to record: quest started, optional completed, etc.

Beat I: Floor One Opens (end of tutorial slice)
Teaches: freedom + direction

The player is told they’re now free to explore Floor One.

The next long-term goal is hinted: reach the guardian/boss area to unlock Floor Two (not required in Chapter 00).

Chapter ends cleanly, handing off to Chapter 01.

Node plan (proposed node IDs)

arrival_beach_wake
arrival_beach_rescue
inn_arrival
inn_orientation_cerel
inn_orientation_dana
class_overview
class_select (existing node or wrapper)
class_confirm
trial_setup
battle_trial_1v1 (start_battle)
trial_victory_reflect (post battle, level up acknowledgment)
party_intro
companion_choice
companion_emma_join
companion_niale_join
battle_party_pack (start_battle)
party_after_battle
knowledge_intro_party_talk
protoquest_offer
protoquest_accept
protoquest_decline
(optional branch) protoquest_area_entry
(optional branch) battle_optional_reward_encounter
(optional branch) protoquest_complete
floor1_open_handoff (camp/menu interlude)

Flags to use (v1 placeholders)

flag_ch00_arrived
flag_class_selected_warrior / rogue / mage / commoner (or one flag + stored class name if supported)
flag_trial_completed
flag_companion_emma / flag_companion_niale
flag_party_battle_completed
flag_knowledge_intro_seen
flag_protoquest_offered
flag_protoquest_accepted
flag_protoquest_completed

Quest placeholders (no system yet)
For proto-quest, we treat it as flags and optional story branches. Later quest system can map:
quest_id: ch00_proto_loot
stage: offered/accepted/completed
objective_text: “Investigate the rumor of a valuable drop in the nearby zone.”

Battle definitions to reuse (initially)

Trial 1v1: can use goblin_grunt or create a new enemy id like “shoreline_vermin” later.

Party pack: reuse goblin_pack_3 or a similar small pack.

Companion requirements

Emma remains Mage.

Add Niale (Rogue) as a second recruit option (must exist in party definitions and have a basic deterministic AI).

Acceptance criteria for Chapter 00 redesign (story-only)

The player experiences: arrival -> class selection -> solo battle -> level up -> companion choice -> party battle -> proto-quest hook -> floor opens.

No debug-only tags appear in normal play.

Existing systems (camp, save/load, travel) still function and remain gated as intended.
