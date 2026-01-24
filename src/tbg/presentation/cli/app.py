"""Console-driven UI loops for TBG."""
from __future__ import annotations
import secrets
import shutil
import textwrap
from typing import Callable, List, Literal, Sequence

from tbg.data.repositories import (
    ArmourRepository,
    ClassesRepository,
    EnemiesRepository,
    FloorsRepository,
    ItemsRepository,
    KnowledgeRepository,
    LocationsRepository,
    LootTablesRepository,
    PartyMembersRepository,
    QuestsRepository,
    StoryRepository,
    SkillsRepository,
    SummonsRepository,
    WeaponsRepository,
    ShopsRepository,
)
from tbg.domain.battle_models import BattleCombatantView, BattleState, Combatant
from tbg.domain.attribute_scaling import AttributeScalingBreakdown
from tbg.domain.entities import Attributes
from tbg.domain.inventory import ARMOUR_SLOTS
from tbg.domain.defs import SkillDef
from tbg.domain.state import GameState
from tbg.services import (
    AreaServiceV2,
    AttributeAllocationService,
    BattleAction,
    BattleController,
    BattleRequestedEvent,
    ChoiceResult,
    ExpGainedEvent,
    GameMenuEnteredEvent,
    GoldGainedEvent,
    LocationEnteredEvent,
    LocationView,
    PartyExpGrantedEvent,
    PartyLevelUpEvent,
    PartyMemberJoinedEvent,
    PlayerClassSetEvent,
    QuestAcceptedEvent,
    QuestCompletedEvent,
    QuestTurnedInEvent,
    QuestService,
    SaveLoadError,
    SaveService,
    SummonLoadoutService,
    StoryNodeView,
    StoryService,
    TravelBlockedError,
    TravelPerformedEvent,
)
from tbg.services.quest_service import QuestJournalView, QuestTurnInView
from tbg.services.area_service_v2 import TRAVEL_BLOCKED_MESSAGE
from tbg.services.shop_service import (
    ShopActionFailedEvent,
    ShopDebugGoldGrantedEvent,
    ShopBatchResult,
    ShopPurchaseEvent,
    ShopSaleEvent,
    ShopService,
    ShopSummaryView,
    ShopView,
)
from tbg.services.battle_service import (
    AttackResolvedEvent,
    BattleEvent,
    BattleExpRewardEvent,
    BattleGoldRewardEvent,
    BattleInventoryItem,
    BattleLevelUpEvent,
    BattleResolvedEvent,
    BattleRewardsHeaderEvent,
    BattleService,
    BattleStartedEvent,
    BattleView,
    CombatantDefeatedEvent,
    DebuffAppliedEvent,
    DebuffExpiredEvent,
    GuardAppliedEvent,
    ItemUsedEvent,
    LootAcquiredEvent,
    PartyTalkEvent,
    SummonSpawnedEvent,
    SummonAutoSpawnDebugEvent,
    SkillFailedEvent,
    SkillUsedEvent,
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
from . import config
from .render import (
    debug_enabled,
    get_text_display_mode,
    render_bullet_lines,
    render_choices,
    render_events_header,
    render_heading,
    render_menu,
    render_story,
    set_text_display_mode,
    wrap_text_for_box,
)
from .save_slots import SaveSlotStore, SlotMetadata

MenuAction = Literal["new_game", "load_game", "options", "information", "quit"]
InfoAction = Literal[
    "about",
    "content",
    "locked",
    "progress",
    "saves",
    "credits",
    "back",
]

GAME_NAME = "Echoes of the Cycle"
GAME_VERSION = "v0.0.1"
DEMO_MESSAGE = "Demo build — content is limited; reaching an ending is expected."
_MAX_RANDOM_SEED = 2**31 - 1
_MENU_TALK_LINES = {
    "emma": [
        "We handled that ambush together. Let's keep that rhythm.",
        "If more goblins show up, we strike first this time.",
    ]
}
_DEFEAT_CAMP_MESSAGE = "You barely make it back to camp, bruised but alive."
_BATTLE_UI_WIDTH = 60
_BATTLE_STATE_LEFT_COL = 27
_BATTLE_STATE_RIGHT_COL = _BATTLE_UI_WIDTH - 3 - _BATTLE_STATE_LEFT_COL
_BATTLE_STATE_MIN_TOTAL = 72
_BATTLE_STATE_MIN_COL = 32
_TURN_SEPARATOR = "=" * _BATTLE_UI_WIDTH
_MENU_RESELECT = object()


def _battle_box_border(char: str = "-") -> str:
    fill = char * (_BATTLE_UI_WIDTH - 2)
    return f"+{fill}+"


def _battle_box_line(text: str) -> str:
    content = text[: _BATTLE_UI_WIDTH - 4]
    return f"| {content.ljust(_BATTLE_UI_WIDTH - 4)} |"


def _render_boxed_panel(title: str, lines: Sequence[str]) -> None:
    """Render a boxed panel with word-wrapped content."""
    print(_battle_box_border("-"))
    print(_battle_box_line(title.upper()))
    
    # Word-wrap each line to fit within the box
    box_inner_width = _BATTLE_UI_WIDTH - 4
    for line in lines or [""]:
        if line.startswith("  "):
            content = line[2:]
            wrapped_lines = wrap_text_for_box(
                content, box_inner_width - 2, indent_continuation=False
            )
            for wrapped in wrapped_lines:
                print(_battle_box_line(f"  {wrapped}"))
        else:
            wrapped_lines = wrap_text_for_box(line, box_inner_width, indent_continuation=True)
            for wrapped in wrapped_lines:
                print(_battle_box_line(wrapped))
    
    print(_battle_box_border("-"))


def _render_turn_separator() -> None:
    print(f"\n{_TURN_SEPARATOR}")


def _render_turn_header(actor_name: str | None) -> None:
    label = actor_name or "Unknown"
    _render_boxed_panel("TURN", [f"{label}"])


def _truncate_cell(text: str, width: int) -> str:
    if len(text) <= width:
        return text.ljust(width)
    if width <= 3:
        return text[:width]
    return f"{text[: width - 3]}...".ljust(width)


def _truncate_enemy_name(
    name_segment: str,
    width: int,
    *,
    raw_name: str,
    prefix_len: int = 2,
) -> str:
    if len(name_segment) <= width:
        return name_segment.ljust(width)
    if not (raw_name.endswith(")") and " (" in raw_name):
        return _truncate_cell(name_segment, width)
    suffix = raw_name[raw_name.rfind(" (") :]
    base_name = raw_name[: -len(suffix)]
    prefix = name_segment[:prefix_len]
    base_width = width - len(prefix) - len(suffix)
    if base_width <= 0:
        return _truncate_cell(name_segment, width)
    if len(base_name) > base_width and base_width > 3:
        base = f"{base_name[: base_width - 3]}..."
    else:
        base = base_name[:base_width]
    return f"{prefix}{base}{suffix}".ljust(width)


def _render_state_row(left: str, right: str, *, left_width: int, right_width: int) -> None:
    left_display = f" {left}" if left else ""
    right_display = f" {right}" if right else ""
    left_cell = _truncate_cell(left_display, left_width)
    right_cell = _truncate_cell(right_display, right_width)
    print(f"|{left_cell}|{right_cell}|")


def _state_row_border(*, left_width: int, right_width: int) -> str:
    left = "-" * left_width
    right = "-" * right_width
    return f"+{left}+{right}+"


def _battle_state_layout() -> tuple[int, int, int]:
    terminal_width = shutil.get_terminal_size((_BATTLE_UI_WIDTH, 0)).columns
    if terminal_width < _BATTLE_STATE_MIN_TOTAL:
        total = _BATTLE_UI_WIDTH
        return total, _BATTLE_STATE_LEFT_COL, _BATTLE_STATE_RIGHT_COL
    total = terminal_width
    available = total - 3
    if available < _BATTLE_STATE_MIN_COL * 2:
        left = max(1, available // 2)
        right = available - left
        return total, left, right
    left = available // 2
    right = available - left
    return total, left, right


def _wrap_text_to_width(text: str, width: int) -> List[str]:
    if width <= 0:
        return [text]
    lines = textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False)
    return lines or [""]


def _build_turn_order_map(battle_state: BattleState) -> dict[str, int]:
    queue = list(battle_state.turn_queue)
    if not queue:
        return {}
    current = battle_state.current_actor_id
    if current in queue:
        idx = queue.index(current)
        queue = queue[idx:] + queue[:idx]
    return {instance_id: idx + 1 for idx, instance_id in enumerate(queue)}


def _render_battle_state_panel(view: BattleView, battle_state: BattleState, *, active_id: str | None) -> None:
    debug_enabled = _debug_enabled()
    turn_order = _build_turn_order_map(battle_state) if debug_enabled else {}
    _, left_width, right_width = _battle_state_layout()
    allies_lines: List[str] = []
    for ally in view.allies:
        marker = ">" if ally.instance_id == active_id else " "
        order_value = turn_order.get(ally.instance_id)
        order_prefix = f"{order_value:>2} " if order_value is not None else ""
        combatant = _find_combatant(battle_state, ally.instance_id)
        mp_text = "--/--"
        if combatant is not None:
            mp_text = f"{combatant.stats.mp}/{combatant.stats.max_mp}"
        hp_display = ally.hp_display if ally.is_alive else "DOWN"
        allies_lines.append(
            _format_battle_state_ally_line(
                marker=marker,
                order_prefix=order_prefix,
                name=ally.name,
                hp_display=hp_display,
                mp_text=mp_text,
                width=left_width,
            )
        )
    enemies_lines: List[str] = []
    enemy_name_lookup = {
        combatant.instance_id: combatant.display_name
        for combatant in battle_state.enemies
    }
    for enemy in view.enemies:
        marker = ">" if enemy.instance_id == active_id else " "
        status = _format_enemy_hp_display(enemy, debug_enabled=debug_enabled)
        combatant_ref = _find_combatant(battle_state, enemy.instance_id)
        badges = _format_enemy_debuff_badges(combatant_ref)
        if badges:
            status = f"{status} {badges}"
        display_name = enemy_name_lookup.get(enemy.instance_id, enemy.name)
        order_value = turn_order.get(enemy.instance_id)
        order_prefix = f"{order_value:>2} " if order_value is not None else ""
        prefix = f"{marker} {order_prefix}"
        name_segment = f"{prefix}{display_name}"
        gap = " "
        available_width = right_width - 1  # account for leading space applied later
        name_width = available_width - len(status) - len(gap)
        if name_width < 0:
            name_width = 0
        if name_width > 0:
            trimmed_name = _truncate_enemy_name(
                name_segment, name_width, raw_name=display_name, prefix_len=len(prefix)
            ).rstrip()
        else:
            trimmed_name = ""
        spacer = gap if trimmed_name else ""
        enemies_lines.append(f"{trimmed_name}{spacer}{status}")
        if debug_enabled:
            debug_lines = _build_enemy_scaling_lines(combatant_ref, right_width)
            for line in debug_lines:
                enemies_lines.append(line)
    rows = max(len(allies_lines), len(enemies_lines))
    print(_state_row_border(left_width=left_width, right_width=right_width))
    _render_state_row("ALLIES", "ENEMIES", left_width=left_width, right_width=right_width)
    for index in range(rows):
        left = allies_lines[index] if index < len(allies_lines) else ""
        right = enemies_lines[index] if index < len(enemies_lines) else ""
        _render_state_row(left, right, left_width=left_width, right_width=right_width)
    print(_state_row_border(left_width=left_width, right_width=right_width))
    if debug_enabled:
        _render_debug_enemy_debuffs(battle_state)


def _render_results_panel(lines: Sequence[str]) -> None:
    panel_lines = lines or ["- Nothing happens."]
    _render_boxed_panel("Results", panel_lines)


def _debug_enabled() -> bool:
    return debug_enabled()


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
        ("Options", "options"),
        ("Information", "information"),
        ("Quit", "quit"),
    ]


def _print_startup_banner() -> None:
    print(f"=== {GAME_NAME} {GAME_VERSION} ===")
    print(DEMO_MESSAGE)


def _print_main_menu_header() -> None:
    print(f"Main Menu — {GAME_NAME} {GAME_VERSION}")


def _show_placeholder_screen(title: str, lines: Sequence[str]) -> None:
    render_heading(title)
    for line in lines:
        print(line)
    input("\nPress Enter to return to the main menu...")


def _information_menu_options() -> List[tuple[str, InfoAction]]:
    return [
        ("About This Demo", "about"),
        ("Available Content", "content"),
        ("Locked / Future Content", "locked"),
        ("How to Progress", "progress"),
        ("Save & Replay Expectations", "saves"),
        ("Credits & Version", "credits"),
        ("Back", "back"),
    ]


def _info_about_demo() -> None:
    render_heading("About This Demo")
    lines = [
        "This is a demo / vertical slice of Echoes of the Cycle.",
        "Content is intentionally limited to showcase early systems, tone, and structure.",
        "Reaching an ending is expected in this demo.",
    ]
    render_bullet_lines(lines)
    input("\nPress Enter to return to Information...")


def _info_available_content() -> None:
    render_heading("Available Content")
    lines = [
        "Chapter 00 tutorial slice.",
        "Core mechanics: combat, travel, towns, and party management.",
        "A complete demo ending is included.",
    ]
    render_bullet_lines(lines)
    input("\nPress Enter to return to Information...")


def _info_locked_content() -> None:
    render_heading("Locked / Future Content")
    lines = [
        "Additional chapters and areas are intentionally unavailable in this demo.",
        "Missing content is not caused by player failure or skipped actions.",
        "This demo focuses on a small, complete slice of the experience.",
    ]
    render_bullet_lines(lines)
    input("\nPress Enter to return to Information...")


def _info_how_to_progress() -> None:
    render_heading("How to Progress")
    lines = [
        "\"No pending story nodes\" means there is no immediate scripted scene.",
        "Travel is the primary way to discover new content and encounters.",
        "Some states are natural pauses or the end of available demo content.",
    ]
    render_bullet_lines(lines)
    input("\nPress Enter to return to Information...")


def _info_save_replay() -> None:
    render_heading("Save & Replay Expectations")
    lines = [
        "Saves are manual and stored in slots.",
        "Saving to a slot overwrites its previous contents.",
        "Replay is expected and safe in a demo context.",
        "Future versions may change save compatibility.",
    ]
    render_bullet_lines(lines)
    input("\nPress Enter to return to Information...")


def _info_credits_version() -> None:
    render_heading("Credits & Version")
    lines = [
        f"Game: {GAME_NAME}",
        f"Version: {GAME_VERSION}",
        "Author: TBG Project",
        "Thank you for playing.",
    ]
    render_bullet_lines(lines)
    input("\nPress Enter to return to Information...")


def _run_information_menu() -> None:
    while True:
        render_menu("Information", [label for label, _ in _information_menu_options()])
        choice = _prompt_menu_index(len(_information_menu_options()))
        action = _information_menu_options()[choice][1]
        if action == "back":
            return
        if action == "about":
            _info_about_demo()
        elif action == "content":
            _info_available_content()
        elif action == "locked":
            _info_locked_content()
        elif action == "progress":
            _info_how_to_progress()
        elif action == "saves":
            _info_save_replay()
        elif action == "credits":
            _info_credits_version()


def _run_options_menu() -> None:
    while True:
        mode_label = "Instant" if get_text_display_mode() == "instant" else "Step"
        options = [
            f"Text display mode: {mode_label} (select to change)",
            "Back",
        ]
        render_menu("Options", options)
        choice = _prompt_menu_index(len(options))
        if choice == 1:
            return
        new_mode = _run_text_display_mode_menu()
        if new_mode is None:
            continue
        set_text_display_mode(new_mode)
        config.save_config({"text_display_mode": new_mode})


def _run_text_display_mode_menu() -> str | None:
    options = [
        "Instant (default)",
        "Step (pause between story segments; press Enter to continue)",
        "Back",
    ]
    render_menu("Text Display Mode", options)
    choice = _prompt_menu_index(len(options))
    if choice == 0:
        return "instant"
    if choice == 1:
        return "step"
    return None


def _build_camp_menu_entries(
    state: GameState, summon_loadout_service: SummonLoadoutService
) -> List[tuple[str, str]]:
    entries: List[tuple[str, str]] = [
        ("Continue story", "continue"),
        ("Travel", "travel"),
    ]
    if _debug_enabled():
        entries.append(("Location Debug (DEBUG)", "location_debug"))
    entries.append(("Inventory / Equipment", "inventory"))
    entries.append(("Allocate Attributes", "allocate_attributes"))
    if state.party_members:
        entries.append(("Party Talk", "talk"))
    entries.append(("Save Game", "save"))
    entries.append(("Quit Game", "quit"))
    return entries


def _build_town_menu_entries(
    state: GameState, summon_loadout_service: SummonLoadoutService
) -> List[tuple[str, str]]:
    entries: List[tuple[str, str]] = [
        ("Continue", "continue"),
        ("Travel", "travel"),
    ]
    if _debug_enabled():
        entries.append(("Location Debug (DEBUG)", "location_debug"))
    entries.append(("Converse", "converse"))
    entries.append(("Quests", "quests"))
    entries.append(("Shops", "shops"))
    entries.append(("Inventory / Equipment", "inventory"))
    entries.append(("Allocate Attributes", "allocate_attributes"))
    if state.party_members:
        entries.append(("Party Talk", "talk"))
    entries.append(("Save Game", "save"))
    entries.append(("Quit Game", "quit"))
    return entries


def _has_known_summons(state: GameState, summon_loadout_service: SummonLoadoutService) -> bool:
    return bool(summon_loadout_service.list_known_summons(state))


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


def _warp_to_checkpoint_location(area_service: AreaServiceV2, state: GameState) -> bool:
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
        quest_service,
        shop_service,
        summon_loadout_service,
        attribute_service,
    ) = _build_services()
    slot_store = SaveSlotStore()
    settings = config.load_config()
    set_text_display_mode(settings.get("text_display_mode", "instant"))
    _print_startup_banner()
    running = True
    while running:
        action = _main_menu_loop()
        if action == "quit":
            running = False
            continue
        if action == "options":
            _run_options_menu()
            continue
        if action == "information":
            _run_information_menu()
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
            quest_service,
            shop_service,
            summon_loadout_service,
            attribute_service,
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
        _print_main_menu_header()
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


def _build_services() -> tuple[
    StoryService,
    BattleService,
    InventoryService,
    SaveService,
    AreaServiceV2,
    QuestService,
    ShopService,
    SummonLoadoutService,
    AttributeAllocationService,
]:
    weapons_repo = WeaponsRepository()
    armour_repo = ArmourRepository()
    summons_repo = SummonsRepository()
    story_repo = StoryRepository()
    classes_repo = ClassesRepository(
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        summons_repo=summons_repo,
    )
    party_repo = PartyMembersRepository()
    inventory_service = InventoryService(
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        party_members_repo=party_repo,
    )
    enemies_repo = EnemiesRepository()
    knowledge_repo = KnowledgeRepository()
    skills_repo = SkillsRepository()
    items_repo = ItemsRepository()
    loot_repo = LootTablesRepository()
    floors_repo = FloorsRepository()
    locations_repo = LocationsRepository(floors_repo=floors_repo)
    quests_repo = QuestsRepository(
        items_repo=items_repo,
        locations_repo=locations_repo,
        story_repo=story_repo,
    )
    shops_repo = ShopsRepository(
        items_repo=items_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
    )
    quest_service = QuestService(
        quests_repo=quests_repo,
        items_repo=items_repo,
        locations_repo=locations_repo,
        party_members_repo=party_repo,
    )
    story_service = StoryService(
        story_repo=story_repo,
        classes_repo=classes_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        party_members_repo=party_repo,
        inventory_service=inventory_service,
        quest_service=quest_service,
    )
    battle_service = BattleService(
        enemies_repo=enemies_repo,
        party_members_repo=party_repo,
        knowledge_repo=knowledge_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        skills_repo=skills_repo,
        items_repo=items_repo,
        loot_tables_repo=loot_repo,
        floors_repo=floors_repo,
        locations_repo=locations_repo,
        quest_service=quest_service,
    )
    area_service = AreaServiceV2(
        floors_repo=floors_repo, locations_repo=locations_repo, quest_service=quest_service
    )
    shop_service = ShopService(
        shops_repo=shops_repo,
        items_repo=items_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        summons_repo=summons_repo,
    )
    save_service = SaveService(
        story_repo=story_repo,
        classes_repo=classes_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        items_repo=items_repo,
        party_members_repo=party_repo,
        locations_repo=locations_repo,
        quests_repo=quests_repo,
    )
    summon_loadout_service = SummonLoadoutService(
        classes_repo=classes_repo,
        summons_repo=summons_repo,
    )
    attribute_service = AttributeAllocationService(classes_repo=classes_repo)
    return (
        story_service,
        battle_service,
        inventory_service,
        save_service,
        area_service,
        quest_service,
        shop_service,
        summon_loadout_service,
        attribute_service,
    )


def _start_new_game(story_service: StoryService, area_service: AreaServiceV2) -> GameState:
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
        action = _prompt_load_slot_action(selection, allow_load=not selection.is_corrupt)
        if action == "back":
            continue
        if action == "delete":
            if _confirm_delete_slot(selection):
                slot_store.delete_slot(selection.slot)
                print(f"Deleted Slot {selection.slot}.")
            continue
        if action != "load":
            continue
        if selection.is_corrupt:
            print("Load failed: Slot data is corrupt.")
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
    quest_service: QuestService,
    shop_service: ShopService,
    summon_loadout_service: SummonLoadoutService,
    attribute_service: AttributeAllocationService,
    state: GameState,
    save_service: SaveService,
    slot_store: SaveSlotStore,
    area_service: AreaServiceV2,
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
                quest_service,
                shop_service,
                summon_loadout_service,
                attribute_service,
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
                quest_service,
                shop_service,
                summon_loadout_service,
                attribute_service,
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
            if state.pending_story_node_id:
                resumed_events = story_service.resume_pending_flow(state)
                if resumed_events:
                    if not _handle_story_events(
                        resumed_events,
                        battle_service,
                        story_service,
                        inventory_service,
                        quest_service,
                        shop_service,
                        summon_loadout_service,
                        attribute_service,
                        state,
                        save_service,
                        slot_store,
                        area_service,
                        print_header=bool(resumed_events),
                    ):
                        return False
                continue
            print("End of demo slice. Returning to main menu.\n")
            return True
        choice_index = _prompt_choice(len(node_view.choices))
        result = story_service.choose(state, choice_index)
        if not _process_story_events(
            result,
            battle_service,
            story_service,
            inventory_service,
            quest_service,
            shop_service,
            summon_loadout_service,
            attribute_service,
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
    quest_service: QuestService,
    shop_service: ShopService,
    summon_loadout_service: SummonLoadoutService,
    attribute_service: AttributeAllocationService,
    state: GameState,
    save_service: SaveService,
    slot_store: SaveSlotStore,
    area_service: AreaServiceV2,
) -> bool:
    return _handle_story_events(
        result.events,
        battle_service,
        story_service,
        inventory_service,
        quest_service,
        shop_service,
        summon_loadout_service,
        attribute_service,
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
    quest_service: QuestService,
    shop_service: ShopService,
    summon_loadout_service: SummonLoadoutService,
    attribute_service: AttributeAllocationService,
    state: GameState,
    save_service: SaveService,
    slot_store: SaveSlotStore,
    area_service: AreaServiceV2,
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
                    quest_service,
                    shop_service,
                    summon_loadout_service,
                    attribute_service,
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
                quest_service,
                shop_service,
                summon_loadout_service,
                attribute_service,
                state,
                save_service,
                slot_store,
                area_service,
                print_header=bool(post_events),
            ):
                return False
        elif isinstance(event, PartyMemberJoinedEvent):
            print(f"- {event.member_id.title()} joins the party.")
        elif isinstance(event, PartyExpGrantedEvent):
            print(f"- {event.member_name} gains {event.amount} EXP (Level {event.new_level}).")
        elif isinstance(event, PartyLevelUpEvent):
            print(f"- {event.member_name} reached Level {event.new_level}!")
        elif isinstance(event, QuestAcceptedEvent):
            print(f"- Quest accepted: {event.quest_name}.")
        elif isinstance(event, QuestCompletedEvent):
            print(f"- Quest completed: {event.quest_name}.")
        elif isinstance(event, QuestTurnedInEvent):
            print(f"- Quest turned in: {event.quest_name}.")
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
                quest_service,
                shop_service,
                summon_loadout_service,
                attribute_service,
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
                quest_service,
                shop_service,
                    summon_loadout_service,
                attribute_service,
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
    quest_service: QuestService,
    shop_service: ShopService,
    summon_loadout_service: SummonLoadoutService,
    attribute_service: AttributeAllocationService,
    state: GameState,
    save_service: SaveService,
    slot_store: SaveSlotStore,
    battle_service: BattleService,
    area_service: AreaServiceV2,
) -> List[object] | None:
    render_heading("Camp Interlude")
    if message:
        print(message)
    state.mode = "camp_menu"
    while True:
        location_view = area_service.get_current_location_view(state)
        if "town" in location_view.tags:
            result = _run_town_menu(
                story_service,
                inventory_service,
                quest_service,
                shop_service,
                summon_loadout_service,
                attribute_service,
                state,
                save_service,
                slot_store,
                battle_service,
                area_service,
            )
        else:
            result = _run_camp_menu(
                story_service,
                inventory_service,
                quest_service,
                summon_loadout_service,
                attribute_service,
                state,
                save_service,
                slot_store,
                battle_service,
                area_service,
            )
        if result is _MENU_RESELECT:
            continue
        return result


def _run_camp_menu(
    story_service: StoryService,
    inventory_service: InventoryService,
    quest_service: QuestService,
    summon_loadout_service: SummonLoadoutService,
    attribute_service: AttributeAllocationService,
    state: GameState,
    save_service: SaveService,
    slot_store: SaveSlotStore,
    battle_service: BattleService,
    area_service: AreaServiceV2,
) -> List[object] | None:
    del battle_service  # Camp menu does not expose battle-specific flows.
    while True:
        menu_entries = _build_camp_menu_entries(state, summon_loadout_service)
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
            return _MENU_RESELECT
        if action == "location_debug":
            _render_location_debug_snapshot(area_service, quest_service, story_service, state)
            continue
        if action == "inventory":
            _run_inventory_flow(inventory_service, summon_loadout_service, state)
            continue
        if action == "allocate_attributes":
            _run_attribute_allocation_menu(attribute_service, inventory_service, state)
            continue
        if action == "talk":
            _handle_menu_party_talk(state)
            continue
        if action == "save":
            _handle_save_request(state, save_service, slot_store)
            continue
        return None


def _run_attribute_allocation_menu(
    attribute_service: AttributeAllocationService,
    inventory_service: InventoryService,
    state: GameState,
) -> None:
    if not state.player:
        print("No player is available for allocation.")
        return
    while True:
        summary = attribute_service.get_player_attribute_points_summary(state)
        breakdown = inventory_service.build_attribute_breakdown(state, state.player.id)
        lines = _build_attribute_lines(breakdown)
        lines.append(f"Available points: {summary.available}")
        render_heading("Allocate Attributes")
        _render_boxed_panel("Attributes", lines)
        if summary.available <= 0:
            options = ["Back"]
            if _debug_enabled():
                options.insert(0, "DEBUG: Grant Attribute Points")
            render_menu("Allocation Options", options)
            choice = _prompt_menu_index(len(options))
            if _debug_enabled() and choice == 0:
                amount = _prompt_non_negative_int("Enter number of points to grant: ")
                if amount < 1:
                    print("Grant amount must be at least 1.")
                    continue
                if amount > 999:
                    print("Grant amount must be 999 or less.")
                    continue
                result = attribute_service.grant_debug_attribute_points(state, amount)
                print(result.message)
                continue
            return
        options = ["STR", "DEX", "INT", "VIT", "BOND"]
        if _debug_enabled():
            options.append("DEBUG: Grant Attribute Points")
        options.append("Back")
        render_menu("Allocation Options", options)
        choice = _prompt_menu_index(len(options))
        if choice == len(options) - 1:
            return
        if _debug_enabled() and options[choice] == "DEBUG: Grant Attribute Points":
            amount = _prompt_non_negative_int("Enter number of points to grant: ")
            if amount < 1:
                print("Grant amount must be at least 1.")
                continue
            if amount > 999:
                print("Grant amount must be 999 or less.")
                continue
            result = attribute_service.grant_debug_attribute_points(state, amount)
            print(result.message)
            continue
        result = attribute_service.spend_player_attribute_point(state, options[choice])
        print(result.message)


def _run_town_menu(
    story_service: StoryService,
    inventory_service: InventoryService,
    quest_service: QuestService,
    shop_service: ShopService,
    summon_loadout_service: SummonLoadoutService,
    attribute_service: AttributeAllocationService,
    state: GameState,
    save_service: SaveService,
    slot_store: SaveSlotStore,
    battle_service: BattleService,
    area_service: AreaServiceV2,
) -> List[object] | None:
    del battle_service
    while True:
        menu_entries = _build_town_menu_entries(state, summon_loadout_service)
        _print_debug_status(state, context="town")
        render_menu("Town Menu", [label for label, _ in menu_entries])
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
            return _MENU_RESELECT
        if action == "location_debug":
            _render_location_debug_snapshot(area_service, quest_service, story_service, state)
            continue
        if action == "converse":
            follow_up = _handle_converse_menu(area_service, story_service, state)
            if follow_up is not None:
                return follow_up
            continue
        if action == "quests":
            quest_follow_up = _handle_quests_menu(quest_service, area_service, story_service, state)
            if quest_follow_up is not None:
                return quest_follow_up
            continue
        if action == "shops":
            _handle_shop_menu(shop_service, area_service, state)
            continue
        if action == "inventory":
            _run_inventory_flow(inventory_service, summon_loadout_service, state)
            continue
        if action == "allocate_attributes":
            _run_attribute_allocation_menu(attribute_service, inventory_service, state)
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
    quest_service: QuestService,
    shop_service: ShopService,
    summon_loadout_service: SummonLoadoutService,
    attribute_service: AttributeAllocationService,
    state: GameState,
    save_service: SaveService,
    slot_store: SaveSlotStore,
    area_service: AreaServiceV2,
) -> bool:
    lost_gold = _apply_defeat_gold_loss(state)
    open_area_battle = _is_open_area_location(area_service, state)
    if open_area_battle:
        _restore_minimum_resources(state)
        message = f"{_DEFEAT_CAMP_MESSAGE} You keep your place, but drop {lost_gold} gold."
    else:
        story_service.rewind_to_checkpoint(state)
        battle_service.restore_party_resources(state, restore_hp=True, restore_mp=True)
        message = f"{_DEFEAT_CAMP_MESSAGE} You drop {lost_gold} gold."
    state.flags["flag_last_battle_defeat"] = True
    state.mode = "camp_menu"
    state.camp_message = message
    follow_up = _run_post_battle_interlude(
        message,
        story_service,
        inventory_service,
        quest_service,
        shop_service,
        summon_loadout_service,
        attribute_service,
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
        quest_service,
        shop_service,
        summon_loadout_service,
        attribute_service,
        state,
        save_service,
        slot_store,
        area_service,
        print_header=bool(follow_up),
    )


def _apply_defeat_gold_loss(state: GameState) -> int:
    lost_gold = state.gold // 2
    state.gold -= lost_gold
    return lost_gold


def _restore_minimum_resources(state: GameState) -> None:
    if not state.player:
        return
    state.player.stats.hp = max(1, state.player.stats.hp)
    state.player.stats.mp = max(1, state.player.stats.mp)


def _is_open_area_location(area_service: AreaServiceV2, state: GameState) -> bool:
    try:
        location = area_service.get_current_location_view(state)
    except Exception:
        return False
    return "open" in location.tags


def _handle_travel_menu(
    area_service: AreaServiceV2, story_service: StoryService, state: GameState
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
        checkpoint_thread = state.story_checkpoint_thread_id or "main_story"
        if state.story_checkpoint_node_id and checkpoint_thread == "main_story" and destination.progresses_story:
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


def _npc_is_available(npc_id: str, location_id: str, state: GameState) -> bool:
    if npc_id == "cerel" and location_id == "threshold_inn":
        return state.flags.get("flag_cerel_returned_to_inn", False)
    return True


def _filter_location_npcs(location_view: LocationView, state: GameState) -> List[object]:
    return [
        npc
        for npc in location_view.npcs_present
        if _npc_is_available(npc.npc_id, location_view.id, state)
    ]


def _handle_converse_menu(
    area_service: AreaServiceV2, story_service: StoryService, state: GameState
) -> List[object] | None:
    location_view = area_service.get_current_location_view(state)
    npcs = _filter_location_npcs(location_view, state)
    if not npcs:
        print("No one is available to converse here.")
        return None
    options = [npc.npc_id.title() for npc in npcs]
    options.append("Back")
    render_menu("Converse", options)
    choice = _prompt_menu_index(len(options))
    if choice == len(npcs):
        return None
    npc = npcs[choice]
    return _play_node_with_auto_resume(story_service, state, npc.talk_node_id)


def _handle_quests_menu(
    quest_service: QuestService,
    area_service: AreaServiceV2,
    story_service: StoryService,
    state: GameState,
) -> List[object] | None:
    while True:
        journal = quest_service.build_journal_view(state)
        render_heading("Quest Journal")
        _render_quest_journal(journal)
        location_view = area_service.get_current_location_view(state)
        turn_ins = _filter_turn_ins_for_location(journal.turn_ins, location_view, state)
        turn_ins = _order_turn_ins(turn_ins, location_view)
        options = [
            f"Turn in: {entry.name} ({entry.npc_id or 'Unknown'})" for entry in turn_ins
        ]
        options.append("Back")
        if not options[:-1]:
            print("No quest turn-ins available here yet.")
        render_menu("Quest Options", options)
        choice = _prompt_menu_index(len(options))
        if choice == len(options) - 1:
            return None
        selected = turn_ins[choice]
        return _play_node_with_auto_resume(story_service, state, selected.node_id)


def _handle_shop_menu(shop_service: ShopService, area_service: AreaServiceV2, state: GameState) -> None:
    location_view = area_service.get_current_location_view(state)
    shops = shop_service.list_shops_for_location(location_view.tags)
    if not shops:
        print("No shops are available here.")
        return
    while True:
        options = [f"{shop.name} ({shop.shop_type.title()})" for shop in shops]
        options.append("Back")
        render_menu("Shops", options)
        choice = _prompt_menu_index(len(options))
        if choice == len(shops):
            return
        _run_shop_menu(shop_service, state, location_view.id, shops[choice])


def _run_shop_menu(
    shop_service: ShopService,
    state: GameState,
    location_id: str,
    shop: ShopSummaryView,
) -> None:
    while True:
        shop_view = shop_service.build_shop_view(state, location_id, shop.shop_id)
        render_heading(shop_view.name)
        _render_shop_stock(shop_view)
        options = ["Buy", "Sell", "Back"]
        if _debug_enabled():
            options.append("Give Gold (DEBUG)")
        render_menu("Shop Options", options)
        choice = _prompt_menu_index(len(options))
        if choice == 0:
            _run_shop_buy_menu(shop_service, state, location_id, shop_view)
            continue
        if choice == 1:
            _run_shop_sell_menu(shop_service, state, shop_view)
            continue
        if choice == 2:
            return
        if _debug_enabled() and choice == 3:
            amount = _prompt_non_negative_int("Gold to add: ")
            events = shop_service.grant_debug_gold(state, amount)
            _render_shop_events(events)
            continue
        return


def _run_shop_buy_menu(
    shop_service: ShopService,
    state: GameState,
    location_id: str,
    shop_view: ShopView,
) -> None:
    while True:
        refreshed = shop_service.build_shop_view(state, location_id, shop_view.shop_id)
        if not refreshed.entries:
            print("No stock is available right now.")
            return
        options = [
            f"{entry.name} - {entry.price}g (Stock: {entry.stock}, Owned: {entry.owned})"
            for entry in refreshed.entries
        ]
        options.append("Back")
        render_menu("Buy", options)
        selections = _prompt_index_batch(len(options), "Select items (comma-separated): ")
        if selections is None:
            continue
        if len(selections) == 1 and selections[0] == len(options):
            return
        if len(selections) > 1 and len(options) in selections:
            print("Back cannot be combined with other selections.")
            continue
        item_ids = [refreshed.entries[index - 1].item_id for index in selections]
        result = shop_service.buy_many(state, location_id, shop_view.shop_id, item_ids)
        _render_shop_events(result.events)
        _render_shop_batch_summary(result, action="Bought")


def _run_shop_sell_menu(
    shop_service: ShopService,
    state: GameState,
    shop_view: ShopView,
) -> None:
    while True:
        refreshed = shop_service.build_sell_view(state, shop_view.shop_id)
        if not refreshed.entries:
            print("Nothing to sell right now.")
            return
        options = [
            f"{entry.name} - {entry.price}g (Owned: {entry.owned})" for entry in refreshed.entries
        ]
        options.append("Back")
        render_menu("Sell", options)
        selections = _prompt_index_batch(len(options), "Select items (comma-separated): ")
        if selections is None:
            continue
        if len(selections) == 1 and selections[0] == len(options):
            return
        if len(selections) > 1 and len(options) in selections:
            print("Back cannot be combined with other selections.")
            continue
        item_ids = [refreshed.entries[index - 1].item_id for index in selections]
        result = shop_service.sell_many(state, shop_view.shop_id, item_ids)
        _render_shop_events(result.events)
        _render_shop_batch_summary(result, action="Sold")


def _render_shop_stock(shop_view: ShopView) -> None:
    print(f"Gold: {shop_view.gold}")
    if not shop_view.entries:
        print("Stock: (none)")
        return
    print("Stock:")
    for entry in shop_view.entries:
        print(
            f"- {entry.name} ({entry.price}g, Stock: {entry.stock}, Owned: {entry.owned})"
        )


def _render_shop_events(events: List[object]) -> None:
    for event in events:
        if isinstance(event, ShopPurchaseEvent):
            print(
                f"- Bought {event.item_name} x{event.quantity} for {event.total_cost}g "
                f"(Gold: {event.total_gold})."
            )
        elif isinstance(event, ShopSaleEvent):
            print(
                f"- Sold {event.item_name} x{event.quantity} for {event.total_gain}g "
                f"(Gold: {event.total_gold})."
            )
        elif isinstance(event, ShopDebugGoldGrantedEvent):
            print(f"- Added {event.amount} gold (Gold: {event.total_gold}).")
        elif isinstance(event, ShopActionFailedEvent):
            print(f"- {event.message}")


def _render_shop_batch_summary(result: ShopBatchResult, *, action: str) -> None:
    total = result.success_count + result.failure_count
    if total <= 1:
        return
    print(f"- {action} {result.success_count} items. {result.failure_count} failed.")


def _prompt_non_negative_int(label: str) -> int:
    while True:
        raw = input(label).strip()
        try:
            value = int(raw)
        except ValueError:
            print("Please enter a valid integer.")
            continue
        if value < 0:
            print("Please enter zero or a positive number.")
            continue
        return value


def _prompt_index_batch(max_index: int, label: str) -> List[int] | None:
    raw = input(label).strip()
    if not raw:
        print("Please enter at least one selection.")
        return None
    tokens = [token.strip() for token in raw.split(",")]
    if any(token == "" for token in tokens):
        print("Selections cannot be empty.")
        return None
    selections: List[int] = []
    seen: set[int] = set()
    for token in tokens:
        try:
            value = int(token)
        except ValueError:
            print("Selections must be numbers.")
            return None
        if value <= 0:
            print("Selections must be positive.")
            return None
        if value > max_index:
            print("Selection out of range.")
            return None
        if value not in seen:
            selections.append(value)
            seen.add(value)
    return selections


def _play_node_with_auto_resume(
    story_service: StoryService, state: GameState, node_id: str
) -> List[object]:
    events: List[object] = []
    events.extend(story_service.play_node(state, node_id))
    while True:
        if any(isinstance(evt, (BattleRequestedEvent, GameMenuEnteredEvent)) for evt in events):
            return events
        node_view = story_service.get_current_node_view(state)
        if node_view.choices:
            return events
        if not state.pending_story_node_id:
            return events
        events.extend(story_service.resume_pending_flow(state))


def _render_quest_journal(journal: QuestJournalView) -> None:
    if journal.active:
        print("Active Quests:")
        for quest in journal.active:
            status = " (Complete)" if quest.is_completed else ""
            print(f"- {quest.name}{status}")
            for objective in quest.objectives:
                progress = f"{objective.current}/{objective.target}"
                marker = "X" if objective.completed else " "
                print(f"  [{marker}] {objective.label} ({progress})")
    else:
        print("Active Quests: (none)")
    if journal.turned_in:
        print("Turned In:")
        for name in journal.turned_in:
            print(f"- {name}")
    if journal.turn_ins:
        print("Turn-ins:")
        grouped: dict[str, List[QuestTurnInView]] = {}
        for entry in journal.turn_ins:
            key = entry.npc_id or "Unknown"
            grouped.setdefault(key, []).append(entry)
        for npc_id in sorted(grouped.keys()):
            print(f"  {npc_id}:")
            for entry in grouped[npc_id]:
                print(f"    - {entry.name}")


def _order_turn_ins(turn_ins: List[QuestTurnInView], location_view: LocationView) -> List[QuestTurnInView]:
    npc_order = [npc.npc_id for npc in location_view.npcs_present]
    def _sort_key(entry: QuestTurnInView) -> tuple[int, str]:
        if entry.npc_id and entry.npc_id in npc_order:
            return (npc_order.index(entry.npc_id), entry.name)
        return (len(npc_order) + 1, entry.name)

    return sorted(turn_ins, key=_sort_key)


def _filter_turn_ins_for_location(
    turn_ins: List[QuestTurnInView], location_view: LocationView, state: GameState
) -> List[QuestTurnInView]:
    npc_ids = {
        npc.npc_id
        for npc in location_view.npcs_present
        if _npc_is_available(npc.npc_id, location_view.id, state)
    }
    filtered: List[QuestTurnInView] = []
    for entry in turn_ins:
        if entry.npc_id is None:
            continue
        if entry.npc_id in npc_ids:
            filtered.append(entry)
    return filtered


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


def _render_location_debug_snapshot(
    area_service: AreaServiceV2,
    quest_service: QuestService,
    story_service: StoryService,
    state: GameState,
) -> None:
    while True:
        options = [
            "Quest Debug",
            "Conversation Debug",
            "Definition Integrity Check",
            "Back",
        ]
        render_menu("DEBUG Menu", options)
        choice = _prompt_menu_index(len(options))
        if choice == 0:
            _render_quest_debug(quest_service, state)
        elif choice == 1:
            _render_conversation_debug(area_service, story_service, state)
        elif choice == 2:
            _render_definition_integrity(area_service, quest_service, story_service, state)
        else:
            return


def _render_quest_debug(quest_service: QuestService, state: GameState) -> None:
    debug_view = quest_service.build_debug_view(state)
    render_heading("DEBUG: Quests")
    print(f"Definitions loaded: {debug_view.total_definitions}")
    active = ", ".join(debug_view.active_ids) if debug_view.active_ids else "(none)"
    completed = ", ".join(debug_view.completed_ids) if debug_view.completed_ids else "(none)"
    turned_in = ", ".join(debug_view.turned_in_ids) if debug_view.turned_in_ids else "(none)"
    print(f"Active: {active}")
    print(f"Completed: {completed}")
    print(f"Turned in: {turned_in}")
    print("Prereqs:")
    for prereq in debug_view.prereqs:
        status = "READY" if prereq.ready else "BLOCKED"
        missing = ", ".join(prereq.missing_required) if prereq.missing_required else "none"
        blocked = ", ".join(prereq.blocked_by) if prereq.blocked_by else "none"
        print(f"  {prereq.quest_id} [{status}] missing={missing} blocked={blocked}")
    journal = quest_service.build_journal_view(state)
    if journal.turn_ins:
        print("Turn-in targets:")
        for entry in journal.turn_ins:
            npc = entry.npc_id or "unknown"
            print(f"  {entry.quest_id} -> {npc} ({entry.node_id})")


def _render_conversation_debug(
    area_service: AreaServiceV2, story_service: StoryService, state: GameState
) -> None:
    debug_view = area_service.build_debug_view(state)
    location = debug_view.location
    render_heading("DEBUG: Conversations")
    print(f"Current: {location.name} ({location.id})")
    print(f"Tags: {', '.join(location.tags)}")
    if location.npcs_present:
        print("NPCs present:")
        for npc in location.npcs_present:
            talk_ok = story_service.has_node(npc.talk_node_id)
            quest_ok = (
                story_service.has_node(npc.quest_hub_node_id) if npc.quest_hub_node_id else True
            )
            print(
                f"  {npc.npc_id} talk={npc.talk_node_id} ok={talk_ok} "
                f"quest_hub={npc.quest_hub_node_id or 'None'} ok={quest_ok}"
            )
    else:
        print("NPCs present: (none)")


def _render_definition_integrity(
    area_service: AreaServiceV2,
    quest_service: QuestService,
    story_service: StoryService,
    state: GameState,
) -> None:
    render_heading("DEBUG: Definition Integrity")
    print(quest_service.get_definition_summary())
    location = area_service.get_current_location_view(state)
    invalid_nodes: List[str] = []
    for npc in location.npcs_present:
        if not story_service.has_node(npc.talk_node_id):
            invalid_nodes.append(npc.talk_node_id)
        if npc.quest_hub_node_id and not story_service.has_node(npc.quest_hub_node_id):
            invalid_nodes.append(npc.quest_hub_node_id)
    if invalid_nodes:
        print("NPC story node validation: FAILED")
        for node_id in sorted(set(invalid_nodes)):
            print(f"  missing node: {node_id}")
    else:
        print("NPC story node validation: OK")
def _handle_save_request(state: GameState, save_service: SaveService, slot_store: SaveSlotStore) -> None:
    selection = _prompt_slot_choice(slot_store, title="Save Game")
    if selection is None:
        return
    if selection.exists:
        label = _format_slot_label(selection)
        print(f"Slot {selection.slot} already contains: {label}")
        if not _prompt_confirmation("Overwrite this save?"):
            return
    try:
        payload = save_service.serialize(state)
        slot_store.write_slot(selection.slot, payload)
    except OSError as exc:
        print(f"Save failed: {exc}")
        return
    print(f"Saved to Slot {selection.slot}.")


def _prompt_load_slot_action(selection: SlotMetadata, *, allow_load: bool) -> str:
    label = _format_slot_label(selection)
    render_heading(f"Slot {selection.slot}: {label}")
    options = [
        "Load this save",
        "Delete this save",
        "Back",
    ]
    render_menu("Load Options", options)
    choice = _prompt_menu_index(len(options))
    if choice == 0:
        return "load" if allow_load else "invalid"
    if choice == 1:
        return "delete"
    return "back"


def _confirm_delete_slot(selection: SlotMetadata) -> bool:
    return _prompt_confirmation(f"Delete Slot {selection.slot} permanently?")


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


def _run_inventory_flow(
    inventory_service: InventoryService,
    summon_loadout_service: SummonLoadoutService,
    state: GameState,
) -> None:
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
        _run_member_equipment_menu(
            members[choice],
            inventory_service,
            summon_loadout_service,
            state,
        )


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


def _render_summon_loadout_summary(
    state: GameState, summon_loadout_service: SummonLoadoutService, owner_id: str
) -> None:
    print("Summons:")
    known_defs = summon_loadout_service.list_known_summons(state)
    if not known_defs:
        print("  No summons available.")
        return
    known_lookup = {summon.id: summon for summon in known_defs}
    owned_counts = summon_loadout_service.get_owned_summons(state)
    equipped = summon_loadout_service.get_equipped_summons(state, owner_id)
    equipped_counts: dict[str, int] = {}
    for summon_id in equipped:
        equipped_counts[summon_id] = equipped_counts.get(summon_id, 0) + 1
    for summon_id in sorted(known_lookup.keys()):
        summon_def = known_lookup[summon_id]
        owned = owned_counts.get(summon_id, 0)
        equipped_count = equipped_counts.get(summon_id, 0)
        print(
            f"  {summon_def.name} (Bond {summon_def.bond_cost}) - "
            f"Owned {owned}, Equipped {equipped_count}"
        )


def _run_summons_menu(
    summon_loadout_service: SummonLoadoutService, state: GameState, owner_id: str, owner_name: str
) -> None:
    known_defs = summon_loadout_service.list_known_summons(state)
    if not known_defs:
        print("No summons available.")
        return
    while True:
        render_heading(f"{owner_name}'s Summons")
        _render_summon_loadout_summary(state, summon_loadout_service, owner_id)
        options = ["Equip Summon", "Unequip Summon", "Reorder Summons", "Back"]
        render_menu("Summon Options", options)
        choice = _prompt_menu_index(len(options))
        if choice == 0:
            entries = [
                f"{summon.name} (Bond {summon.bond_cost}) [{summon.id}]"
                for summon in known_defs
            ]
            entries.append("Back")
            render_menu("Equip which summon?", entries)
            selection = _prompt_menu_index(len(entries))
            if selection == len(entries) - 1:
                continue
            try:
                summon_loadout_service.equip_summon(state, owner_id, known_defs[selection].id)
            except ValueError as exc:
                print(str(exc))
        elif choice == 1:
            equipped = summon_loadout_service.get_equipped_summons(state, owner_id)
            if not equipped:
                print("No summons equipped.")
                continue
            entries = [f"Slot {idx + 1}: {summon_id}" for idx, summon_id in enumerate(equipped)]
            entries.append("Back")
            render_menu("Unequip which slot?", entries)
            selection = _prompt_menu_index(len(entries))
            if selection == len(entries) - 1:
                continue
            try:
                summon_loadout_service.unequip_summon(state, owner_id, selection)
            except ValueError as exc:
                print(str(exc))
        elif choice == 2:
            equipped = summon_loadout_service.get_equipped_summons(state, owner_id)
            if len(equipped) < 2:
                print("Not enough summons to reorder.")
                continue
            entries = [f"Slot {idx + 1}: {summon_id}" for idx, summon_id in enumerate(equipped)]
            entries.append("Back")
            render_menu("Move which slot?", entries)
            from_choice = _prompt_menu_index(len(entries))
            if from_choice == len(entries) - 1:
                continue
            render_menu("Move to position", entries)
            to_choice = _prompt_menu_index(len(entries))
            if to_choice == len(entries) - 1:
                continue
            try:
                summon_loadout_service.move_equipped_summon(
                    state, owner_id, from_choice, to_choice
                )
            except ValueError as exc:
                print(str(exc))
        else:
            return


def _run_member_equipment_menu(
    member: PartyMemberView,
    inventory_service: InventoryService,
    summon_loadout_service: SummonLoadoutService,
    state: GameState,
) -> None:
    while True:
        weapon_slots, armour_slots = inventory_service.build_member_equipment_view(
            state, member.member_id
        )
        render_heading(f"{member.name}'s Equipment")
        _display_weapon_slots(weapon_slots)
        _display_armour_slots(armour_slots)
        _render_summon_loadout_summary(state, summon_loadout_service, member.member_id)
        options = ["Manage Weapons", "Manage Armour", "View Attributes"]
        options.append("Manage Summons")
        options.append("Back")
        render_menu("Equipment Options", options)
        choice = _prompt_menu_index(len(options))
        if choice == 0:
            _run_weapon_menu(member, inventory_service, state)
        elif choice == 1:
            _run_armour_menu(member, inventory_service, state)
        elif choice == 2:
            _render_member_attributes(member, inventory_service, state)
        elif choice == 3:
            _run_summons_menu(
                summon_loadout_service, state, member.member_id, member.name
            )
        else:
            return


def _render_member_attributes(
    member: PartyMemberView,
    inventory_service: InventoryService,
    state: GameState,
) -> None:
    breakdown = inventory_service.build_attribute_breakdown(state, member.member_id)
    lines = _build_attribute_lines(breakdown)
    _render_boxed_panel(f"{member.name} Attributes", lines)
    if _debug_enabled():
        debug_lines = _build_attribute_debug_lines(breakdown)
        _render_boxed_panel("Debug: Stat Breakdown", debug_lines)


def _get_member_attributes(member: PartyMemberView, state: GameState) -> Attributes:
    if member.is_player and state.player:
        return state.player.attributes
    return state.party_member_attributes.get(member.member_id, Attributes(STR=0, DEX=0, INT=0, VIT=0, BOND=0))


def _build_attribute_lines(breakdown: AttributeScalingBreakdown) -> List[str]:
    attributes = breakdown.attributes
    contributions = breakdown.contributions
    return [
        f"STR: {attributes.STR:>3} (+{contributions.attack:>2} ATK) - increases Attack",
        f"DEX: {attributes.DEX:>3} (+{contributions.speed:>2} INIT) - increases Initiative/Speed",
        f"INT: {attributes.INT:>3} (+{contributions.max_mp:>2} MAX MP) - increases Max MP",
        f"VIT: {attributes.VIT:>3} (+{contributions.max_hp:>2} MAX HP) - increases Max HP",
        f"BOND:{attributes.BOND:>3} - increases summon capacity and scaling",
    ]


def _build_attribute_debug_lines(breakdown: AttributeScalingBreakdown) -> List[str]:
    clamp_notes: List[str] = []
    if breakdown.hp_clamped:
        clamp_notes.append(
            f"HP clamped from {breakdown.hp_before_clamp} to {breakdown.final_stats.max_hp}"
        )
    if breakdown.mp_clamped:
        clamp_notes.append(
            f"MP clamped from {breakdown.mp_before_clamp} to {breakdown.final_stats.max_mp}"
        )
    clamp_line = f"Clamp: {', '.join(clamp_notes)}" if clamp_notes else "Clamp: none"
    return [
        "Base stats:",
        f"  MAX HP {breakdown.base_stats.max_hp} MAX MP {breakdown.base_stats.max_mp}",
        f"  ATK {breakdown.base_stats.attack} DEF {breakdown.base_stats.defense} INIT {breakdown.base_stats.speed}",
        "Contributions:",
        f"  +{breakdown.contributions.max_hp} MAX HP",
        f"  +{breakdown.contributions.max_mp} MAX MP",
        f"  +{breakdown.contributions.attack} ATK",
        f"  +{breakdown.contributions.speed} INIT",
        "Final stats:",
        f"  MAX HP {breakdown.final_stats.max_hp} MAX MP {breakdown.final_stats.max_mp}",
        f"  ATK {breakdown.final_stats.attack} DEF {breakdown.final_stats.defense} INIT {breakdown.final_stats.speed}",
        "Current:",
        f"  HP {breakdown.final_stats.hp}/{breakdown.final_stats.max_hp} MP {breakdown.final_stats.mp}/{breakdown.final_stats.max_mp}",
        clamp_line,
    ]


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
    controller = BattleController(battle_service)
    if _debug_enabled():
        render_heading(f"Battle {battle_state.battle_id}")
    is_first_turn = True

    while not battle_state.is_over:
        view = controller.get_battle_view(battle_state)
        actor_id = battle_state.current_actor_id
        if not actor_id:
            break

        # Always print turn separator and header
        _render_turn_separator()
        actor = _find_combatant(battle_state, actor_id)
        if actor is None:
            break
        _render_turn_header(actor.display_name)

        # Render state panel only at decision points
        if controller.should_render_state_panel(battle_state, state, is_first_turn=is_first_turn):
            _render_battle_state_panel(view, battle_state, active_id=actor_id)

        is_first_turn = False

        # Execute the appropriate turn type
        if controller.is_player_controlled_turn(battle_state, state):
            turn_lines = _run_player_turn(controller, battle_state, state, actor_id)
        elif controller.is_ally_ai_turn(battle_state, state):
            events = controller.run_ally_ai_turn(battle_state, state.rng)
            turn_lines = _format_battle_event_lines(events)
        else:
            events = controller.run_enemy_turn(battle_state, state.rng)
            turn_lines = _format_battle_event_lines(events)

        _render_results_panel(turn_lines)

    if battle_state.victor == "allies":
        reward_events = controller.apply_victory_rewards(battle_state, state)
        _render_battle_events(reward_events)

    return battle_state.victor == "allies"


def _run_player_turn(
    controller: BattleController, battle_state: BattleState, state: GameState, actor_id: str
) -> List[str]:
    """Handle the player-controlled turn. Only re-renders action menu on invalid input, not the state panel."""
    turn_lines: List[str] = []
    actions = controller.get_available_actions(battle_state, state)
    battle_items: List[BattleInventoryItem] = actions.get("items", [])

    while True:
        action_type = _prompt_battle_action(
            can_talk=actions["can_talk"],
            can_use_skill=actions["can_use_skill"],
            can_use_item=actions["can_use_item"],
        )

        if action_type == "attack":
            estimator = lambda enemy: controller.estimate_damage(
                battle_state, actor_id, enemy.instance_id
            )
            target = _prompt_battle_target(
                battle_state, damage_estimator=estimator, state=state, controller=controller
            )
            action = BattleAction(action_type="attack", target_id=target.instance_id)
            events = controller.apply_player_action(battle_state, state, action)
            turn_lines.extend(_format_battle_event_lines(events))
            return turn_lines

        if action_type == "skill":
            skill = _prompt_skill_choice(
                actions["available_skills"], battle_state, controller, actor_id, state
            )
            damage_estimator: Callable[[Combatant], int] | None = None
            if skill.effect_type == "damage":
                damage_estimator = lambda enemy: controller.estimate_damage(
                    battle_state, actor_id, enemy.instance_id, bonus_power=skill.base_power
                )
            target_ids = _prompt_skill_targets(
                skill, battle_state, damage_estimator=damage_estimator, state=state, controller=controller
            )
            action = BattleAction(action_type="skill", skill_id=skill.id, target_ids=target_ids)
            events = controller.apply_player_action(battle_state, state, action)
            failure_event = next((evt for evt in events if isinstance(evt, SkillFailedEvent)), None)
            if failure_event:
                reason = _format_skill_failure_reason(failure_event.reason)
                turn_lines.append(f"- Cannot use {skill.name} ({reason}).")
                continue
            turn_lines.extend(_format_battle_event_lines(events))
            return turn_lines

        if action_type == "item":
            item_entry = _prompt_item_choice(battle_items)
            if item_entry is None:
                continue
            target_id = _prompt_item_target(battle_state, actor_id, item_entry.targeting)
            if target_id is None:
                continue
            action = BattleAction(action_type="item", item_id=item_entry.item_id, target_id=target_id)
            events = controller.apply_player_action(battle_state, state, action)
            turn_lines.extend(_format_battle_event_lines(events))
            return turn_lines

        # Talk action
        speaker_member_id = _prompt_party_member_choice(state, boxed=True)
        speaker_combatant_id = f"party_{speaker_member_id}"
        action = BattleAction(action_type="talk", speaker_id=speaker_combatant_id)
        events = controller.apply_player_action(battle_state, state, action)
        turn_lines.extend(_format_battle_event_lines(events))
        return turn_lines


def _format_skill_failure_reason(reason: str) -> str:
    if reason == "insufficient_mp":
        return "insufficient MP"
    return reason.replace("_", " ")


def _format_damage_preview(value: int | None, *, suffix: str = "", base_power: int | None = None, is_known: bool = False) -> str:
    """
    Format damage preview based on debug mode and knowledge.
    
    Args:
        value: Estimated damage (when known or debug)
        suffix: Optional suffix like " each"
        base_power: Skill base power (fallback for unknown enemies)
        is_known: Whether party has knowledge of the enemy
    
    Returns:
        Formatted preview string
    """
    if _debug_enabled():
        if value is None:
            return ""
        return f"Projected: {value}{suffix}"
    
    if is_known and value is not None:
        return f"Projected: {value}{suffix}"
    
    # Non-debug, no knowledge: show base power only
    if base_power is not None:
        return f"Power: {base_power}{suffix}"
    
    return ""


def _build_skill_preview(
    skill: SkillDef,
    battle_state: BattleState,
    controller: BattleController,
    actor_id: str,
    state: GameState,
) -> str:
    """Build preview string for a skill, respecting knowledge and debug modes."""
    if skill.effect_type != "damage":
        return ""
    
    suffix = " each" if skill.target_mode == "multi_enemy" else ""
    
    # Check if we can show projected values
    can_project = _debug_enabled()
    if not can_project:
        # Check if party has knowledge of any living enemy
        living_enemies = [enemy for enemy in battle_state.enemies if enemy.is_alive]
        if living_enemies:
            # Check knowledge for the first enemy as representative
            enemy = living_enemies[0]
            can_project = controller.has_knowledge_of_enemy(state, enemy.tags)
    
    if not can_project:
        # Show base power only
        return _format_damage_preview(
            None, suffix=suffix, base_power=skill.base_power, is_known=False
        )
    
    # Can show projected damage
    if skill.target_mode == "self":
        estimate = controller.estimate_damage(
            battle_state, actor_id, actor_id, bonus_power=skill.base_power
        )
        return _format_damage_preview(estimate, suffix="", base_power=skill.base_power, is_known=True)
    
    if skill.target_mode in {"single_enemy", "multi_enemy"}:
        living_enemies = [enemy for enemy in battle_state.enemies if enemy.is_alive]
        if not living_enemies:
            return ""
        estimates = [
            controller.estimate_damage(
                battle_state, actor_id, enemy.instance_id, bonus_power=skill.base_power
            )
            for enemy in living_enemies
        ]
        if len(set(estimates)) == 1:
            return _format_damage_preview(
                estimates[0], suffix=suffix, base_power=skill.base_power, is_known=True
            )
    return ""


def _format_battle_event_lines(events: List[BattleEvent]) -> List[str]:
    """Canonical battle event formatter. All battle event rendering must use this function."""
    lines: List[str] = []
    loot_order: List[str] = []
    loot_totals: dict[str, tuple[str, int]] = {}
    for event in events:
        if isinstance(event, SummonAutoSpawnDebugEvent):
            continue
        if isinstance(event, LootAcquiredEvent):
            if event.item_id not in loot_totals:
                loot_order.append(event.item_id)
                loot_totals[event.item_id] = (event.item_name, 0)
            name, qty = loot_totals[event.item_id]
            loot_totals[event.item_id] = (name, qty + event.quantity)
            continue
        if isinstance(event, BattleStartedEvent):
            lines.append(f"- Battle started against {', '.join(event.enemy_names)}.")
        elif isinstance(event, AttackResolvedEvent):
            lines.append(f"- {event.attacker_name} hits {event.target_name} for {event.damage} damage.")
        elif isinstance(event, CombatantDefeatedEvent):
            lines.append(f"- {event.combatant_name} is defeated.")
        elif isinstance(event, PartyTalkEvent):
            lines.append(f"- {event.text}")
        elif isinstance(event, SummonSpawnedEvent):
            lines.append(f"- {event.summon_name} is summoned.")
        elif isinstance(event, SkillUsedEvent):
            lines.append(
                f"- {event.attacker_name} uses {event.skill_name} on {event.target_name} for {event.damage} damage."
            )
        elif isinstance(event, GuardAppliedEvent):
            lines.append(f"- {event.combatant_name} braces, reducing the next hit by {event.amount}.")
        elif isinstance(event, SkillFailedEvent):
            lines.append(f"- {event.combatant_name} cannot use that skill ({event.reason}).")
        elif isinstance(event, ItemUsedEvent):
            if event.result_text:
                lines.append(f"- {event.result_text}")
            else:
                deltas: List[str] = []
                if event.hp_delta:
                    deltas.append(f"+{event.hp_delta} HP")
                if event.mp_delta:
                    deltas.append(f"+{event.mp_delta} MP")
                if event.energy_delta:
                    deltas.append(f"+{event.energy_delta} Energy")
                delta_text = ", ".join(deltas) if deltas else "had no effect"
                lines.append(
                    f"- {event.user_name} uses {event.item_name} on {event.target_name}: {delta_text}."
                )
        elif isinstance(event, DebuffAppliedEvent):
            if event.debuff_type == "attack_down":
                detail = f"ATK -{event.amount}"
            else:
                detail = f"DEF -{event.amount}"
            lines.append(f"- {event.target_name} suffers {detail} (until next action).")
        elif isinstance(event, DebuffExpiredEvent):
            label = "ATK" if event.debuff_type == "attack_down" else "DEF"
            lines.append(f"- {event.target_name}'s {label} penalty wore off.")
        elif isinstance(event, ItemUsedEvent):
            deltas: List[str] = []
            if event.hp_delta:
                deltas.append(f"+{event.hp_delta} HP")
            if event.mp_delta:
                deltas.append(f"+{event.mp_delta} MP")
            if event.energy_delta:
                deltas.append(f"+{event.energy_delta} Energy")
            delta_text = ", ".join(deltas) if deltas else "had no effect"
            lines.append(
                f"- {event.user_name} uses {event.item_name} on {event.target_name}: {delta_text}."
            )
        elif isinstance(event, BattleResolvedEvent):
            lines.append(f"- Battle resolved. Victor: {event.victor.title()}")
        elif isinstance(event, BattleGoldRewardEvent):
            lines.append(f"- Gained {event.amount} gold (Total: {event.total_gold}).")
        elif isinstance(event, BattleExpRewardEvent):
            lines.append(f"- {event.member_name} gains {event.amount} EXP (Level {event.new_level}).")
        elif isinstance(event, BattleLevelUpEvent):
            lines.append(f"- {event.member_name} reached Level {event.new_level}!")
        elif isinstance(event, BattleRewardsHeaderEvent):
            pass
        else:
            lines.append(f"- {event}")
    for item_id in loot_order:
        item_name, quantity = loot_totals[item_id]
        lines.append(f"- Loot: {item_name} x{quantity}")
    return lines


def _prompt_battle_action(*, can_talk: bool, can_use_skill: bool, can_use_item: bool) -> str:
    options: List[tuple[str, str]] = [("attack", "Basic Attack")]
    if can_use_skill:
        options.append(("skill", "Use Skill"))
    if can_use_item:
        options.append(("item", "Use Item"))
    if can_talk:
        options.append(("talk", "Party Talk"))
    while True:
        lines = [f"{idx + 1:>2}) {label}" for idx, (_, label) in enumerate(options)]
        _render_boxed_panel("Actions", lines)
        choice = input("Choose action: ").strip()
        try:
            index = int(choice) - 1
        except ValueError:
            print("Invalid selection.")
            continue
        if 0 <= index < len(options):
            return options[index][0]
        print("Invalid selection.")


def _prompt_skill_choice(
    skills: List[SkillDef],
    battle_state: BattleState,
    controller: BattleController,
    actor_id: str,
    state: GameState,
) -> SkillDef:
    while True:
        lines = []
        for idx, skill in enumerate(skills, start=1):
            target_desc = {
                "single_enemy": "Single Enemy",
                "multi_enemy": f"Up to {skill.max_targets} Enemies",
                "self": "Self",
            }[skill.target_mode]
            preview = _build_skill_preview(
                skill, battle_state, controller, actor_id, state
            )
            line = f"{idx:>2}) {skill.name} (MP {skill.mp_cost}, {target_desc})"
            if preview:
                line = f"{line} - {preview}"
            lines.append(line)
            if skill.description:
                desc_width = _BATTLE_UI_WIDTH - 6  # account for box padding and indent
                desc_lines = wrap_text_for_box(
                    skill.description, desc_width, indent_continuation=False
                )
                lines.extend([f"  {desc_line}" for desc_line in desc_lines])
        _render_boxed_panel("Skills", lines)
        choice = input("Select skill: ").strip()
        try:
            index = int(choice) - 1
        except ValueError:
            print("Invalid selection.")
            continue
        if 0 <= index < len(skills):
            return skills[index]
        print("Invalid selection.")


def _prompt_skill_targets(
    skill: SkillDef,
    battle_state: BattleState,
    *,
    damage_estimator: Callable[[Combatant], int] | None = None,
    state: GameState | None = None,
    controller: BattleController | None = None,
) -> List[str]:
    if skill.target_mode == "self":
        return []
    living_enemies = [enemy for enemy in battle_state.enemies if enemy.is_alive]
    if not living_enemies:
        raise ValueError("No valid targets.")
    if skill.target_mode == "single_enemy":
        target = _prompt_battle_target(
            battle_state, damage_estimator=damage_estimator, state=state, controller=controller
        )
        return [target.instance_id]
    return _prompt_multi_enemy_targets(
        battle_state, skill.max_targets, damage_estimator=damage_estimator,
        state=state, controller=controller
    )


def _prompt_item_choice(items: List[BattleInventoryItem]) -> BattleInventoryItem | None:
    if not items:
        print("No consumable items are available.")
        return None
    while True:
        lines: List[str] = []
        for idx, entry in enumerate(items, start=1):
            targeting_label = _format_item_targeting(entry.targeting)
            note = ""
            if entry.targeting not in {"self", "ally", "enemy"}:
                note = " - Cannot be used in battle yet"
            lines.append(f"{idx:>2}) {entry.item_name} x{entry.quantity} ({targeting_label}){note}")
        _render_boxed_panel("Items", lines)
        raw = input("Select item (blank to cancel): ").strip()
        if not raw:
            return None
        try:
            index = int(raw) - 1
        except ValueError:
            print("Invalid selection.")
            continue
        if 0 <= index < len(items):
            entry = items[index]
            if entry.targeting not in {"self", "ally", "enemy"}:
                print(f"{entry.item_name} cannot be used that way yet.")
                continue
            return entry
        print("Invalid selection.")


def _prompt_item_target(battle_state: BattleState, actor_id: str, targeting: str) -> str | None:
    actor = _find_combatant(battle_state, actor_id)
    if actor is None:
        return None
    if targeting == "enemy":
        target = _prompt_battle_target(battle_state)
        return target.instance_id

    living_allies = [ally for ally in battle_state.allies if ally.is_alive]
    selectable = [actor] if targeting == "self" else living_allies
    if not selectable:
        print("No valid targets available.")
        return None

    while True:
        lines: List[str] = []
        for idx, ally in enumerate(selectable, start=1):
            label = "Self" if ally.instance_id == actor_id else ally.display_name
            lines.append(f"{idx:>2}) {label} ({ally.stats.hp}/{ally.stats.max_hp} HP)")
        _render_boxed_panel("Item Target", lines)
        raw = input("Target # (blank to cancel): ").strip()
        if not raw:
            return None
        try:
            index = int(raw) - 1
        except ValueError:
            print("Enter a number.")
            continue
        if 0 <= index < len(selectable):
            return selectable[index].instance_id
        print("Invalid target.")


def _format_item_targeting(targeting: str) -> str:
    mapping = {
        "self": "Self",
        "ally": "Ally",
        "enemy": "Enemy",
        "any": "Any Target",
    }
    return mapping.get(targeting, targeting.title())


def _prompt_multi_enemy_targets(
    battle_state: BattleState,
    max_targets: int,
    *,
    damage_estimator: Callable[[Combatant], int] | None = None,
    state: GameState | None = None,
    controller: BattleController | None = None,
) -> List[str]:
    living_enemies = [enemy for enemy in battle_state.enemies if enemy.is_alive]
    while True:
        lines = []
        for idx, enemy in enumerate(living_enemies):
            line = f"{idx + 1:>2}) {enemy.display_name}"
            if damage_estimator:
                estimate = damage_estimator(enemy)
                # Determine if we can show projected damage
                can_project = _debug_enabled()
                if not can_project and state and controller:
                    can_project = controller.has_knowledge_of_enemy(state, enemy.tags)
                
                if can_project:
                    line = f"{line} - Projected: {estimate}"
                # If not can_project, don't show preview for multi-target
            lines.append(line)
        _render_boxed_panel("Select Targets", lines)
        raw = input(f"Choose up to {max_targets} targets (comma separated): ").strip()
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


def _prompt_battle_target(
    battle_state: BattleState,
    exclude_ids: Sequence[str] | None = None,
    *,
    damage_estimator: Callable[[Combatant], int] | None = None,
    state: GameState | None = None,
    controller: BattleController | None = None,
) -> Combatant:
    """Prompt for a battle target with optional damage preview."""
    exclude_set = set(exclude_ids or [])
    living_enemies = [enemy for enemy in battle_state.enemies if enemy.is_alive and enemy.instance_id not in exclude_set]
    while True:
        lines = []
        for idx, enemy in enumerate(living_enemies):
            line = f"{idx + 1:>2}) {enemy.display_name}"
            if damage_estimator:
                estimate = damage_estimator(enemy)
                # Determine if we can show projected damage
                can_project = _debug_enabled()
                if not can_project and state and controller:
                    can_project = controller.has_knowledge_of_enemy(state, enemy.tags)
                
                if can_project:
                    line = f"{line} - Projected: {estimate}"
                # If not can_project, don't show any preview for basic attacks in target list
            lines.append(line)
        _render_boxed_panel("Target", lines)
        raw = input("Target #: ").strip()
        try:
            index = int(raw) - 1
        except ValueError:
            print("Enter a number.")
            continue
        if 0 <= index < len(living_enemies):
            return living_enemies[index]
        print("Invalid target.")
        _render_boxed_panel("Target", lines)
        raw = input("Target #: ").strip()
        try:
            index = int(raw) - 1
        except ValueError:
            print("Enter a number.")
            continue
        if 0 <= index < len(living_enemies):
            return living_enemies[index]
        print("Invalid target.")


def _prompt_party_member_choice(state: GameState, prompt_title: str = "Party Talk", *, boxed: bool = False) -> str:
    while True:
        if boxed:
            lines = [f"{idx + 1:>2}) {member_id.title()}" for idx, member_id in enumerate(state.party_members)]
            _render_boxed_panel(prompt_title, lines)
        else:
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
    """Render battle events with appropriate headers. Uses canonical event formatter."""
    if not events:
        return
    if any(isinstance(event, BattleRewardsHeaderEvent) for event in events):
        _render_reward_panels(events)
        return
    standard_header_printed = False
    for event in events:
        if not standard_header_printed:
            render_events_header()
            standard_header_printed = True
        if _debug_enabled() and isinstance(event, BattleStartedEvent) and event.battle_level is not None:
            source_label = event.level_source or "default"
            source_value = (
                f"={event.level_source_value}" if event.level_source_value is not None else ""
            )
            location = f", location={event.location_id}" if event.location_id else ""
            floor = f", floor={event.floor_id}" if event.floor_id else ""
            lines = [
                f"Battle level: {event.battle_level} (source: {source_label}{source_value}{location}{floor})",
                (
                    "Per level: "
                    f"+{event.scaling_hp_per_level} HP, "
                    f"+{event.scaling_attack_per_level} ATK, "
                    f"+{event.scaling_defense_per_level} DEF, "
                    f"+{event.scaling_speed_per_level} INIT"
                ),
            ]
            _render_boxed_panel("Debug: Enemy Scaling", lines)
        if _debug_enabled() and isinstance(event, SummonSpawnedEvent):
            base_stats = event.base_stats
            scaled_stats = event.scaled_stats
            if base_stats and scaled_stats:
                lines = [
                    f"{event.summon_name} ({event.summon_id})",
                    f"Owner BOND: {event.owner_bond}",
                    (
                        f"Base HP {base_stats.max_hp} ATK {base_stats.attack} "
                        f"DEF {base_stats.defense} INIT {base_stats.speed}"
                    ),
                    (
                        f"Scaled HP {scaled_stats.max_hp} ATK {scaled_stats.attack} "
                        f"DEF {scaled_stats.defense} INIT {scaled_stats.speed}"
                    ),
                ]
                _render_boxed_panel("Debug: Summon Scaling", lines)
        if _debug_enabled() and isinstance(event, SummonAutoSpawnDebugEvent):
            lines = [
                f"BOND capacity: {event.bond_capacity}",
                f"Equipped: {event.equipped_summons}",
            ]
            for summon_id, cost, spawned in event.decisions:
                status = "spawned" if spawned else "blocked"
                lines.append(f"{summon_id}: cost {cost} ({status})")
            _render_boxed_panel("Debug: Summon Auto-Spawn", lines)
        # Use canonical formatter for consistency
        formatted = _format_battle_event_lines([event])
        for line in formatted:
            print(line)


def _find_combatant(battle_state: BattleState, combatant_id: str | None) -> Combatant | None:
    if combatant_id is None:
        return None
    for combatant in battle_state.allies + battle_state.enemies:
        if combatant.instance_id == combatant_id:
            return combatant
    return None


def _render_reward_panels(events: List[BattleEvent]) -> None:
    gold_events = [evt for evt in events if isinstance(evt, BattleGoldRewardEvent)]
    exp_events = [evt for evt in events if isinstance(evt, BattleExpRewardEvent)]
    level_events = [evt for evt in events if isinstance(evt, BattleLevelUpEvent)]
    loot_events = [evt for evt in events if isinstance(evt, LootAcquiredEvent)]

    reward_lines = _format_battle_event_lines([*gold_events, *exp_events])
    if reward_lines:
        _render_boxed_panel("Rewards", reward_lines)

    level_lines = _format_battle_event_lines(level_events)
    if level_lines:
        _render_boxed_panel("Level Ups", level_lines)

    loot_lines = _format_battle_event_lines(loot_events)
    if loot_lines:
        _render_boxed_panel("Loot", loot_lines)


def _format_enemy_hp_display(enemy: BattleCombatantView, *, debug_enabled: bool) -> str:
    """Format enemy HP display with optional debug info (HP + DEF)."""
    if not enemy.is_alive:
        return "DOWN"
    if not debug_enabled:
        return enemy.hp_display
    # Debug mode: show HP and defense (ultra-compact: [15/15|D2])
    return f"{enemy.hp_display}[{enemy.current_hp}/{enemy.max_hp}|D{enemy.defense}]"


def _format_enemy_debuff_badges(combatant: Combatant | None) -> str:
    if combatant is None or not getattr(combatant, "debuffs", None) or not combatant.is_alive:
        return ""
    badges: List[str] = []
    for debuff in combatant.debuffs:
        label = "ATK" if debuff.debuff_type == "attack_down" else "DEF"
        badges.append(f"{label}-{debuff.amount}")
    if not badges:
        return ""
    return f"[{'/'.join(badges)}]"


def _format_battle_state_ally_line(
    *,
    marker: str,
    order_prefix: str,
    name: str,
    hp_display: str,
    mp_text: str,
    width: int,
) -> str:
    suffix = f"HP {hp_display} MP {mp_text}"
    prefix = f"{marker} {order_prefix}"
    line_prefix = prefix
    space = " "
    if len(line_prefix) + len(space) + len(suffix) > width:
        line_prefix = ""
        space = ""
    available = width - len(line_prefix) - len(space) - len(suffix)
    if available < 0:
        available = 0
    name_part = name[:available]
    return f"{line_prefix}{name_part}{space}{suffix}".strip()


def _build_enemy_scaling_lines(combatant: Combatant | None, width: int) -> List[str]:
    if combatant is None or combatant.base_stats is None:
        return []
    base = combatant.base_stats
    stats = combatant.stats
    hp_delta = stats.max_hp - base.max_hp
    atk_delta = stats.attack - base.attack
    def_delta = stats.defense - base.defense
    speed_delta = stats.speed - base.speed
    details = (
        f"HP {stats.max_hp} (Base {base.max_hp} +{hp_delta}) "
        f"ATK {stats.attack} (Base {base.attack} +{atk_delta}) "
        f"DEF {stats.defense} (Base {base.defense} +{def_delta}) "
        f"INIT {stats.speed} (Base {base.speed} +{speed_delta})"
    )
    wrapped = _wrap_text_to_width(details, width - 2)
    if len(wrapped) > 2:
        wrapped = wrapped[:2]
    return [f"  {line}" for line in wrapped]


def _render_debug_enemy_debuffs(battle_state: BattleState) -> None:
    if not _debug_enabled():
        return
    lines: List[str] = []
    for enemy in battle_state.enemies:
        if not enemy.debuffs:
            continue
        parts: List[str] = []
        for debuff in enemy.debuffs:
            label = "ATK" if debuff.debuff_type == "attack_down" else "DEF"
            parts.append(f"{label}-{debuff.amount} (round {debuff.expires_at_round})")
        if parts:
            lines.append(f"{enemy.display_name}: {', '.join(parts)}")
    if lines:
        _render_boxed_panel("Debug Debuffs", lines)


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



