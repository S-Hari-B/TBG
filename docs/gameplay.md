Title: Gameplay Rules

Core loop (v1)
Main Menu

New Game (enter seed or generate)

Load Game (resume from one of three managed slots)

Options (future)

Quit

Game Menu

The game menu appears after `enter_game_menu` story effects. Non-town areas show the Camp Menu; town areas (`town` tag) show the Town Menu.

- Continue / Continue story – resumes the pending story node that triggered the interlude. If no pending node exists (e.g. after exhausting the current slice) the option remains but prints a reminder to explore via Travel instead.
- Travel – opens the area map defined in `data/definitions/locations.json`. The screen shows the current location’s name/description, lists every connected destination using the JSON `"label"` fields, and lets the player pick a destination. Travelling emits deterministic events (`Traveled from …`, `Arrived at …`) and renders a fresh “Location” block with the new area description. Locations can optionally declare `entry_story_node_id`; those nodes fire exactly once per save file when the player first enters that location and can show short flavour beats before returning to camp. When a required battle checkpoint is active, any connection flagged as `progresses_story: true` is temporarily locked with the message “You can’t push onward yet…” until the battle is cleared, but backtracking routes remain available.
- Converse (Town Menu only) – lists NPCs defined in the current hub’s `npcs_present` block and routes into their conversation entry story node.
- Quests (Town Menu only) – shows active objectives and available turn-ins; selecting a turn-in routes into its story node so narrative remains authoritative.
- Shops (Town Menu only) – opens the deterministic shop flow (item, weapon, and armour vendors) with buy/sell actions.
- Location Debug (DEBUG) – only in debug builds (`TBG_DEBUG=1`). Opens a debug submenu with quest, conversation, and definition integrity snapshots. Does not mutate state.
- Inventory / Equipment – opens the shared inventory where you can inspect party members, equip/unequip weapons and armour, and view remaining supplies. Accessible during camp interludes and future out-of-combat scenes.
- Party Talk – appears whenever at least one companion has joined. Surfaces deterministic banter lines.
- Save Game – available from interludes to persist the current runtime state to a slot under `data/saves/slot_{1-3}.json`.
- Quit to main menu

### Shops

* Town shops are deterministic: each shop has a fixed stock pool and a stock size (default 10). The current stock page is selected by `location_visits[location_id] % num_pages`, where `num_pages` is derived from the stock pool length.
* Stock is finite per visit; buying consumes remaining quantities. Reopening the shop does not refill. Leaving and returning increments the visit count, rotating the stock page and resetting quantities for the new visit.
* Buy/Sell inputs accept comma-separated indices (e.g. `1,3,5`). Duplicates are ignored, and each selection buys/sells exactly one item.
* Buy price is the item’s `value` from the relevant definition file (`items.json`, `weapons.json`, `armour.json`). Sell price is `floor(value * 0.5)`.

## Manual Save/Load

* Saving is always player initiated and only surfaces inside the Camp Menu interlude that fires after `enter_game_menu` story effects. The CLI lists three numbered slots; picking one serializes the full `GameState` plus RNG state. Success prints `Saved to Slot X.` and the player remains in camp. Errors are reported and the menu remains open.
* Loading is only exposed on the Main Menu before entering or resuming play. Selecting `Load Game` shows the same three slots with summaries (player name, node id, last-saved timestamp). Empty slots are marked `Empty`; corrupt slots display `Corrupt data`. Attempting to load an empty or corrupt slot keeps the player in the Main Menu.
* Save files live under `data/saves/slot_1.json` through `slot_3.json`. The format is versioned (`"save_version": 1`). Any mismatch or missing fields results in `Load failed: <reason>` and the CLI returns to the Main Menu without altering state.
* Saves include the RNG internal state, so any random draws performed after loading match what would have happened had the player never quit. Story flow resumes exactly where the camp interlude paused: if you saved mid-camp you load back into the Camp Menu before continuing; otherwise the story picks up at the stored node and pending narration.
* Save files are portable and JSON-readable so players (and tests) can inspect them, but only validated ids defined in `data/definitions` are accepted during load. If definitions change incompatibly, the load is refused with `Save incompatible with current definitions`.

### Recovery & Defeat Rules

* After every victorious battle the entire party’s MP is restored to full before any follow-up story or camp logic occurs. (HP remains unchanged unless specified elsewhere.)
* Whenever a player-controlled character levels up (including multiple levels in one reward step) their HP and MP snap to their current max values immediately after the level-up calculation, guaranteeing they’re ready for the next encounter.
* If the hero (player-controlled combatant) is reduced to 0 HP at any point in battle, the encounter ends instantly in defeat even if allies remain standing—no extra turns are played out after the hero falls.
* When the party is defeated, no one dies permanently: `flag_last_battle_defeat` is set to `true` and the CLI drops back into Camp Menu with the message “You barely make it back to camp…”. Story battles rewind to the last checkpointed node (the moment that triggered the battle) so selecting “Continue story” replays the failed encounter rather than skipping ahead. Open-area battles keep the player in the same location with HP/MP set to a minimum of 1. Checkpoints are tagged by thread (`main_story` today), so future quest checkpoints can coexist without fighting over Camp Continue. Defeat now costs half of current gold (rounded down) regardless of battle type.

### Debug-mode UI helpers

Setting `TBG_DEBUG=1` adds a small status line to Camp and Travel menus (`DEBUG: <context> seed=… node=… location=… mode=…`), exposes the Location Debug submenu described above (quest + conversation snapshots), and augments the Save/Load slot picker with the stored seed + current location id so testers can verify persistence quickly. Combat still hides HP in normal play; debug mode continues to show explicit HP readings next to the `???` placeholder for enemies, including defense values in an ultra-compact format (e.g., `???[22/22|D2]`). Debug mode also prints the battle ID heading (`=== Battle battle_XXXX ===`) at the start of encounters for reproducibility testing and shows turn-order numbers in the battle state panel.
Shop screens include a `Give Gold (DEBUG)` option while debug mode is enabled, allowing testers to inject gold instantly for purchase checks.

### Battle damage previews

During battle, the UI provides damage previews to help players make informed decisions. The skill list now also shows each skill's description on a wrapped line under the entry for quick reference:

- **Debug mode (`TBG_DEBUG=1`)**: Always shows exact projected damage based on attacker/target stats (e.g., "Projected: 6").
- **Normal mode with knowledge**: If any party member has knowledge of the target enemy type (via the knowledge system), the UI shows the exact projected damage as in debug mode.
- **Normal mode without knowledge**: For unknown enemies, the UI shows only the skill's base power value (e.g., "Power: 4") to avoid leaking hidden enemy defense stats. For basic attacks without knowledge, no preview is shown.

Projected damage does not account for guard reduction, which is consumed on hit. Previews are purely informational and never affect battle outcomes or RNG consumption.

Story flow
The player navigates story nodes. Nodes display dialogue and provide choices. Nodes can trigger battles, rewards, party changes, or flag updates.

### Chapter 00 Tutorial beats

Chapter 00 is a LitRPG-framed tutorial introducing core systems through story beats:

1. **Beach Arrival** (`arrival_beach_wake`, `arrival_beach_rescue`) – Player wakes with fragmented memory, rescued by NPCs, sets `flag_ch00_arrived`.
2. **Inn Orientation** (`inn_arrival`, `inn_orientation_cerel`, `inn_orientation_dana`) – Cerel and Dana explain Floors, progression, and party trade-offs.
3. **Class Overview** (`class_overview`) – Cerel explains class permanence before selection.
4. **Class Selection** (`class_select`) – Player chooses class (Warrior/Rogue/Mage/Commoner), sets class-specific flags.
5. **Solo Trial** (`trial_setup`, `battle_trial_1v1`) – 1v1 tutorial battle grants enough EXP to reach Level 2.
6. **Level-Up Reflection** (`trial_victory_reflect`) – Cerel and Dana explain progression curves, MP/HP reset mechanics, sets `flag_trial_completed`.
7. **Companion Choice** (`party_intro`, `companion_choice`) – Player chooses:
   - **Go solo** (no companions, skips party battle, narrative knowledge intro only)
   - **Emma only** (Mage, Level 3)
   - **Niale only** (Rogue, Level 3)
   - **Both Emma and Niale** (full party from start, 3-way EXP split)
8. **Party Battle** (`battle_party_setup`, `battle_party_pack`, `party_after_battle`) – Multi-enemy encounter demonstrating party coordination (skipped if solo path chosen), sets `flag_party_battle_completed`.
9. **Knowledge Intro** (`knowledge_intro_party_talk` or `solo_knowledge_intro`) – Party Talk or solo knowledge advice explained, sets `flag_knowledge_intro_seen`.
10. **Proto-Quest Hook** (`protoquest_offer`) – Dana mentions optional shoreline ruins loot, player can accept or decline, sets `flag_protoquest_offered`.
11. **Floor One Handoff** (`floor1_open_handoff`) – Cerel's farewell, Floor One gate opens.
12. **Threshold Inn Hub** (`threshold_inn_hub`) – Dana offers an optional wolf-tooth quest; the gate is available.
13. **Floor One Threshold** (`floor1_gate_entry`) – entry story when crossing the gate.
14. **Open Plains** (`plains_entry`) – travel hub; stay on road (story) or go off-road (open farming).
15. **Side Quest 1: Wolf Teeth** – collect 3 wolf teeth from off-road wolves, then return to Dana to turn in for rewards.
16. **Goblin Cave Entrance** (`goblin_cave_entrance_intro`) – Cerel offers kill-count side quest; goblin camp and deeper path unlock.
17. **Side Quest 2: Kill Quest** – defeat 10 Goblin Grunts + 5 Half-Orcs in goblin camp / cave encounters, then return to Cerel to claim rewards.
18. **Goblin Camp** (`goblin_camp_hub`) – open farming area with repeatable fights.
19. **Deeper Cave Path** (`cave_path_entry`) – forced story battles with checkpoint rewind on defeat.
20. **Guardian Foreshadow** (`cave_guardian_foreshadow`) – sealed boss chamber is visible but locked.
21. **Floor One Ready** (`floor1_ready`) – player free to farm, quest, and prepare.

If proto-quest accepted, player can Travel to **Shoreline Ruins**, trigger `protoquest_ruins_entry` → `protoquest_battle` → `protoquest_complete` (10 gold reward, sets `flag_protoquest_completed`).

Legacy content (old Chapter 00 nodes referencing forest encounters) is preserved in `chapter_00_legacy_redirects.json` for save compatibility but redirects to chapter end cleanly.

Party

Max party size is 4.

Party members can be added or removed through story effects. Each recruit now carries a defined `starting_level` so Emma joins the slice at level 3 instead of restarting at level 1.

If party is full, adding a member must either fail with a message or require replacing someone (future decision; v1 can “fail with message”).

Stats and progression
Base stats (Actor):

hp/max_hp

energy/max_energy (energy is the MP equivalent)

speed

level

exp

### Attributes (base)

Attributes now deterministically feed into derived combat stats. They remain flat (no % scaling, no caps).

- STR: increases attack (ATK) by +1 per point.
- DEX: increases initiative/speed (INIT) by +1 per point.
- INT: increases max MP by +2 per point.
- VIT: increases max HP by +3 per point.
- BOND: summon-only stat reserved for future summon systems (no current combat effect).

Base vs final stats:

- **Base stats** are computed from class/level baselines plus equipment (attack/defense from equipped gear).
- **Final stats** are base stats plus attribute contributions.
- Current HP/MP are always clamped to the final maxima after recalculation; there is no “base current HP/MP”.

Scaling policy (implemented + future contract):

- Each point matters; scaling is linear and deterministic.
- Derived combat stats already incorporate STR/DEX/INT/VIT contributions.
- Equipment requirements will use attributes in future tickets.
- Summon systems will use BOND in future tickets.

BOND currently has no effect on combat outcomes and is stored/displayed only.

### Enemy stat scaling (deterministic)

Enemy combat stats scale deterministically by battle level, derived from location context:

- If `locations.json` provides `area_level`, that value is used.
- Otherwise, the floor’s `level` from `floors.json` is used.
- If neither is available, level defaults to 0.

Scaling (flat per level, no RNG):

- max HP: +10 per level
- ATK: +2 per level
- DEF: +1 per level
- INIT: unchanged

Floor Zero is level 0 and uses base enemy definitions with no scaling.

Economy

gold exists in v1

gold is stored on `GameState`

Equipment and derived stats

Each party member has two weapon slots and four armour slots (head, body, hands, boots). Weapons with a slot_cost of 2 occupy both weapon slots; equipping them replaces any currently equipped one-handed weapons. Armour is one piece per slot. Equipping and unequipping gear is driven through the shared inventory menu. Equipped weapons determine basic attack power and available skill tags (including the new spear polearms), while equipped armour pieces contribute to total defense.

Combat (v1)
Participants

Party (1 to 4 actors) versus enemies (later expand for unique enemies and bosses)

Action economy
On a turn, the active actor chooses exactly one action:

* Basic Attack
* Use Skill (if at least one skill matches the actor’s equipped weapon/shield tags and they have the MP to spend)
* Use Item
* Party Talk (consumes the turn; returns deterministic intel text; no stat reveal yet)
* Defend (optional, can be v1.1)

Initiative
Initiative order is computed each round:

Sort by speed descending

If speeds tie, resolve tie with a deterministic dice roll using the game RNG

Tie-break roll is a d20 by default

### Skills (starter set)

* Skills live in `data/definitions/skills.json` and are gated by `required_weapon_tags`. Warriors with `["sword", "shield"]` gain Power Slash + Brace; Staff casters gain Firebolt + Ember Wave.
* Target modes:
  * `single_enemy` – choose one living enemy.
  * `multi_enemy` – choose 1..`max_targets` living enemies (Slice A cap: 3 on Ember Wave).
  * `self` – applies to the acting combatant (Brace).
* Effects:
  * `damage`: `damage = max(1, attack + base_power - target.defense)` (before guard). MP cost paid once per use.
  * `guard`: applies `base_power` as a guard buffer; the next incoming hit is reduced by that amount, then the buffer expires.
* The CLI only lists “Use Skill” when at least one eligible skill exists for the actor.

### Party Talk in combat

* Available whenever at least one party member is present (Emma in Slice A).
* Consumes the acting character's turn.
* Prints deterministic intel lines from `knowledge.json`. Enemy HP stays hidden (`???`) in normal play; when `TBG_DEBUG=1` is set the actual HP is displayed alongside the enemy list rather than inside the combat log.

Item (later, ability to use items)
### Use Item (v1)

* The battle menu now exposes **Use Item** whenever the shared inventory holds at least one consumable.
* Selecting the action shows a deterministic list using `items.json` definitions (quantity and targeting are rendered so players know why something may be blocked).
* Targets always include Self plus any living party members. Consumables that specify `targeting: "enemy"` can be used on a single living foe; `targeting: "any"` remains blocked and prints a clear diagnostic instead of wasting the turn.
* Consumables always consume the player's turn and the inventory stack, even if all affected stats were already at their maximum. In those cases the battle log explicitly reports "had no effect" to keep the flow readable.
* Enemy debuff items are flat, deterministic modifiers. `Weakening Vial` applies `ATK -2` while `Armor Sunder Powder` applies `DEF -2`. Both last for the remainder of the current round and all of the next round, expiring automatically at the start of the following round, and they cannot stack. Reapplying while the debuff is active still consumes the item and prints "had no effect."
* Active debuffs are visible directly inside the enemy column as compact tags (e.g., `[ATK-2]`). When `TBG_DEBUG=1`, an additional boxed panel lists exact magnitudes and the round index when the penalty will wear off. Expiry events ("Goblin Grunt's ATK penalty wore off.") fire before the first action of the round in which the debuff ends, but are suppressed for enemies that are already downed.
* Every starting class now begins with one Weakening Vial and one Armor Sunder Powder so players can immediately test the debuff flow.


Flee (A chance to flee battle. If success, no rewards gained but retreats back to previous state before battle started. If failed will result in player and all party member turns skipped and enemy gets to complete their turn)

Identical enemies in the same encounter are suffixed deterministically (“Goblin Grunt (1)”, “Goblin Grunt (2)”, …) so the CLI, events, and target prompts always stay in sync.

### Battle CLI presentation

* Battles now render inside a fixed-width (60 character) ASCII layout. Each actor turn begins with a `====` separator and a boxed `TURN` header so long encounters are easy to scan.
* A boxed battlefield view shows ALLIES vs ENEMIES in two columns. The currently acting unit is marked with `>` and allies always list both HP and MP (even when downed). Enemy HP remains hidden as `???` in normal play, while `TBG_DEBUG=1` keeps the `??? [current/max]` suffix that already existed.
* The state panel prints once at battle start and once at the beginning of every player-controlled turn; invalid menu input and retries never trigger a full re-render.
* Player menus (Actions, Skills, Target selection, Party Talk) use boxed panels with numbered entries. Enemy/ally AI turns never show menus.
* Every actor turn finishes with exactly one boxed RESULTS panel summarising all resolved events for that turn (multi-hit skills print multiple bullet lines). Invalid actions such as insufficient MP are summarised inside the same panel before re-prompting the relevant menu.
* Target selection panels include deterministic damage previews. In debug (`TBG_DEBUG=1`), exact values show as `Projected: X`. In normal play, previews use a non-leaky baseline label (no numeric damage) unless future knowledge rules explicitly allow exact projections. Previews never use RNG and ignore guard reductions for now.
* Post-battle rewards render in boxed panels: `REWARDS` (gold + EXP), `LEVEL UPS` (only when level-up events occur), and `LOOT` (aggregated item counts).
* **Text wrapping**: Long lines in boxed panels (RESULTS, Party Talk knowledge entries, etc.) are word-wrapped at render time to fit within the 56-character inner width, with continuation lines indented for readability. This ensures full knowledge text displays correctly without breaking panel borders or truncating mid-word.

Winning and losing
Victory

All enemies defeated

Rewards are applied: exp, gold, deterministic loot rolls using the shared RNG.

### Battle Rewards

* Gold: Sum the `rewards_gold` fields for defeated enemies; the total is added to the shared party stash and surfaced in a “Battle Rewards” block.
* EXP: Sum `rewards_exp`, split evenly across the player plus every recruited party member. Any remainder goes to the player. Experience thresholds use `xp_to_next = 10 + (level - 1) * 5`, so the Hero reaches Level 2 immediately after clearing `goblin_pack_3`.
* Levels: Each character keeps independent `level` and `exp` values so Emma remains level 3 when she joins. Level-ups generate their own reward events.
* Loot: `loot_tables.json` defines tag-driven drops. Every defeated enemy is matched against all tables whose required tags are satisfied (and forbidden tags avoided). Each drop entry rolls a deterministic chance using the game RNG; successes roll quantities and the resulting items are deposited into the shared inventory. Goblins always award `goblin_horn`, while optional drops such as potions use <100% chances so tests can assert deterministic seeds.

Defeat

Defeat condition: The player character reaching 0 HP results in defeat, regardless of the status of other party members.

Party members may be defeated independently, but cannot prevent defeat once the player is defeated.

Show defeat flow and return to main menu or last checkpoint (v1 can return to main menu)