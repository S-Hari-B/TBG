Title: Gameplay Rules

Core loop (v1)
Main Menu

New Game (enter seed or generate)

Load Game (future)

Options (future)

Quit

Game Menu

Continue story

Party status (future to include party talk)

Inventory

Save Game (future)

Quit to main menu

Story flow
The player navigates story nodes. Nodes display dialogue and provide choices. Nodes can trigger battles, rewards, party changes, or flag updates.

Party

Max party size is 4.

Party members can be added or removed through story effects.

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

Equipped weapon defines “basic attack” and attack power.

Equipped armour defines defense.

Combat (v1)
Participants

Party (1 to 4 actors) versus enemies (later expand for unique enemies and bosses)

Action economy
On a turn, the active actor chooses exactly one action:

Basic Attack

Ability (weapon-tag gated, later)

Use Item

Defend (optional, can be v1.1)

Initiative
Initiative order is computed each round:

Sort by speed descending

If speeds tie, resolve tie with a deterministic dice roll using the game RNG

Tie-break roll is a d20 by default

Party talk (later expanded for ability to discuss battle with party members)

Item (later, ability to use items)

Flee (A chance to flee battle. If success, no rewards gained but retreats back to previous state before battle started. If failed will result in player and all party member turns skipped and enemy gets to complete their turn)

Winning and losing
Victory

All enemies defeated

Rewards are applied: exp, gold, drops (drops can be v1.1 if we want)

Defeat

Defeat condition: The player character reaching 0 HP results in defeat, regardless of the status of other party members.

Party members may be defeated independently, but cannot prevent defeat once the player is defeated.

Show defeat flow and return to main menu or last checkpoint (v1 can return to main menu)