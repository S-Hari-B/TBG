# Balance Changes 30h: Enemy Skills & Rampager Reclass

**Date:** 2026-01-25  
**Ticket:** 30h - Early enemy skills and deterministic enemy skill usage

## Overview

Introduced minimal enemy skill usage for early content, adding texture to combat while maintaining balance targets and determinism. Reclassified Goblin Rampager from boss-tier to elite-tier with a limited-use AoE skill.

## Hard Constraints Met

- ✅ **Determinism**: All enemy skill selection is deterministic. Multi-target selection uses aggro-based ordering with stable tiebreaks (no new RNG).
- ✅ **Layering**: All combat logic in `BattleService`, reusing existing `SkillDef` system. No CLI logic changes.
- ✅ **System Reuse**: Enemy skills use existing `SkillsRepository` and `use_skill` paths. No parallel framework.
- ✅ **Balance Preservation**: Changes are conservative, focused on adding variety without disrupting existing difficulty bands.
- ✅ **Testability**: Comprehensive tests for determinism, usage caps, and fallback behavior.

## System Changes

### Data Schema
- Added optional `enemy_skill_ids: [str]` to enemy definitions
- Allows enemies to explicitly list usable skills (bypasses weapon-tag gating)
- Validated in definition integrity tests with skill reference checking

### Battle State
- Added `enemy_skill_uses: Dict[str, Dict[str, int]]` to `BattleState`
- Tracks per-battle skill usage per enemy instance
- Resets automatically on new battle start

### Enemy AI Logic
- `run_enemy_turn` now attempts skills before falling back to basic attack
- Skill selection iterates `enemy_skill_ids` in order, picks first usable
- Usability checks: sufficient MP, valid targets, usage cap not exceeded
- Target selection:
  - `single_enemy`: reuses existing threat-based `_select_enemy_target` (preserves anti-dogpile)
  - `multi_enemy`: deterministic sort by (-aggro, instance_id), take top N
  - `self`: target self (already supported)

### Usage Caps
- Hardcoded cap for `skill_rampager_cleave`: 2 uses per battle
- Extensible system via `_get_skill_usage_cap` method
- Only increments on successful skill use (checks for `SkillUsedEvent` or `GuardAppliedEvent`)

## Enemy Skills Added

All enemy skills use `required_weapon_tags: []` and include an "enemy" tag to prevent allies from using them (allies filter out skills tagged "enemy" in `get_available_skills`).

### New Skills (skills.json)

1. **skill_rampager_cleave**
   - Name: "Rampager Cleave"
   - Target: `multi_enemy` (max 3)
   - MP Cost: 8
   - Base Power: 6
   - Tags: `["skill", "enemy", "elite", "physical", "aoe"]`
   - Usage: Elite AoE threat, 2 uses per battle

2. **skill_aimed_shot**
   - Name: "Aimed Shot"
   - Target: `single_enemy`
   - MP Cost: 3
   - Base Power: 4
   - Tags: `["skill", "enemy", "physical", "ranged"]`
   - Usage: Goblin Archer precision attack

3. **skill_hex_spark**
   - Name: "Hex Spark"
   - Target: `single_enemy`
   - MP Cost: 2
   - Base Power: 5
   - Tags: `["skill", "enemy", "magic", "dark"]`
   - Usage: Goblin Shaman magical attack

4. **skill_savage_bite**
   - Name: "Savage Bite"
   - Target: `single_enemy`
   - MP Cost: 0
   - Base Power: 3
   - Tags: `["skill", "enemy", "physical", "beast"]`
   - Usage: Wolf/beast signature move (no MP cost, always available)

5. **skill_vicious_stab**
   - Name: "Vicious Stab"
   - Target: `single_enemy`
   - MP Cost: 2
   - Base Power: 4
   - Tags: `["skill", "enemy", "physical"]`
   - Usage: Goblin Skirmisher aggressive strike

## Enemy Assignments

### Goblin Rampager (Reclass: Boss → Elite)
- **Before:** HP 140, MP 0, ATK 16, DEF 5
- **After:** HP 140, MP 20, ATK 16, DEF 5
- **Tags:** Added "elite" tag
- **Skills:** `["skill_rampager_cleave"]` (2 uses/battle)
- **Intent:** Scary AoE moment but not spammable, no longer boss-tier threat

### Goblin Archer
- **Before:** MP 0
- **After:** MP 4
- **Skills:** `["skill_aimed_shot"]`
- **Intent:** Precision ranged attack, 1 use per typical encounter

### Goblin Skirmisher
- **Before:** MP 0
- **After:** MP 3
- **Skills:** `["skill_vicious_stab"]`
- **Intent:** Aggressive single-target, adds variety to goblin fights

### Goblin Shaman
- **Already had MP 16**
- **Skills:** `["skill_hex_spark"]`
- **Intent:** Magical threat, 8 casts available (won't spam, prefers skill when available)

### Forest Wolf
- **MP:** Stays at 0
- **Skills:** `["skill_savage_bite"]`
- **Intent:** Always-available signature move (0 MP cost), still falls back to attack

## Balance Notes

### Power Budget
- Enemy skills have modest base_power values (3-6)
- Comparable to or slightly below basic attacks for most
- Rampager AoE is 6 power × 3 targets = 18 total, but limited to 2 uses

### MP Economics
- Small MP pools (3-4) limit trash to 1-2 skill uses per fight
- Shaman's 16 MP allows sustained casting but won't spam (AI picks first usable skill)
- Rampager 20 MP allows 2 AoE uses with buffer

### Encounter Impact
- **Trash encounters:** 1 skill use adds texture, doesn't dominate
- **Rampager fights:** 2 AoE moments create pressure, then reverts to normal attacks
- **Balance bands maintained:** No changes to base ATK/HP/DEF needed

### Determinism Verification
- All target selection uses existing threat logic or deterministic sorts
- Multi-target selection: `sort(key=lambda: (-aggro, instance_id))` ensures stability
- No new RNG consumption paths introduced

## Testing Coverage

### Definition Integrity
- `test_definition_integrity.py`: validates `enemy_skill_ids` field and skill references

### Enemy Skill Usage
- `test_enemy_uses_skill_when_available`: enemy with MP uses skill
- `test_enemy_falls_back_to_attack_without_mp`: 0 MP → basic attack
- `test_enemy_skill_selection_order`: picks first usable from list

### Usage Caps
- `test_rampager_aoe_usage_cap`: 2 uses max, then fallback
- `test_rampager_aoe_cap_resets_per_battle`: fresh battle resets counter

### Determinism
- `test_enemy_multi_target_selection_deterministic`: identical seeds → identical targets

## Files Modified

### Domain/Data
- `src/tbg/domain/defs/enemy_def.py`: added `enemy_skill_ids` field
- `src/tbg/data/repositories/enemies_repo.py`: parse `enemy_skill_ids`
- `data/definitions/enemies.json`: added skills to 5 enemies, reclassed rampager
- `data/definitions/skills.json`: added 5 new enemy skills

### Services
- `src/tbg/services/battle_service.py`:
  - `run_enemy_turn`: skill attempt before attack
  - `_try_enemy_skill`: skill selection logic
  - `_select_enemy_skill_targets`: deterministic multi-target
  - `_check_enemy_skill_usage_allowed`: usage cap checking
  - `_record_enemy_skill_use`: usage tracking
  - `_get_skill_usage_cap`: hardcoded cap for rampager cleave
  - `get_available_skills`: filter out "enemy" tagged skills from allies

### Battle Models
- `src/tbg/domain/battle_models.py`: added `enemy_skill_uses` to `BattleState`

### Tests
- `tests/test_definition_integrity.py`: updated enemy validation
- `tests/test_battle_service.py`: added 7 new enemy skill tests

### Documentation
- `docs/balance_changes_30h_summary.md`: this document

## Gameplay Impact

### Player Experience
- **Early encounters more varied:** Occasional enemy skills break monotony
- **Readable threat:** Skills are simple damage, no complex status effects
- **Rampager fights scarier:** AoE creates pressure, rewards positioning (figuratively)
- **No balance shock:** Changes are additive, existing strategies remain viable

### Future Extensibility
- System supports adding more skills to enemies easily
- Usage cap system can be extended to other skills if needed
- Deterministic multi-target can handle more complex targeting if required
- Foundation for later introducing enemy self-buffs or ally-target skills

## Balance Invariants Maintained

- ✅ Party-first design: enemies still reactive, not proactive
- ✅ Attrition matters: MP pools are small, skills run out
- ✅ DEF conservative: no changes to defense values
- ✅ Early-game appropriate: no stuns, DOT, or complex debuffs
- ✅ Determinism: all randomness routed through seeded RNG

## Next Steps (Not in 30h)

- Monitor MP consumption rates in early floors
- Consider adding enemy self-buffs (e.g., guard skills) in later tickets
- Potential future: enemy ally-target healing/buffing for late-game encounters
- Balance tuning: adjust base_power if skills prove too strong/weak in playtesting

## Conclusion

Ticket 30h successfully adds minimal enemy skill usage to early content while maintaining strict determinism and balance targets. Goblin Rampager is now an elite-tier threat with a memorable AoE moment, and trash encounters have occasional skill usage for texture without overwhelming complexity.
