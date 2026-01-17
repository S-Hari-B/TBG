# Battle Controller Architecture

**Status**: Implemented  
**Last Updated**: 2026-01-17

## Overview

The battle controller pattern separates state progression (game logic) from rendering and user input (presentation logic). This separation enables:

- GUI replacement without touching game rules
- Testable battle flow without mocking CLI
- Clear responsibility boundaries between layers

## Structure

```
services/controllers/
  └── battle_controller.py     # UI-agnostic battle orchestration

presentation/cli/
  └── app.py                    # Rendering + input only
```

## Controller Responsibilities

The `BattleController` is a thin wrapper around `BattleService` that:

- Exposes **structured state** (current actor, available actions, etc.)
- Applies **player actions** via `BattleAction` dataclass
- Executes **AI turns** deterministically
- Determines **when to render** the state panel

## What the Controller Does NOT Do

The controller is UI-agnostic. It never:

- Calls `print()` or `input()`
- Formats strings or boxed panels
- Knows about CLI layout widths or separators

## Presentation Layer Responsibilities

The CLI (`presentation/cli/app.py`) is now responsible ONLY for:

- **Rendering** panels, events, and menus
- **Prompting** for user input
- **Formatting** text for display

It does NOT:

- Advance battle state directly
- Contain game rules or AI logic
- Decide which actions are valid

## Key Interfaces

### BattleAction (Input to Controller)

```python
BattleAction(
    action_type="attack",     # "attack" | "skill" | "talk"
    target_id="enemy_1",      # Optional: target for attack/skill
    target_ids=["enemy_1"],   # Optional: multi-target for skills
    skill_id="power_strike",  # Optional: skill ID
    speaker_id="party_emma",  # Optional: speaker for talk
)
```

### Available Actions (Output from Controller)

```python
{
    "can_attack": bool,
    "can_use_skill": bool,
    "can_talk": bool,
    "available_skills": List[SkillDef],
}
```

### BattleView (Rendering State)

```python
BattleView(
    battle_id="battle_xyz",
    allies=[...],
    enemies=[...],
    current_actor_id="hero",
)
```

## Rendering Flow

The controller determines **when** to render the state panel via:

```python
controller.should_render_state_panel(battle_state, state, is_first_turn=bool)
```

Rules:

- **Always** render on the first turn of battle
- **Always** render at the start of each player-controlled turn
- **Never** render for AI ally or enemy turns (compact results only)

This ensures the state panel appears exactly once per decision point, not on every input retry.

## Example: Player Turn Flow

```python
# 1. Controller identifies player turn
if controller.is_player_controlled_turn(battle_state, state):
    # 2. Controller provides available actions
    actions = controller.get_available_actions(battle_state, state)

    # 3. CLI prompts user (presentation layer)
    action_type = _prompt_battle_action(
        can_talk=actions["can_talk"],
        can_use_skill=actions["can_use_skill"]
    )

    # 4. CLI gathers targets (presentation layer)
    target = _prompt_battle_target(battle_state)

    # 5. CLI constructs action and submits to controller
    action = BattleAction(action_type="attack", target_id=target.instance_id)
    events = controller.apply_player_action(battle_state, state, action)

    # 6. CLI formats and renders events (presentation layer)
    lines = _format_battle_event_lines(events)
    _render_results_panel(lines)
```

## Canonical Event Formatting

All battle event rendering uses a single formatter:

```python
_format_battle_event_lines(events: List[BattleEvent]) -> List[str]
```

This eliminates duplication between:

- `_render_battle_events` (start events, rewards)
- Turn result summaries (attack, skill, talk)

## Testing Strategy

### Controller Tests (`test_battle_controller.py`)

- Controller exposes structured state
- Controller identifies turn types
- Controller applies actions without printing
- Controller determines rendering timing

### CLI Tests (`test_cli_battle_ui.py`)

- State panel renders once per player turn
- Invalid input does NOT reprint state panel
- Enemy HP debug display behavior
- Box width formatting

## Future Work

When building a GUI (Tkinter, Pygame, etc.):

1. Import `BattleController` from `services`
2. Call controller methods to advance state
3. Subscribe to returned events for animations
4. Render using GUI widgets instead of `print()`

**No changes to `BattleService` or domain logic required.**

## Migration Summary

| Before | After |
|--------|-------|
| `_run_battle_loop` mixed rendering + state progression | `_run_battle_loop` delegates to controller, only renders |
| `_run_player_turn` called `BattleService` directly | `_run_player_turn` constructs `BattleAction`, submits to controller |
| Duplicate event formatting in `_summarize_battle_events` and `_render_battle_events` | Single canonical `_format_battle_event_lines` |
| State panel reprinted on invalid input retries | State panel tied to decision points, not input loops |

## Architectural Constraints

- **Determinism preserved**: Controller passes RNG through, no new randomness
- **Gameplay unchanged**: Controller is a thin orchestration layer, no new rules
- **CLI output unchanged**: Line-for-line identical (verified by tests)
- **No GUI implementation**: This refactor is preventative, not a feature
