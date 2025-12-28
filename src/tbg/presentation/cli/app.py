"""Console-driven UI loops for TBG."""
from __future__ import annotations

import os
import secrets
from typing import List, Literal, Sequence

from tbg.data.repositories import (
    ArmourRepository,
    ClassesRepository,
    EnemiesRepository,
    KnowledgeRepository,
    PartyMembersRepository,
    StoryRepository,
    SkillsRepository,
    WeaponsRepository,
)
from tbg.domain.battle_models import BattleCombatantView, BattleState, Combatant
from tbg.domain.defs import SkillDef
from tbg.domain.state import GameState
from tbg.services import (
    BattleRequestedEvent,
    ChoiceResult,
    ExpGainedEvent,
    GoldGainedEvent,
    PartyMemberJoinedEvent,
    PlayerClassSetEvent,
    StoryNodeView,
    StoryService,
)
from tbg.services.battle_service import (
    AttackResolvedEvent,
    BattleEvent,
    BattleResolvedEvent,
    BattleService,
    BattleStartedEvent,
    BattleView,
    CombatantDefeatedEvent,
    GuardAppliedEvent,
    PartyTalkEvent,
    SkillFailedEvent,
    SkillUsedEvent,
)

MenuAction = Literal["new_game", "quit"]
_MAX_RANDOM_SEED = 2**31 - 1


def main() -> None:
    """Start the interactive CLI session."""
    story_service = _build_story_service()
    battle_service = _build_battle_service()
    print("=== Text Based Game (To be renamed) ===")
    running = True
    while running:
        action = _main_menu_loop()
        if action == "quit":
            running = False
            continue
        game_state = _start_new_game(story_service)
        keep_playing = _run_story_loop(story_service, battle_service, game_state)
        if not keep_playing:
            running = False
    print("Goodbye!")


def _main_menu_loop() -> MenuAction:
    while True:
        print()
        print("Main Menu")
        print("1. New Game")
        print("2. Quit")
        choice = input("Select an option: ").strip()
        if choice == "1":
            return "new_game"
        if choice == "2":
            return "quit"
        print("Invalid selection. Please enter 1 or 2.")


def _build_story_service() -> StoryService:
    """Construct the StoryService with concrete repositories."""
    story_repo = StoryRepository()
    classes_repo = ClassesRepository()
    weapons_repo = WeaponsRepository()
    armour_repo = ArmourRepository()
    return StoryService(
        story_repo=story_repo,
        classes_repo=classes_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
    )


def _build_battle_service() -> BattleService:
    """Construct the BattleService with concrete repositories."""
    enemies_repo = EnemiesRepository()
    party_repo = PartyMembersRepository()
    knowledge_repo = KnowledgeRepository()
    weapons_repo = WeaponsRepository()
    armour_repo = ArmourRepository()
    skills_repo = SkillsRepository()
    return BattleService(
        enemies_repo=enemies_repo,
        party_members_repo=party_repo,
        knowledge_repo=knowledge_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        skills_repo=skills_repo,
    )


def _start_new_game(story_service: StoryService) -> GameState:
    seed = _prompt_seed()
    player_name = _prompt_player_name()
    state = story_service.start_new_game(seed=seed, player_name=player_name)
    print(f"Game started with seed: {seed}")
    return state


def _prompt_seed() -> int:
    while True:
        raw_value = input("Enter seed (blank for random): ").strip()
        if not raw_value:
            return secrets.randbelow(_MAX_RANDOM_SEED)
        try:
            return int(raw_value)
        except ValueError:
            print("Invalid seed. Please enter a valid integer.")


def _prompt_player_name() -> str:
    while True:
        name = input("Enter hero name (default Hero): ").strip()
        if not name:
            return "Hero"
        return name


def _run_story_loop(story_service: StoryService, battle_service: BattleService, state: GameState) -> bool:
    """Run the minimal story loop for the tutorial slice."""
    print("\nBeginning tutorial slice...\n")
    while True:
        node_view = story_service.get_current_node_view(state)
        _render_node_view(node_view)
        if not node_view.choices:
            print("End of demo slice. Returning to main menu.\n")
            return True
        choice_index = _prompt_choice(len(node_view.choices))
        result = story_service.choose(state, choice_index)
        if not _process_story_events(result, battle_service, story_service, state):
            return False


def _render_node_view(node_view: StoryNodeView) -> None:
    for idx, (node_id, text) in enumerate(node_view.segments):
        if idx > 0:
            print()
        print(f"[{node_id}]")
        print(text)
    if node_view.choices:
        print("Choices:")
        for idx, label in enumerate(node_view.choices, start=1):
            print(f"  {idx}. {label}")


def _prompt_choice(choice_count: int) -> int:
    while True:
        raw = input("Select an option: ").strip()
        try:
            index = int(raw) - 1
        except ValueError:
            print("Please enter a number.")
            continue
        if 0 <= index < choice_count:
            return index
        print(f"Please enter a value between 1 and {choice_count}.")


def _process_story_events(
    result: ChoiceResult, battle_service: BattleService, story_service: StoryService, state: GameState
) -> bool:
    return _handle_story_events(result.events, battle_service, story_service, state, print_header=True)


def _handle_story_events(
    events: List[object],
    battle_service: BattleService,
    story_service: StoryService,
    state: GameState,
    *,
    print_header: bool,
) -> bool:
    if not events:
        return True
    if print_header:
        print("\nEvents:")
    for event in events:
        if isinstance(event, PlayerClassSetEvent):
            print(f"- You assume the role of a {event.class_id}. (Player ID: {event.player_id})")
        elif isinstance(event, BattleRequestedEvent):
            print(f"- Battle initiated against '{event.enemy_id}'.")
            battle_state, start_events = battle_service.start_battle(event.enemy_id, state)
            _render_battle_events(start_events)
            if not _run_battle_loop(battle_service, battle_state, state):
                print("You fall in battle. Game Over.\n")
                return False
            post_events = story_service.resume_after_battle(state)
            if not _handle_story_events(post_events, battle_service, story_service, state, print_header=bool(post_events)):
                return False
        elif isinstance(event, PartyMemberJoinedEvent):
            print(f"- {event.member_id.title()} joins the party.")
        elif isinstance(event, GoldGainedEvent):
            print(f"- Gained {event.amount} gold (Total: {event.total_gold}).")
        elif isinstance(event, ExpGainedEvent):
            print(f"- Gained {event.amount} experience (Total: {event.total_exp}).")
        elif isinstance(event, SkillUsedEvent):
            print(
                f"- {event.attacker_name} uses {event.skill_name} on {event.target_name} "
                f"for {event.damage} damage (HP {event.target_hp})."
            )
        elif isinstance(event, GuardAppliedEvent):
            print(f"- {event.combatant_name} braces, reducing the next hit by {event.amount}.")
        elif isinstance(event, SkillFailedEvent):
            print(f"- {event.combatant_name} cannot use that skill ({event.reason}).")
        else:
            print(f"- {event}")
    if print_header:
        print()
    return True


def _run_battle_loop(battle_service: BattleService, battle_state: BattleState, state: GameState) -> bool:
    """Run the deterministic battle loop until victory or defeat."""
    while not battle_state.is_over:
        view = battle_service.get_battle_view(battle_state)
        _render_battle_view(view)
        actor = _find_combatant(battle_state, view.current_actor_id)
        if actor is None:
            break
        if actor.side == "allies":
            if actor.instance_id == state.player.id:
                available_skills = battle_service.get_available_skills(battle_state, actor.instance_id)
                action = _prompt_battle_action(
                    can_talk=bool(state.party_members), can_use_skill=bool(available_skills)
                )
                if action == "attack":
                    target = _prompt_battle_target(battle_state)
                    events = battle_service.basic_attack(battle_state, actor.instance_id, target.instance_id)
                elif action == "skill":
                    events = _handle_player_skill_choice(
                        battle_service, battle_state, actor.instance_id, available_skills
                    )
                    if any(isinstance(evt, SkillFailedEvent) for evt in events):
                        _render_battle_events(events)
                        continue
                else:
                    speaker_member_id = _prompt_party_member_choice(state)
                    speaker_combatant_id = f"party_{speaker_member_id}"
                    events = battle_service.party_talk(battle_state, speaker_combatant_id)
            else:
                events = battle_service.run_ally_ai_turn(battle_state, actor.instance_id, state.rng)
        else:
            events = battle_service.run_enemy_turn(battle_state, state.rng)
        _render_battle_events(events)
    return battle_state.victor == "allies"


def _render_battle_view(view: BattleView) -> None:
    print(f"\n=== Battle: {view.battle_id} ===")
    print("Allies:")
    for ally in view.allies:
        status = "DOWN" if not ally.is_alive else ally.hp_display
        marker = "*" if ally.instance_id == view.current_actor_id else " "
        print(f"{marker} {ally.name:<12} HP {status}")
    print("Enemies:")
    debug_enabled = bool(os.getenv("TBG_DEBUG"))
    for enemy in view.enemies:
        marker = "*" if enemy.instance_id == view.current_actor_id else " "
        status = _format_enemy_hp_display(enemy, debug_enabled=debug_enabled)
        print(f"{marker} {enemy.name:<12} HP {status}")


def _prompt_battle_action(*, can_talk: bool, can_use_skill: bool) -> str:
    options: List[tuple[str, str]] = [("attack", "Basic Attack")]
    if can_use_skill:
        options.append(("skill", "Use Skill"))
    if can_talk:
        options.append(("talk", "Party Talk"))
    while True:
        print("\nActions:")
        for idx, (_, label) in enumerate(options, start=1):
            print(f"{idx}. {label}")
        choice = input("Choose action: ").strip()
        try:
            index = int(choice) - 1
        except ValueError:
            print("Invalid selection.")
            continue
        if 0 <= index < len(options):
            return options[index][0]
        print("Invalid selection.")


def _handle_player_skill_choice(
    battle_service: BattleService,
    battle_state: BattleState,
    actor_id: str,
    skills: List[SkillDef],
) -> List[BattleEvent]:
    skill = _prompt_skill_choice(skills)
    target_ids = _prompt_skill_targets(skill, battle_state)
    return battle_service.use_skill(battle_state, actor_id, skill.id, target_ids)


def _prompt_skill_choice(skills: List[SkillDef]) -> SkillDef:
    while True:
        print("\nSkills:")
        for idx, skill in enumerate(skills, start=1):
            target_desc = {
                "single_enemy": "Single Enemy",
                "multi_enemy": f"Up to {skill.max_targets} Enemies",
                "self": "Self",
            }[skill.target_mode]
            print(f"{idx}. {skill.name} (MP {skill.mp_cost}, {target_desc}) - {skill.description}")
        choice = input("Select skill: ").strip()
        try:
            index = int(choice) - 1
        except ValueError:
            print("Invalid selection.")
            continue
        if 0 <= index < len(skills):
            return skills[index]
        print("Invalid selection.")


def _prompt_skill_targets(skill: SkillDef, battle_state: BattleState) -> List[str]:
    if skill.target_mode == "self":
        return []
    living_enemies = [enemy for enemy in battle_state.enemies if enemy.is_alive]
    if not living_enemies:
        raise ValueError("No valid targets.")
    if skill.target_mode == "single_enemy":
        target = _prompt_battle_target(battle_state)
        return [target.instance_id]
    return _prompt_multi_enemy_targets(battle_state, skill.max_targets)


def _prompt_multi_enemy_targets(battle_state: BattleState, max_targets: int) -> List[str]:
    living_enemies = [enemy for enemy in battle_state.enemies if enemy.is_alive]
    while True:
        print("\nSelect targets (comma-separated):")
        for idx, enemy in enumerate(living_enemies, start=1):
            print(f"{idx}. {enemy.display_name}")
        raw = input(f"Choose up to {max_targets} targets: ").strip()
        parts = [part.strip() for part in raw.split(",") if part.strip()]
        try:
            indices = [int(part) - 1 for part in parts]
        except ValueError:
            print("Please enter numbers separated by commas.")
            continue
        if not indices:
            print("Select at least one target.")
            continue
        if len(indices) > max_targets:
            print("Too many targets selected.")
            continue
        if any(index < 0 or index >= len(living_enemies) for index in indices):
            print("Invalid target selection.")
            continue
        if len(indices) != len(set(indices)):
            print("Duplicate targets are not allowed.")
            continue
        return [living_enemies[index].instance_id for index in indices]


def _prompt_battle_target(battle_state: BattleState, exclude_ids: Sequence[str] | None = None) -> Combatant:
    exclude_set = set(exclude_ids or [])
    living_enemies = [enemy for enemy in battle_state.enemies if enemy.is_alive and enemy.instance_id not in exclude_set]
    while True:
        print("\nChoose target:")
        for idx, enemy in enumerate(living_enemies, start=1):
            print(f"{idx}. {enemy.display_name}")
        raw = input("Target #: ").strip()
        try:
            index = int(raw) - 1
        except ValueError:
            print("Enter a number.")
            continue
        if 0 <= index < len(living_enemies):
            return living_enemies[index]
        print("Invalid target.")


def _prompt_party_member_choice(state: GameState) -> str:
    while True:
        print("\nChoose a party member to speak:")
        for idx, member_id in enumerate(state.party_members, start=1):
            print(f"{idx}. {member_id.title()}")
        raw = input("Speaker #: ").strip()
        try:
            index = int(raw) - 1
        except ValueError:
            print("Enter a number.")
            continue
        if 0 <= index < len(state.party_members):
            return state.party_members[index]
        print("Invalid choice.")


def _render_battle_events(events: List[BattleEvent]) -> None:
    for event in events:
        if isinstance(event, BattleStartedEvent):
            print(f"\nBattle started against {', '.join(event.enemy_names)}.")
        elif isinstance(event, AttackResolvedEvent):
            print(
                f"- {event.attacker_name} hits {event.target_name} for {event.damage} damage "
                f"(HP now {event.target_hp})."
            )
        elif isinstance(event, CombatantDefeatedEvent):
            print(f"- {event.combatant_name} is defeated.")
        elif isinstance(event, PartyTalkEvent):
            print(f"- {event.text}")
        elif isinstance(event, SkillUsedEvent):
            print(
                f"- {event.attacker_name} uses {event.skill_name} on {event.target_name} "
                f"for {event.damage} damage (HP now {event.target_hp})."
            )
        elif isinstance(event, GuardAppliedEvent):
            print(f"- {event.combatant_name} braces, reducing the next hit by {event.amount}.")
        elif isinstance(event, SkillFailedEvent):
            print(f"- {event.combatant_name} cannot use that skill ({event.reason}).")
        elif isinstance(event, BattleResolvedEvent):
            print(f"- Battle resolved. Victor: {event.victor.title()}")
        else:
            print(f"- {event}")


def _find_combatant(battle_state: BattleState, combatant_id: str | None) -> Combatant | None:
    if combatant_id is None:
        return None
    for combatant in battle_state.allies + battle_state.enemies:
        if combatant.instance_id == combatant_id:
            return combatant
    return None


def _format_enemy_hp_display(enemy: BattleCombatantView, *, debug_enabled: bool) -> str:
    if not enemy.is_alive:
        return "DOWN"
    if not debug_enabled:
        return enemy.hp_display
    return f"{enemy.hp_display} (DEBUG {enemy.current_hp}/{enemy.max_hp})"



