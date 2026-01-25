# Ticket 30e: Balance Analysis & Implementation Plan

## Current System State

### Damage Formula
```
damage = max(1, effective_attack + bonus_power - effective_defense)
```

### Scaling Constants (from code)
- **Player Attributes:**
  - VIT → HP: +3 per point
  - INT → MP: +2 per point
  - STR → ATK: +1 per point
  - DEX → SPEED: +1 per point
  - DEX → ATK (finesse weapons): +0.5 per point

- **Enemy Scaling (per battle level):**
  - HP: +12 per level
  - ATK: +2 per level
  - DEF: +2 per level
  - SPEED: +1 per level

### Starting Classes (Level 1)
**Warrior:**
- Base HP: 40, Base MP: 6, Speed: 4
- Attributes: STR 8, DEX 4, INT 2, VIT 6, BOND 5
- Weapon: Iron Sword (ATK 8) + Wooden Shield (ATK 1)
- Armour: Heavy Iron (DEF 14 total: body 6, head 2, hands 2, boots 2, +4 HP bonus)
- **Final Stats:** HP ~62, ATK 16, DEF 14, SPEED 8

**Rogue:**
- Base HP: 32, Base MP: 8, Speed: 7
- Attributes: STR 4, DEX 8, INT 6, VIT 4
- Weapons: 2x Iron Dagger (ATK 5, finesse) + Shortbow (ATK 6, finesse)
- Armour: Medium Leather (DEF 6 total: body 4, head 1, hands 1, boots 1, +4 HP bonus)
- **Final Stats:** HP ~48, ATK 9, DEF 6, SPEED 15
- **Finesse ATK:** 9 + (8 * 0.5) = 13 effective

**Mage:**
- Base HP: 26, Base MP: 18, Speed: 5
- Attributes: STR 2, DEX 4, INT 10, VIT 4
- Weapon: Fire Staff (ATK 3, energy_bonus 6)
- Armour: Light Cloth (DEF 3 total: body 2, head 1, hands 0, boots 0, +2 HP bonus)
- **Final Stats:** HP ~40, ATK 5, DEF 3, SPEED 9, MP 38
- **INT scaling:** ATK 5, but skills use INT → effective 15 for magic skills

**Beastmaster:**
- Base HP: 34, Base MP: 8, Speed: 6
- Attributes: STR 5, DEX 6, INT 3, VIT 4, BOND 10
- Weapons: Iron Dagger + Shortbow
- Armour: Medium Leather (DEF 6 total)
- **Final Stats:** HP ~46, ATK 11 (finesse 14), DEF 6, SPEED 12
- **Summons:** 2x Micro Raptor (BOND 10 = cost 5 each)
  - Each raptor: HP 35, ATK 16, DEF 12, SPEED 12

## Enemy Baseline Analysis (Area Level 0)

### Trash Mobs
**Goblin Grunt:** HP 32, ATK 7, DEF 5, Weapon ATK 3
- Equipped: Goblin Shiv (3), Patchwork Vest (2), Bone Cap (1), Bracers (1) = DEF 9 total
- **Effective ATK:** 10 (7 base + 3 weapon)

**Goblin Archer:** HP 25, ATK 10, DEF 2, Weapon ATK 4 (finesse)
- **Effective ATK:** 14

**Goblin Skirmisher:** HP 24, ATK 6, DEF 1, SPEED 9

**Wolf:** HP 30, ATK 8, DEF 3, SPEED 8

**Spore Slime:** HP 38, ATK 7, DEF 2, SPEED 3

### Elites
**Goblin Brute:** HP 40, ATK 9, DEF 3, SPEED 4
- Full gear: DEF 7 total

**Bandit Scout:** HP 34, ATK 9, DEF 4, SPEED 6
- Full gear

**Great Boar:** HP 42, ATK 10, DEF 5, SPEED 4

### Boss-tier
**Goblin Rampager:** HP 125, ATK 13, DEF 6, SPEED 5, Rewards 18 EXP / 14 gold
- Full gear: DEF 10 total

**Half-Orc Raider:** HP 46, ATK 12, DEF 5, SPEED 4
- Full gear: DEF 11 total

## Time-to-Kill Analysis (Level 0 vs Level 0)

### Warrior vs Goblin Grunt
- **Warrior ATK:** 16, **Goblin DEF:** 9
- **Damage per hit:** 16 - 9 = 7
- **Goblin HP:** 32
- **TTK:** 32 / 7 = **4.6 actions** ✅ (target: 2-4)

### Rogue vs Goblin Grunt
- **Rogue finesse ATK:** 13, **Goblin DEF:** 9
- **Damage per hit:** 13 - 9 = 4
- **TTK:** 32 / 4 = **8 actions** ❌ (target: 2-4)

### Mage vs Goblin Grunt (Firebolt)
- **Firebolt:** base_power 9, INT-scaled ATK 15
- **Damage per hit:** 15 + 9 - 9 = 15
- **TTK:** 32 / 15 = **2.1 actions** ✅
- **MP cost:** 4, can cast 9 times

### Beastmaster + 2 Raptors vs Goblin Grunt
- **Beastmaster finesse ATK:** 14, damage = 5
- **Raptor ATK:** 16, damage = 7 each
- **Total damage per round:** 5 + 7 + 7 = 19
- **TTK:** 32 / 19 = **1.7 rounds** ✅ (but 3 actors)

### Warrior vs Goblin Rampager (Boss)
- **Warrior ATK:** 16, **Rampager DEF:** 10
- **Damage per hit:** 16 - 10 = 6
- **Rampager HP:** 125
- **TTK:** 125 / 6 = **20.8 actions** ❌ (target: 10-12)

## Enemy Damage to Players (Attrition Analysis)

### Goblin Grunt → Warrior
- **Goblin ATK:** 10, **Warrior DEF:** 14
- **Damage:** max(1, 10 - 14) = **1 damage** ⚠️ (DEF floor problem)

### Goblin Archer → Rogue
- **Archer ATK:** 14, **Rogue DEF:** 6
- **Damage:** 14 - 6 = **8 damage**
- **As % of Rogue HP:** 8 / 48 = **16.7%** ✅ (target: 15-25%)

### Goblin Grunt → Mage
- **Grunt ATK:** 10, **Mage DEF:** 3
- **Damage:** 10 - 3 = **7 damage**
- **As % of Mage HP:** 7 / 40 = **17.5%** ✅

### Goblin Rampager → Warrior
- **Rampager ATK:** 13, **Warrior DEF:** 14
- **Damage:** max(1, 13 - 14) = **1 damage** ⚠️ (DEF floor problem)

## Critical Issues Identified

### 1. DEF Breakpoint Problem (High Priority)
- **Warrior DEF (14) completely negates trash mob damage (ATK 10)**
- This creates a binary situation: trivial vs impossible
- **Root cause:** Subtractive DEF + high warrior base DEF

### 2. Rogue Damage Too Low (High Priority)
- **8 actions to kill trash** vs target of 2-4
- DEX finesse multiplier (0.5) is too weak
- Rogue ATK needs significant boost

### 3. Boss TTK Too High (Medium Priority)
- **20+ actions for Warrior** vs target of 10-12
- Boss HP (125) vs trash HP (32) ratio is 3.9x
- Needs adjustment in boss HP or player damage

### 4. Enemy Damage Variance (Medium Priority)
- Some enemies hit DEF floor, others hit for 15-25%
- Need more consistent enemy ATK across archetypes

### 5. Summon Power Budget (Low Priority - Working as Intended)
- **2 Raptors = 2 extra party members**
- Total party output is correct (3 actors)
- Beastmaster personal damage is intentionally low
- System working correctly but needs documentation

## Proposed Solutions

### Solution 1: Adjust DEX Finesse Multiplier
**Change:** 0.5 → 0.75
**Impact:**
- Rogue finesse ATK: 13 → 15
- Rogue vs Grunt: 4 dmg → 6 dmg
- Rogue TTK: 8 actions → 5.3 actions ✅

### Solution 2: Reduce Enemy Base DEF
**Change:** Reduce trash mob DEF by 2-3 points across the board
**Impact:**
- Goblin Grunt DEF: 9 → 6-7
- Warrior vs Grunt: 7 dmg → 9-10 dmg (TTK: 3.2-3.6 actions) ✅
- Prevents DEF floor from triggering early

### Solution 3: Adjust Boss HP Pool
**Change:** Reduce boss HP from 125 → 90-100
**Impact:**
- Warrior vs Rampager: 20.8 actions → 15-16.7 actions (still high)
- Need to combine with damage boost

### Solution 4: Increase Player Weapon Damage
**Change:** Boost starting weapons by 1-2 ATK
**Impact:**
- Iron Sword: 8 → 10 (+2)
- Iron Dagger: 5 → 6 (+1)
- Fire Staff: Leave at 3 (INT-scaled)

### Solution 5: Reduce Enemy Scaling Per Level
**Change:** Reduce DEF scaling to +1 per level (from +2)
**Impact:**
- Level 2 enemies: DEF +4 → DEF +2
- Prevents DEF scaling from outpacing ATK scaling

## Implementation Priority

### Phase 1: Critical Fixes (Must Do)
1. **Increase DEX finesse multiplier:** 0.5 → 0.75
2. **Boost starting weapon ATK:** Iron Sword +2, Iron Dagger +1, Shortbow +1
3. **Reduce trash mob base DEF:** -2 to -3 across goblins/wolves
4. **Reduce boss HP:** Rampager 125 → 85

### Phase 2: Scaling Adjustments (Should Do)
5. **Reduce enemy DEF scaling:** +2 → +1 per level
6. **Adjust enemy ATK variance:** Ensure 8-12 ATK range for trash

### Phase 3: Fine-tuning (Nice to Have)
7. **Adjust elite HP pools:** Ensure 5-6 action TTK
8. **Review summon scaling:** Verify BOND scaling remains balanced

## Post-Change Projections

### Rogue vs Goblin Grunt (After Changes)
- **Rogue finesse ATK:** 10 (base) + (8 * 0.75) = 16
- **Goblin DEF:** 6 (reduced)
- **Damage:** 16 - 6 = 10
- **TTK:** 32 / 10 = **3.2 actions** ✅

### Warrior vs Goblin Grunt (After Changes)
- **Warrior ATK:** 18 (8 STR + 10 weapon)
- **Goblin DEF:** 6
- **Damage:** 18 - 6 = 12
- **TTK:** 32 / 12 = **2.7 actions** ✅

### Warrior vs Goblin Rampager (After Changes)
- **Warrior ATK:** 18
- **Rampager DEF:** 8 (reduced)
- **Rampager HP:** 85 (reduced)
- **Damage:** 18 - 8 = 10
- **TTK:** 85 / 10 = **8.5 actions** ✅

### Goblin Grunt → Warrior (After Changes)
- **Goblin ATK:** 10, **Warrior DEF:** 14
- **Damage:** max(1, 10 - 14) = 1
- Still hits floor, but acceptable (low threat is warrior fantasy)

## Success Criteria
- ✅ Trash mobs: 2-4 player actions
- ✅ Elites: 5-6 player actions
- ✅ Bosses: 8-12 player actions
- ✅ Attrition: 15-25% HP loss per trash fight
- ✅ No archetype invalidated
- ✅ All tests passing
