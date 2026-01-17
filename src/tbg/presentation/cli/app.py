"""Console-driven UI loops for TBG."""
from __future__ import annotations

import os
import secrets
from typing import List, Literal, Sequence

from tbg.data.repositories import (
    ArmourRepository,
    AreasRepository,
    ClassesRepository,
    EnemiesRepository,
    ItemsRepository,
    KnowledgeRepository,
    LootTablesRepository,
    PartyMembersRepository,
    StoryRepository,
    SkillsRepository,
    WeaponsRepository,
)
from tbg.domain.battle_models import BattleCombatantView, BattleState, Combatant
from tbg.domain.inventory import ARMOUR_SLOTS
from tbg.domain.defs import SkillDef
from tbg.domain.state import GameState
from tbg.services import (
    AreaService,
    BattleRequestedEvent,
    ChoiceResult,
    ExpGainedEvent,
    GameMenuEnteredEvent,
    GoldGainedEvent,
    LocationEnteredEvent,
    LocationView,
    PartyMemberJoinedEvent,
    PlayerClassSetEvent,
    SaveLoadError,
    SaveService,
    StoryNodeView,
    StoryService,
    TravelBlockedError,
    TravelPerformedEvent,
)
from tbg.services.area_service import TRAVEL_BLOCKED_MESSAGE
from tbg.services.battle_service import (
    AttackResolvedEvent,
    BattleEvent,
    BattleExpRewardEvent,
    BattleLevelUpEvent,
    BattleResolvedEvent,
    BattleRewardsHeaderEvent,
    BattleService,
    BattleStartedEvent,
    BattleView,
    CombatantDefeatedEvent,
    GuardAppliedEvent,
    LootAcquiredEvent,
    PartyTalkEvent,
    SkillFailedEvent,
    SkillUsedEvent,
    BattleGoldRewardEvent,
)
from tbg.services.inventory_service import (
    ArmourSlotView,
    EquipFailedEvent,
    InventoryEvent,
    InventoryService,
    InventorySummary,
    ItemEquippedEvent,
    ItemUnequippedEvent,
    PartyMemberView,
    WeaponSlotView,
)
from .render import (
    render_choices,
    render_events_header,
    render_heading,
    render_menu,
    render_story,
)
from .save_slots import SaveSlotStore, SlotMetadata

MenuAction = Literal["new_game", "load_game", "quit"]
_MAX_RANDOM_SEED = 2**31 - 1
_MENU_TALK_LINES = {
    "emma": [
        "We handled that ambush together. Let's keep that rhythm.",
        "If more goblins show up, we strike first this time.",
    ]
}
_DEFEAT_CAMP_MESSAGE = "You barely make it back to camp, bruised but alive."


def _debug_enabled() -> bool:
    return bool(os.getenv("TBG_DEBUG"))


def _print_debug_status(state: GameState, *, context: str) -> None:
    if not _debug_enabled():
        return
    node_id = state.current_node_id or "unknown"
    location_id = state.current_location_id or "unplaced"
    checkpoint_thread = state.story_checkpoint_thread_id or "none"
    checkpoint_node = state.story_checkpoint_node_id or "none"
    checkpoint_loc = state.story_checkpoint_location_id or "none"
    print(
        f"DEBUG: {context} seed={state.seed} node={node_id} location={location_id} mode={state.mode} "
        f"checkpoint_thread={checkpoint_thread} checkpoint_node={checkpoint_node} checkpoint_loc={checkpoint_loc}"
    )


def _main_menu_options() -> List[tuple[str, MenuAction]]:
    return [
        ("New Game", "new_game"),
        ("Load Game", "load_game"),
        ("Quit", "quit"),
    ]


def _build_camp_menu_entries(state: GameState) -> List[tuple[str, str]]:
    entries: List[tuple[str, str]] = [
        ("Continue story", "continue"),
        ("Travel", "travel"),
    ]
    if _debug_enabled():
        entries.append(("Location Debug (DEBUG)", "location_debug"))
    entries.append(("Inventory / Equipment", "inventory"))
    if state.party_members:
        entries.append(("Party Talk", "talk"))
    entries.append(("Save Game", "save"))
    entries.append(("Quit to Main Menu", "quit"))
    return entries


def _format_slot_label(meta: SlotMetadata) -> str:
    if not meta.exists:
        return f"Slot {meta.slot}: Empty"
    if meta.is_corrupt:
        return f"Slot {meta.slot}: Corrupt data"
    metadata = meta.metadata or {}
    player_name = metadata.get("player_name", "Unknown")
    node_id = metadata.get("current_node_id") or "Unknown"
    mode = metadata.get("mode")
    saved_at = metadata.get("saved_at")
    summary = f"Slot {meta.slot}: {player_name} – {node_id}"
    if isinstance(mode, str):
        summary += f" [{mode}]"
    if isinstance(saved_at, str):
        summary += f" ({saved_at})"
    if _debug_enabled():
        seed = metadata.get("seed", "?")
        location = metadata.get("current_location_id") or "Unknown"
        summary += f" | seed={seed} location={location}"
    return summary


def _warp_to_checkpoint_location(area_service: AreaService, state: GameState) -> bool:
    checkpoint_location_id = state.story_checkpoint_location_id
    if not checkpoint_location_id:
        return False
    if state.current_location_id == checkpoint_location_id:
        return False
    previous_location = state.current_location_id or "unknown"
    area_service.force_set_location(state, checkpoint_location_id)
    if state.current_location_id != checkpoint_location_id:
        raise RuntimeError(
            f"Checkpoint warp failed: expected location '{checkpoint_location_id}' but found '{state.current_location_id}'."
        )
    pretty_name = checkpoint_location_id.replace("_", " ").title()
    print(f"- Returned to {pretty_name} (checkpoint rewind).")
    if _debug_enabled():
        print(
            f"DEBUG: checkpoint warp from={previous_location} to={checkpoint_location_id}"
        )
    return True


def main() -> None:
    """Start the interactive CLI session."""
    (
        story_service,
        battle_service,
        inventory_service,
        save_service,
        area_service,
    ) = _build_services()
    slot_store = SaveSlotStore()
    print("=== Text Based Game (To be renamed) ===")
    running = True
    while running:
        action = _main_menu_loop()
        if action == "quit":
            running = False
            continue
        if action == "load_game":
            game_state = _load_game_flow(save_service, slot_store)
            if game_state is None:
                continue
            from_load = True
        else:
            game_state = _start_new_game(story_service, area_service)
            from_load = False
        keep_playing = _run_story_loop(
            story_service,
            battle_service,
            inventory_service,
            game_state,
            save_service,
            slot_store,
            area_service,
            from_load=from_load,
        )
        if not keep_playing:
            running = False
    print("Goodbye!")


def _main_menu_loop() -> MenuAction:
    while True:
        print()
        print("Main Menu")
        options = _main_menu_options()
        for index, (label, _) in enumerate(options, start=1):
            print(f"{index}. {label}")
        choice = input("Select an option: ").strip()
        try:
            selection = int(choice) - 1
        except ValueError:
            print("Invalid selection. Please enter a number.")
            continue
        if 0 <= selection < len(options):
            return options[selection][1]
        print(f"Invalid selection. Please enter 1 to {len(options)}.")


def _build_services() -> tuple[StoryService, BattleService, InventoryService, SaveService, AreaService]:
    weapons_repo = WeaponsRepository()
    armour_repo = ArmourRepository()
    story_repo = StoryRepository()
    classes_repo = ClassesRepository(weapons_repo=weapons_repo, armour_repo=armour_repo)
    party_repo = PartyMembersRepository()
    inventory_service = InventoryService(
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        party_members_repo=party_repo,
    )
    story_service = StoryService(
        story_repo=story_repo,
        classes_repo=classes_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        party_members_repo=party_repo,
        inventory_service=inventory_service,
    )
    enemies_repo = EnemiesRepository()
    knowledge_repo = KnowledgeRepository()
    skills_repo = SkillsRepository()
    items_repo = ItemsRepository()
    loot_repo = LootTablesRepository()
    battle_service = BattleService(
        enemies_repo=enemies_repo,
        party_members_repo=party_repo,
        knowledge_repo=knowledge_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        skills_repo=skills_repo,
        items_repo=items_repo,
        loot_tables_repo=loot_repo,
    )
    areas_repo = AreasRepository()
    area_service = AreaService(areas_repo=areas_repo)
    save_service = SaveService(
        story_repo=story_repo,
        classes_repo=classes_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        items_repo=items_repo,
        party_members_repo=party_repo,
        areas_repo=areas_repo,
    )
    return story_service, battle_service, inventory_service, save_service, area_service


def _start_new_game(story_service: StoryService, area_service: AreaService) -> GameState:
    seed = _prompt_seed()
    player_name = _prompt_player_name()
    state = story_service.start_new_game(seed=seed, player_name=player_name)
    area_service.initialize_state(state)
    print(f"Game started with seed: {seed}")
    return state


def _load_game_flow(save_service: SaveService, slot_store: SaveSlotStore) -> GameState | None:
    while True:
        selection = _prompt_slot_choice(slot_store, title="Load Game")
        if selection is None:
            return None
        if not selection.exists:
            print("Slot is empty.")
            continue
        if selection.is_corrupt:
            print("Slot data is corrupt. Overwrite it from the Camp Menu.")
            continue
        try:
            payload = slot_store.read_slot(selection.slot)
        except FileNotFoundError:
            print("Slot is empty.")
            continue
        except ValueError as exc:
            print(f"Load failed: {exc}")
            return None
        try:
            state = save_service.deserialize(payload)
        except SaveLoadError as exc:
            print(f"Load failed: {exc}")
            return None
        print(f"Loaded Slot {selection.slot}.")
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


def _run_story_loop(
    story_service: StoryService,
    battle_service: BattleService,
    inventory_service: InventoryService,
    state: GameState,
    save_service: SaveService,
    slot_store: SaveSlotStore,
    area_service: AreaService,
    *,
    from_load: bool,
) -> bool:
    """Run the minimal story loop for the tutorial slice."""
    if from_load:
        print("\nResuming saved game...\n")
        if state.mode == "camp_menu":
            follow_up = _run_post_battle_interlude(
                state.camp_message or "",
                story_service,
                inventory_service,
                state,
                save_service,
                slot_store,
                battle_service,
                area_service,
            )
            if follow_up is None:
                return False
            if not _handle_story_events(
                follow_up,
                battle_service,
                story_service,
                inventory_service,
                state,
                save_service,
                slot_store,
                area_service,
                print_header=bool(follow_up),
            ):
                return False
    else:
        print("\nBeginning tutorial slice...\n")
    while True:
        node_view = story_service.get_current_node_view(state)
        _render_node_view(node_view)
        if not node_view.choices:
            print("End of demo slice. Returning to main menu.\n")
            return True
        choice_index = _prompt_choice(len(node_view.choices))
        result = story_service.choose(state, choice_index)
        if not _process_story_events(
            result,
            battle_service,
            story_service,
            inventory_service,
            state,
            save_service,
            slot_store,
            area_service,
        ):
            return False


def _render_node_view(node_view: StoryNodeView) -> None:
    render_story(node_view.segments)
    render_choices(node_view.choices)


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
    result: ChoiceResult,
    battle_service: BattleService,
    story_service: StoryService,
    inventory_service: InventoryService,
    state: GameState,
    save_service: SaveService,
    slot_store: SaveSlotStore,
    area_service: AreaService,
) -> bool:
    return _handle_story_events(
        result.events,
        battle_service,
        story_service,
        inventory_service,
        state,
        save_service,
        slot_store,
        area_service,
        print_header=True,
    )


def _handle_story_events(
    events: List[object],
    battle_service: BattleService,
    story_service: StoryService,
    inventory_service: InventoryService,
    state: GameState,
    save_service: SaveService,
    slot_store: SaveSlotStore,
    area_service: AreaService,
    *,
    print_header: bool,
) -> bool:
    if not events:
        return True
    rendered_story_this_batch = False
    if print_header:
        render_events_header()
    for event in events:
        if isinstance(event, PlayerClassSetEvent):
            print(f"- You assume the role of a {event.class_id}. (Player ID: {event.player_id})")
        elif isinstance(event, BattleRequestedEvent):
            rendered_story_this_batch = _render_story_if_needed(
                story_service, state, rendered_story_this_batch
            )
            print(f"- Battle initiated against '{event.enemy_id}'.")
            state.mode = "battle"
            battle_state, start_events = battle_service.start_battle(event.enemy_id, state)
            _render_battle_events(start_events)
            if not _run_battle_loop(battle_service, battle_state, state):
                if not _handle_defeat_flow(
                    battle_service,
                    story_service,
                    inventory_service,
                    state,
                    save_service,
                    slot_store,
                    area_service,
                ):
                    return False
                continue
            story_service.clear_checkpoint(state)
            state.mode = "story"
            post_events = story_service.resume_pending_flow(state)
            if not _handle_story_events(
                post_events,
                battle_service,
                story_service,
                inventory_service,
                state,
                save_service,
                slot_store,
                area_service,
                print_header=bool(post_events),
            ):
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
        elif isinstance(event, GameMenuEnteredEvent):
            rendered_story_this_batch = _render_story_if_needed(
                story_service, state, rendered_story_this_batch
            )
            follow_up = _run_post_battle_interlude(
                event.message,
                story_service,
                inventory_service,
                state,
                save_service,
                slot_store,
                battle_service,
                area_service,
            )
            if follow_up is None:
                return False
            if not _handle_story_events(
                follow_up,
                battle_service,
                story_service,
                inventory_service,
                state,
                save_service,
                slot_store,
                area_service,
                print_header=bool(follow_up),
            ):
                return False
        else:
            print(f"- {event}")
    if print_header:
        print()
    return True


def _run_post_battle_interlude(
    message: str,
    story_service: StoryService,
    inventory_service: InventoryService,
    state: GameState,
    save_service: SaveService,
    slot_store: SaveSlotStore,
    battle_service: BattleService,
    area_service: AreaService,
) -> List[object] | None:
    render_heading("Camp Interlude")
    if message:
        print(message)
    state.mode = "camp_menu"
    while True:
        menu_entries = _build_camp_menu_entries(state)
        _print_debug_status(state, context="camp")
        render_menu("Camp Menu", [label for label, _ in menu_entries])
        index = _prompt_menu_index(len(menu_entries))
        action = menu_entries[index][1]
        if action == "continue":
            if state.story_checkpoint_thread_id in (None, "main_story"):
                _warp_to_checkpoint_location(area_service, state)
            resumed_events = story_service.resume_pending_flow(state)
            if not resumed_events:
                print("No pending story nodes. Explore via Travel or Save your progress.")
                continue
            state.mode = "story"
            state.camp_message = None
            return resumed_events
        if action == "travel":
            travel_follow_up = _handle_travel_menu(area_service, story_service, state)
            if travel_follow_up is not None:
                return travel_follow_up
            continue
        if action == "location_debug":
            _render_location_debug_snapshot(area_service, state)
            continue
        if action == "inventory":
            _run_inventory_flow(inventory_service, state)
            continue
        if action == "talk":
            _handle_menu_party_talk(state)
            continue
        if action == "save":
            _handle_save_request(state, save_service, slot_store)
            continue
        return None


def _handle_defeat_flow(
    battle_service: BattleService,
    story_service: StoryService,
    inventory_service: InventoryService,
    state: GameState,
    save_service: SaveService,
    slot_store: SaveSlotStore,
    area_service: AreaService,
) -> bool:
    story_service.rewind_to_checkpoint(state)
    battle_service.restore_party_resources(state, restore_hp=True, restore_mp=True)
    state.flags["flag_last_battle_defeat"] = True
    message = _DEFEAT_CAMP_MESSAGE
    state.mode = "camp_menu"
    state.camp_message = message
    follow_up = _run_post_battle_interlude(
        message,
        story_service,
        inventory_service,
        state,
        save_service,
        slot_store,
        battle_service,
        area_service,
    )
    if follow_up is None:
        return False
    if not follow_up:
        return True
    return _handle_story_events(
        follow_up,
        battle_service,
        story_service,
        inventory_service,
        state,
        save_service,
        slot_store,
        area_service,
        print_header=bool(follow_up),
    )


def _handle_travel_menu(
    area_service: AreaService, story_service: StoryService, state: GameState
) -> List[object] | None:
    while True:
        location_view = area_service.get_current_location_view(state)
        _render_travel_context(location_view, state)
        connections = list(location_view.connections)
        if not connections:
            print("No destinations are available from here yet.")
            return None
        options = [conn.label for conn in connections]
        options.append("Back")
        render_menu("Travel Destinations", options)
        choice = _prompt_menu_index(len(options))
        if choice == len(connections):
            return None
        destination = connections[choice]
        if state.story_checkpoint_node_id and destination.progresses_story:
            print(TRAVEL_BLOCKED_MESSAGE)
            continue
        try:
            result = area_service.travel_to(state, destination.destination_id)
        except TravelBlockedError as exc:
            print(str(exc))
            continue
        except ValueError as exc:
            print(f"Cannot travel: {exc}")
            continue
        _render_travel_events(result.events)
        if result.entry_story_node_id:
            return story_service.play_node(state, result.entry_story_node_id)
        return None


def _render_travel_context(location_view: LocationView, state: GameState) -> None:
    render_heading("Travel")
    print(f"Current Location: {location_view.name}")
    print(location_view.description)
    if _debug_enabled():
        tags = ", ".join(location_view.tags)
        entry_info = location_view.entry_story_node_id or "None"
        print(f"[DEBUG] id={location_view.id} tags=[{tags}] entry_story={entry_info} entry_seen={location_view.entry_seen}")
    _print_debug_status(state, context="travel")


def _render_travel_events(events: List[object]) -> None:
    if not events:
        return
    render_events_header()
    for event in events:
        if isinstance(event, TravelPerformedEvent):
            print(
                f"- Traveled from {event.from_location_name} to {event.to_location_name}."
            )
        elif isinstance(event, LocationEnteredEvent):
            _render_location_arrival(event.location)


def _render_location_arrival(location_view: LocationView) -> None:
    render_heading(f"Location: {location_view.name}")
    print(location_view.description)
    if _debug_enabled():
        tags = ", ".join(location_view.tags)
        entry_story = location_view.entry_story_node_id or "None"
        print(f"[DEBUG] id={location_view.id} tags=[{tags}] entry_story={entry_story} entry_seen={location_view.entry_seen}")


def _render_location_debug_snapshot(area_service: AreaService, state: GameState) -> None:
    debug_view = area_service.build_debug_view(state)
    render_heading("DEBUG: Location State")
    location = debug_view.location
    print(f"Current: {location.name} ({location.id})")
    print(f"Tags: {', '.join(location.tags)}")
    print(
        f"Entry story: {location.entry_story_node_id or 'None'} | entry_seen={location.entry_seen}"
    )
    if location.connections:
        print("Connections:")
        for conn in location.connections:
            print(f"  -> {conn.label} ({conn.destination_id})")
    else:
        print("Connections: (none)")
    visited = ", ".join(debug_view.visited_locations) if debug_view.visited_locations else "(none)"
    print(f"Visited order: {visited}")
    print("Entry flags:")
    for area_id, seen in debug_view.entry_seen_flags:
        print(f"  {area_id}: {seen}")
def _handle_save_request(state: GameState, save_service: SaveService, slot_store: SaveSlotStore) -> None:
    selection = _prompt_slot_choice(slot_store, title="Save Game")
    if selection is None:
        return
    try:
        payload = save_service.serialize(state)
        slot_store.write_slot(selection.slot, payload)
    except OSError as exc:
        print(f"Save failed: {exc}")
        return
    print(f"Saved to Slot {selection.slot}.")


def _prompt_slot_choice(slot_store: SaveSlotStore, *, title: str) -> SlotMetadata | None:
    entries = slot_store.list_slots()
    options = [_format_slot_label(entry) for entry in entries]
    options.append("Back")
    render_menu(title, options)
    choice = _prompt_menu_index(len(options))
    if choice == len(entries):
        return None
    return entries[choice]


def _handle_menu_party_talk(state: GameState) -> None:
    if not state.party_members:
        print("No companions to speak with.")
        return
    member_id = _prompt_party_member_choice(state, prompt_title="Camp Conversation")
    lines = _MENU_TALK_LINES.get(member_id, ["We should stay alert."])
    render_heading("Party Talk")
    print(f"{member_id.title()}: {lines[0]}")


def _run_inventory_flow(inventory_service: InventoryService, state: GameState) -> None:
    while True:
        summary = inventory_service.build_inventory_summary(state)
        render_heading("Shared Inventory")
        _render_inventory_summary(summary)
        members = inventory_service.list_party_members(state)
        if not members:
            print("No party members available.")
            return
        options = [member.name for member in members]
        options.append("Back")
        render_menu("Select a party member", options)
        choice = _prompt_menu_index(len(options))
        if choice == len(options) - 1:
            return
        _run_member_equipment_menu(members[choice], inventory_service, state)


def _render_inventory_summary(summary: InventorySummary) -> None:
    if summary.weapons:
        print("Weapons:")
        for weapon_id, name, qty, slot_cost in summary.weapons:
            hand = "2H" if slot_cost == 2 else "1H"
            print(f"  {name} x{qty} [{hand}] ({weapon_id})")
    else:
        print("Weapons: (none)")

    if summary.armour:
        print("Armour:")
        for armour_id, name, qty, slot in summary.armour:
            print(f"  {name} x{qty} [{slot}] ({armour_id})")
    else:
        print("Armour: (none)")

    if summary.items:
        print("Items:")
        for item_id, qty in summary.items:
            print(f"  {item_id} x{qty}")
    else:
        print("Items: (none)")


def _run_member_equipment_menu(
    member: PartyMemberView,
    inventory_service: InventoryService,
    state: GameState,
) -> None:
    while True:
        weapon_slots, armour_slots = inventory_service.build_member_equipment_view(
            state, member.member_id
        )
        render_heading(f"{member.name}'s Equipment")
        _display_weapon_slots(weapon_slots)
        _display_armour_slots(armour_slots)
        options = ["Manage Weapons", "Manage Armour", "Back"]
        render_menu("Equipment Options", options)
        choice = _prompt_menu_index(len(options))
        if choice == 0:
            _run_weapon_menu(member, inventory_service, state)
        elif choice == 1:
            _run_armour_menu(member, inventory_service, state)
        else:
            return


def _display_weapon_slots(weapon_slots: List[WeaponSlotView]) -> None:
    print("Weapons:")
    for slot in weapon_slots:
        label = f"  Slot {slot.slot_index + 1}: "
        if slot.weapon_name:
            hand = "2H" if (slot.slot_cost or 1) == 2 else "1H"
            print(f"{label}{slot.weapon_name} [{hand}]")
        else:
            print(f"{label}Empty")


def _display_armour_slots(armour_slots: List[ArmourSlotView]) -> None:
    print("Armour:")
    for slot in armour_slots:
        name = slot.armour_name or "Empty"
        print(f"  {slot.slot.title()}: {name}")


def _run_weapon_menu(
    member: PartyMemberView,
    inventory_service: InventoryService,
    state: GameState,
) -> None:
    while True:
        weapon_slots, _ = inventory_service.build_member_equipment_view(state, member.member_id)
        render_heading(f"{member.name} – Weapons")
        _display_weapon_slots(weapon_slots)
        options = ["Equip Weapon", "Unequip Slot 1", "Unequip Slot 2", "Back"]
        render_menu("Weapon Actions", options)
        choice = _prompt_menu_index(len(options))
        if choice == 0:
            summary = inventory_service.build_inventory_summary(state)
            if not summary.weapons:
                print("No weapons available in the shared inventory.")
                continue
            weapon_choice = _prompt_inventory_selection(
                summary.weapons,
                "Select weapon to equip",
                formatter=lambda entry: f"{entry[1]} x{entry[2]} ({'2H' if entry[3] == 2 else '1H'})",
            )
            if weapon_choice is None:
                continue
            weapon_id, weapon_name, _, slot_cost = weapon_choice
            slot_index = None
            allow_replace = False
            if slot_cost == 1:
                slot_index = _prompt_weapon_slot_choice(weapon_slots)
                if slot_index is None:
                    continue
                current_item = weapon_slots[slot_index].weapon_name
                if current_item:
                    if not _prompt_confirmation(
                        f"Replace {current_item} in slot {slot_index + 1}?"
                    ):
                        continue
                    allow_replace = True
            else:
                occupied = any(slot.weapon_id for slot in weapon_slots)
                if occupied and not _prompt_confirmation(
                    "Two-handed weapons use both slots. Replace current weapons?"
                ):
                    continue
                allow_replace = occupied
                slot_index = None
            events = inventory_service.equip_weapon(
                state,
                member.member_id,
                weapon_id,
                slot_index=slot_index,
                allow_replace=allow_replace,
            )
            _render_inventory_events(events)
        elif choice in (1, 2):
            slot_to_clear = choice - 1
            events = inventory_service.unequip_weapon_slot(
                state, member.member_id, slot_to_clear
            )
            _render_inventory_events(events)
        else:
            return


def _run_armour_menu(
    member: PartyMemberView,
    inventory_service: InventoryService,
    state: GameState,
) -> None:
    while True:
        _, armour_slots = inventory_service.build_member_equipment_view(state, member.member_id)
        render_heading(f"{member.name} – Armour")
        _display_armour_slots(armour_slots)
        options = ["Equip Armour", "Unequip Slot", "Back"]
        render_menu("Armour Actions", options)
        choice = _prompt_menu_index(len(options))
        if choice == 0:
            summary = inventory_service.build_inventory_summary(state)
            if not summary.armour:
                print("No armour available in the shared inventory.")
                continue
            armour_choice = _prompt_inventory_selection(
                summary.armour,
                "Select armour to equip",
                formatter=lambda entry: f"{entry[1]} x{entry[2]} ({entry[3]})",
            )
            if armour_choice is None:
                continue
            armour_id, armour_name, _, slot = armour_choice
            current = next((s for s in armour_slots if s.slot == slot), None)
            allow_replace = False
            if current and current.armour_id:
                if not _prompt_confirmation(
                    f"Replace {current.armour_name} in {slot} slot?"
                ):
                    continue
                allow_replace = True
            events = inventory_service.equip_armour(
                state, member.member_id, armour_id, allow_replace=allow_replace
            )
            _render_inventory_events(events)
        elif choice == 1:
            slot_choice = _prompt_armour_slot_choice()
            if slot_choice is None:
                continue
            events = inventory_service.unequip_armour_slot(
                state, member.member_id, slot_choice
            )
            _render_inventory_events(events)
        else:
            return


def _prompt_weapon_slot_choice(weapon_slots: List[WeaponSlotView]) -> int | None:
    while True:
        raw = input("Equip to slot (1 or 2, blank to cancel): ").strip()
        if not raw:
            return None
        if raw in {"1", "2"}:
            return int(raw) - 1
        print("Please enter 1, 2, or press Enter to cancel.")


def _prompt_armour_slot_choice() -> str | None:
    slots = list(slot for slot in ARMOUR_SLOTS)
    render_menu("Choose armour slot to unequip", [slot.title() for slot in slots] + ["Back"])
    choice = _prompt_menu_index(len(slots) + 1)
    if choice == len(slots):
        return None
    return slots[choice]


def _prompt_inventory_selection(
    entries: Sequence,
    title: str,
    *,
    formatter,
) -> tuple | None:
    render_menu(title, [formatter(entry) for entry in entries] + ["Back"])
    choice = _prompt_menu_index(len(entries) + 1)
    if choice == len(entries):
        return None
    return entries[choice]


def _prompt_menu_index(option_count: int) -> int:
    while True:
        raw = input("Select an option: ").strip()
        try:
            selection = int(raw) - 1
        except ValueError:
            print("Please enter a number.")
            continue
        if 0 <= selection < option_count:
            return selection
        print(f"Please enter a number between 1 and {option_count}.")


def _prompt_confirmation(message: str) -> bool:
    while True:
        raw = input(f"{message} (y/n): ").strip().lower()
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no", ""}:
            return False
        print("Please enter 'y' or 'n'.")


def _render_inventory_events(events: List[InventoryEvent]) -> None:
    if not events:
        return
    render_events_header()
    for event in events:
        if isinstance(event, ItemEquippedEvent):
            print(
                f"- {event.member_name} equipped {event.item_name} ({event.slot.replace('_', ' ').title()})."
            )
        elif isinstance(event, ItemUnequippedEvent):
            print(
                f"- {event.member_name} unequipped {event.item_name} ({event.slot.replace('_', ' ').title()})."
            )
        elif isinstance(event, EquipFailedEvent):
            print(f"- {event.message}")
def _run_battle_loop(battle_service: BattleService, battle_state: BattleState, state: GameState) -> bool:
    """Run the deterministic battle loop until victory or defeat."""
    first_snapshot = True
    while not battle_state.is_over:
        view = battle_service.get_battle_view(battle_state)
        _render_battle_view(view, show_banner=first_snapshot)
        first_snapshot = False
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
                    events = battle_service.party_talk(battle_state, speaker_combatant_id, state.rng)
            else:
                events = battle_service.run_ally_ai_turn(battle_state, actor.instance_id, state.rng)
        else:
            events = battle_service.run_enemy_turn(battle_state, state.rng)
        _render_battle_events(events)
    if battle_state.victor == "allies":
        reward_events = battle_service.apply_victory_rewards(battle_state, state)
        _render_battle_events(reward_events)
    return battle_state.victor == "allies"


def _render_battle_view(view: BattleView, *, show_banner: bool) -> None:
    debug_enabled = _debug_enabled()
    if show_banner:
        render_heading(f"Battle {view.battle_id}")
    else:
        actor_name = _lookup_combatant_name(view, view.current_actor_id)
        render_heading(f"Turn: {actor_name or 'Battle Continues'}")
    print("Allies:")
    for ally in view.allies:
        status = "DOWN" if not ally.is_alive else ally.hp_display
        marker = "*" if ally.instance_id == view.current_actor_id else " "
        print(f"{marker} {ally.name:<12} HP {status}")
    print("Enemies:")
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
        render_menu("Actions", [label for _, label in options])
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
        render_heading("Skills")
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
        render_heading("Select Targets")
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
        render_heading("Choose Target")
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


def _prompt_party_member_choice(state: GameState, prompt_title: str = "Party Talk") -> str:
    while True:
        render_heading(prompt_title)
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
    if not events:
        return
    standard_header_printed = False
    in_rewards_block = False
    for event in events:
        if isinstance(event, BattleRewardsHeaderEvent):
            render_heading("Battle Rewards")
            in_rewards_block = True
            continue
        if not in_rewards_block and not standard_header_printed:
            render_events_header()
            standard_header_printed = True
        if isinstance(event, BattleStartedEvent):
            print(f"- Battle started against {', '.join(event.enemy_names)}.")
        elif isinstance(event, AttackResolvedEvent):
            print(f"- {event.attacker_name} hits {event.target_name} for {event.damage} damage.")
        elif isinstance(event, CombatantDefeatedEvent):
            print(f"- {event.combatant_name} is defeated.")
        elif isinstance(event, PartyTalkEvent):
            print(f"- {event.text}")
        elif isinstance(event, SkillUsedEvent):
            print(f"- {event.attacker_name} uses {event.skill_name} on {event.target_name} for {event.damage} damage.")
        elif isinstance(event, GuardAppliedEvent):
            print(f"- {event.combatant_name} braces, reducing the next hit by {event.amount}.")
        elif isinstance(event, SkillFailedEvent):
            print(f"- {event.combatant_name} cannot use that skill ({event.reason}).")
        elif isinstance(event, BattleResolvedEvent):
            print(f"- Battle resolved. Victor: {event.victor.title()}")
        elif isinstance(event, BattleGoldRewardEvent):
            print(f"- Gained {event.amount} gold (Total: {event.total_gold}).")
        elif isinstance(event, BattleExpRewardEvent):
            print(f"- {event.member_name} gains {event.amount} EXP (Level {event.new_level}).")
        elif isinstance(event, BattleLevelUpEvent):
            print(f"- {event.member_name} reached Level {event.new_level}!")
        elif isinstance(event, LootAcquiredEvent):
            print(f"- Loot: {event.item_name} x{event.quantity}")
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
    return f"{enemy.hp_display} [{enemy.current_hp}/{enemy.max_hp}]"


def _lookup_combatant_name(view: BattleView, combatant_id: str | None) -> str | None:
    if combatant_id is None:
        return None
    for roster in (view.allies, view.enemies):
        for combatant in roster:
            if combatant.instance_id == combatant_id:
                return combatant.name
    return None


def _render_story_if_needed(
    story_service: StoryService,
    state: GameState,
    rendered_flag: bool,
) -> bool:
    if rendered_flag:
        return True
    node_view = story_service.get_current_node_view(state)
    render_story(node_view.segments)
    return True



