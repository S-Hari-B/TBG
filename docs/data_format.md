Title: Data Formats and Tag Rules

General rules

All IDs are unique strings, snake_case, lowercase. Example: “bronze_sword”.

Tags are lowercase, snake_case, no spaces. Example: “sword”, “healing_item”.

Definitions live in TBG - V1/data/definitions/*.json.

Repositories load definitions at startup.

Tag conventions (initial set)
Weapon type tags: sword, axe, club, dagger, staff, bow (expanded later)
Damage tags: slash, pierce, blunt, fire, ice, lightning (expanded later)
Item tags: consumable, healing, energy_restore (expanded later)
Monster tags: beast, undead, humanoid, dragon (expanded later)

Weapons (weapons.json)
Weapon fields (v1):

id: string

name: string

tags: list[string] (must include weapon type tag like “sword”)

base_attack: int

default_basic_attack_id: string (refers to an ability/move)

energy: int (The amount of energy that the weapon has, will be added with the entities base energy value)

value_gold: int

Example:
{
"id": "bronze_sword",
"name": "Bronze Sword",
"tags": ["sword", "slash"],
"base_attack": 6,
"default_basic_attack_id": "basic_slash",
"energy": 2,
"value_gold": 30
}

Armour (armour.json)
Armour fields (v1):

id: string

name: string

slot: string (v1: “body”)

base_defense: int

tags: list[string]

value_gold: int

Example:
{
"id": "cloth_tunic",
"name": "Cloth Tunic",
"slot": "body",
"base_defense": 2,
"tags": ["light_armour"],
"value_gold": 15
}

Items (items.json)
Item fields (v1):

id: string

name: string

tags: list[string]

item_type: string (“consumable” only in v1)

value_gold: int

effect: object describing what happens when used

Consumable effect types (v1):

heal_hp: restores hp

restore_energy: restores energy

Example:
{
"id": "potion_hp_small",
"name": "Small HP Potion",
"tags": ["consumable", "healing"],
"item_type": "consumable",
"value_gold": 10,
"effect": { "type": "heal_hp", "amount": 25 }
}

Abilities and Moves (abilities.json)
Abilities represent both basic attacks and special skills.

Ability fields (v1):

id: string

name: string

required_weapon_tags: list[string] (empty list means always usable)

energy_cost: int

target: string (v1: “single_enemy”, “self”)

effect: object

Effect types (v1):

deal_damage: uses attacker attack vs target defense with a simple formula

heal_hp: heal a target
Later: buffs, debuffs, status effects.

Example basic attack move:
{
"id": "basic_slash",
"name": "Slash",
"required_weapon_tags": ["sword"],
"energy_cost": 0,
"target": "single_enemy",
"effect": { "type": "deal_damage", "power": 1.0, "damage_tag": "slash" }
}

Enemies (enemies.json)
Enemy fields (v1):

id: string

name: string

level: int

base_stats: object

equipment: object with weapon_id and armour_id

rewards: exp, gold (drops can be later)

tags: list[string]

Base stats fields (v1):

max_hp

max_energy

speed

Example:
{
"id": "slime",
"name": "Slime",
"level": 1,
"base_stats": { "max_hp": 20, "max_energy": 0, "speed": 3 },
"equipment": { "weapon_id": "slime_pseudopod", "armour_id": "slime_skin" },
"rewards": { "exp": 5, "gold": 2 },
"tags": ["beast"]
}

Classes (classes.json)
Class fields (v1):

id: string

name: string

starting_stats: object

starting_equipment: object

starting_items: list of item_id with quantities

Example:
{
"id": "wanderer",
"name": "Wanderer",
"starting_stats": { "max_hp": 35, "max_energy": 10, "speed": 5 },
"starting_equipment": { "weapon_id": "bronze_sword", "armour_id": "cloth_tunic" },
"starting_items": [
{ "item_id": "potion_hp_small", "quantity": 2 },
{ "item_id": "potion_energy_small", "quantity": 1 }
]
}

Story nodes (story.json)
Story is a graph of nodes.

Node fields (v1):

id: string

text: string

speaker: optional string

choices: list of choices

effects: list of effects to apply when entering or choosing

next: optional string (default next node)

Choice fields:

label: string

next: string

conditions: optional list

effects: optional list

Effect types (v1):

set_flag {flag, value}

give_item {item_id, quantity}

start_battle {enemy_id}

add_party_member {member_id}

remove_party_member {member_id}

give_gold {amount}

Example node:
{
"id": "village_start",
"speaker": "Elder",
"text": "A slime has been seen near the road. Will you help us?",
"choices": [
{ "label": "Yes", "next": "slime_battle", "effects": [] },
{ "label": "No", "next": "village_start_refuse", "effects": [] }
]
}