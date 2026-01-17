# Battle Flow Architecture - Before vs After

## Before: Mixed Responsibilities

```
presentation/cli/app.py
├── _run_battle_loop()
│   ├── Renders turn header
│   ├── Renders state panel
│   ├── Determines who's turn it is
│   ├── Calls BattleService directly
│   ├── Formats events (duplicated)
│   └── Renders results
│
└── _run_player_turn()
    ├── Re-renders state panel on retry
    ├── Prompts for action
    ├── Calls BattleService directly
    ├── Formats events (duplicated)
    └── Returns to loop
```

**Problems**:
- State progression mixed with rendering
- Duplicate event formatting
- State panel reprinted on invalid input
- Hard to test without CLI
- GUI would need to rewrite everything

---

## After: Clean Separation

```
services/controllers/battle_controller.py
└── BattleController (UI-agnostic)
    ├── get_battle_view() → structured state
    ├── is_player_controlled_turn() → bool
    ├── get_available_actions() → dict
    ├── apply_player_action(BattleAction) → events
    ├── run_ally_ai_turn() → events
    ├── run_enemy_turn() → events
    └── should_render_state_panel() → bool

presentation/cli/app.py
├── _format_battle_event_lines() [CANONICAL]
│   └── Single source of truth for event text
│
├── _run_battle_loop()
│   ├── Creates BattleController
│   ├── Asks controller: who's turn?
│   ├── Asks controller: should render state?
│   ├── Renders turn header (once)
│   ├── Renders state panel (decision points only)
│   ├── Delegates to controller for state progression
│   ├── Uses canonical formatter
│   └── Renders results
│
└── _run_player_turn()
    ├── Gets available actions from controller
    ├── Prompts user (presentation only)
    ├── Constructs BattleAction
    ├── Submits to controller
    ├── Uses canonical formatter
    └── Returns events (no reprinting)
```

**Benefits**:
- Clear separation: controller progresses, CLI renders
- One canonical event formatter
- State panel tied to decision points
- Controller testable without CLI
- GUI can reuse controller directly

---

## Data Flow

### Player Turn (Simplified)

```
[User Input]
     ↓
[CLI Prompts] → "attack" + target
     ↓
[BattleAction] → { type: "attack", target_id: "enemy_1" }
     ↓
[Controller] → apply_player_action()
     ↓
[BattleService] → basic_attack()
     ↓
[Events] → [AttackResolvedEvent, ...]
     ↓
[Canonical Formatter] → ["- Hero hits Goblin for 5 damage."]
     ↓
[CLI Renders] → prints to console
```

### Future GUI Flow

```
[GUI Button Click]
     ↓
[BattleAction] → { type: "attack", target_id: "enemy_1" }
     ↓
[Controller] → apply_player_action()
     ↓
[Events] → [AttackResolvedEvent, ...]
     ↓
[GUI Event Handler] → animates damage
     ↓
[GUI Updates] → redraws health bars
```

**No changes to services or domain required!**

---

## Testing Strategy

### Before
- Mock CLI input/output
- Test full integration path
- Hard to isolate logic

### After
- Test controller without CLI
- Test CLI rendering separately
- Test event formatting independently
- Clean unit test boundaries

---

## Migration Impact

| Aspect | Impact |
|--------|--------|
| Gameplay | ✅ None (100% identical) |
| CLI Output | ✅ None (line-for-line identical) |
| Determinism | ✅ None (same RNG usage) |
| Test Coverage | ✅ Improved (+7 tests) |
| Code Clarity | ✅ Improved (clear boundaries) |
| Future GUI | ✅ Enabled (controller ready) |
