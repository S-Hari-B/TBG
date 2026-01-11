Title: Gameplay Rules

Core loop (v1)
Main Menu

New Game (enter seed or generate)

Load Game (resume from one of three managed slots)

Options (future)

Quit

Game Menu

- Continue story – resumes the pending story node that triggered the camp interlude. If no pending node exists (e.g. after exhausting the current slice) the option remains but prints a reminder to explore via Travel instead.
- Travel – opens the area map defined in `data/definitions/areas.json`. The screen shows the current location’s name/description, lists every connected destination using the JSON `"label"` fields, and lets the player pick a destination. Travelling emits deterministic events (`Traveled from …`, `Arrived at …`) and renders a fresh “Location” block with the new area description. Areas can optionally declare `entry_story_node_id`; those nodes fire exactly once per save file when the player first enters that area and can show short flavour beats before returning to camp.
- Location Debug (DEBUG) – only in debug builds (`TBG_DEBUG=1`). Prints ids, tags, and entry-story flags for the current area plus the full `visited_locations`/`location_entry_seen` maps. Does not mutate state.
- Inventory / Equipment – opens the shared inventory where you can inspect party members, equip/unequip weapons and armour, and view remaining supplies. Accessible during camp interludes and future out-of-combat scenes.
- Party Talk – appears whenever at least one companion has joined. Surfaces deterministic banter lines.
- Save Game – only available from camp interludes. Writes the current runtime state (story position, party, inventory, equipment, flags, RNG state, and the new location trackers) to a chosen slot under `data/saves/slot_{1-3}.json`.
- Quit to main menu

## Manual Save/Load

* Saving is always player initiated and only surfaces inside the Camp Menu interlude that fires after `enter_game_menu` story effects. The CLI lists three numbered slots; picking one serializes the full `GameState` plus RNG state. Success prints `Saved to Slot X.` and the player remains in camp. Errors are reported and the menu remains open.
* Loading is only exposed on the Main Menu before entering or resuming play. Selecting `Load Game` shows the same three slots with summaries (player name, node id, last-saved timestamp). Empty slots are marked `Empty`; corrupt slots display `Corrupt data`. Attempting to load an empty or corrupt slot keeps the player in the Main Menu.
* Save files live under `data/saves/slot_1.json` through `slot_3.json`. The format is versioned (`"save_version": 1`). Any mismatch or missing fields results in `Load failed: <reason>` and the CLI returns to the Main Menu without altering state.
* Saves include the RNG internal state, so any random draws performed after loading match what would have happened had the player never quit. Story flow resumes exactly where the camp interlude paused: if you saved mid-camp you load back into the Camp Menu before continuing; otherwise the story picks up at the stored node and pending narration.
* Save files are portable and JSON-readable so players (and tests) can inspect them, but only validated ids defined in `data/definitions` are accepted during load. If definitions change incompatibly, the load is refused with `Save incompatible with current definitions`.

### Debug-mode UI helpers

Setting `TBG_DEBUG=1` adds a small status line to Camp and Travel menus (`DEBUG: <context> seed=… node=… location=… mode=…`), exposes the Location Debug menu entry described above, and augments the Save/Load slot picker with the stored seed + current location id so testers can verify persistence quickly. Combat still hides HP in normal play; debug mode continues to show explicit HP readings next to the `???` placeholder for enemies.

Story flow
The player navigates story nodes. Nodes display dialogue and provide choices. Nodes can trigger battles, rewards, party changes, or flag updates.

### Chapter 00 Tutorial beats

1. `intro_decree` – the King’s summons arrives and sets `flag_decree_received`.
2. `intro_departure` – the player commits to the road (`flag_left_village`).
3. `class_select` → `forest_intro` → `forest_scream` – establishes the crowded path to the capital before the Emma rescue.
4. `emma_encounter` → `emma_join` – first battle, Emma joins, and `flag_met_emma` flips on.
5. `forest_ambush` → `post_ambush_menu` – second battle followed by the first big camp interlude.
6. `forest_aftermath` – awards a small gold stipend and nudges players to Travel before resuming the main story.
7. Optional Travel to `forest_deeper` triggers `forest_deeper_entry` → `forest_deeper_path` → `forest_deeper_tracks`, culminating in either a wolf den or bandit ambush fight and the `forest_deeper_clearing` camp (`flag_cleared_forest_path`).
8. `demo_slice_complete` – reminds players they can keep replaying battles or exploring the deep-forest camp before the next chapter unlocks.

These steps, plus the deterministic Travel system, give Chapter 00 enough structure to test future quest tracking without introducing new mechanics yet.

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

Economy

gold exists in v1

gold is stored on Player

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
* Consumes the acting character’s turn.
* Prints deterministic intel lines from `knowledge.json`. Enemy HP stays hidden (`???`) in normal play; when `TBG_DEBUG=1` is set the actual HP is displayed alongside the enemy list rather than inside the combat log.

Item (later, ability to use items)

Flee (A chance to flee battle. If success, no rewards gained but retreats back to previous state before battle started. If failed will result in player and all party member turns skipped and enemy gets to complete their turn)

Identical enemies in the same encounter are suffixed deterministically (“Goblin Grunt (1)”, “Goblin Grunt (2)”, …) so the CLI, events, and target prompts always stay in sync.

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