from tbg.core.rng import RNG
from tbg.domain.state import GameState
from tbg.presentation.cli import app
from tbg.presentation.cli.app import (
    _MENU_RESELECT,
    _build_camp_menu_entries,
    _build_town_menu_entries,
    _filter_location_npcs,
    _information_menu_options,
    _main_menu_options,
    _print_main_menu_header,
    _print_startup_banner,
    _prompt_index_batch,
    _play_node_with_auto_resume,
    _run_information_menu,
    _run_shop_menu,
    _show_placeholder_screen,
    _warp_to_checkpoint_location,
)
from tbg.services.shop_service import ShopSummaryView, ShopView
from tbg.services.area_service_v2 import AreaServiceV2
from tbg.data.repositories import FloorsRepository, LocationsRepository
from tbg.data.repositories import (
    ArmourRepository,
    ClassesRepository,
    SummonsRepository,
    WeaponsRepository,
    ItemsRepository,
    PartyMembersRepository,
    QuestsRepository,
    StoryRepository,
)
from tbg.services.summon_loadout_service import SummonLoadoutService
from tbg.services.factories import create_player_from_class_id
from tbg.services.story_service import GameMenuEnteredEvent
from tbg.services.inventory_service import InventoryService
from tbg.services.story_service import StoryService
from tbg.services.quest_service import QuestService


def _camp_state() -> GameState:
    return GameState(seed=1, rng=RNG(1), mode="camp_menu", current_node_id="class_select")


def _summon_service() -> SummonLoadoutService:
    weapons_repo = WeaponsRepository()
    armour_repo = ArmourRepository()
    summons_repo = SummonsRepository()
    classes_repo = ClassesRepository(
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        summons_repo=summons_repo,
    )
    return SummonLoadoutService(classes_repo=classes_repo, summons_repo=summons_repo)


def _build_story_service() -> StoryService:
    weapons_repo = WeaponsRepository()
    armour_repo = ArmourRepository()
    party_repo = PartyMembersRepository()
    inventory_service = InventoryService(
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        party_members_repo=party_repo,
    )
    items_repo = ItemsRepository()
    floors_repo = FloorsRepository()
    locations_repo = LocationsRepository(floors_repo=floors_repo)
    story_repo = StoryRepository()
    quests_repo = QuestsRepository(
        items_repo=items_repo,
        locations_repo=locations_repo,
        story_repo=story_repo,
    )
    quest_service = QuestService(
        quests_repo=quests_repo,
        items_repo=items_repo,
        locations_repo=locations_repo,
        party_members_repo=party_repo,
    )
    return StoryService(
        story_repo=story_repo,
        classes_repo=ClassesRepository(weapons_repo=weapons_repo, armour_repo=armour_repo),
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        party_members_repo=party_repo,
        inventory_service=inventory_service,
        quest_service=quest_service,
    )


def test_camp_menu_includes_save_option() -> None:
    state = _camp_state()
    entries = _build_camp_menu_entries(state, _summon_service())
    labels = [label for label, _ in entries]
    assert "Save Game" in labels
    assert "Travel" in labels
    assert all(label != "Load Game" for label in labels)


def test_town_menu_includes_converse_and_quests() -> None:
    state = _camp_state()
    entries = _build_town_menu_entries(state, _summon_service())
    labels = [label for label, _ in entries]
    assert "Converse" in labels
    assert "Quests" in labels
    assert "Shops" in labels
    assert "Summons" not in labels


def test_cerel_converse_requires_return_flag() -> None:
    floors_repo = FloorsRepository()
    locations_repo = LocationsRepository(floors_repo=floors_repo)
    area_service = AreaServiceV2(floors_repo=floors_repo, locations_repo=locations_repo)
    state = _camp_state()
    area_service.initialize_state(state)
    area_service.force_set_location(state, "threshold_inn")
    location_view = area_service.get_current_location_view(state)

    npcs = _filter_location_npcs(location_view, state)
    assert [npc.npc_id for npc in npcs] == ["dana"]

    story_service = _build_story_service()
    story_service.play_node(state, "inn_arrival")
    npcs = _filter_location_npcs(location_view, state)
    assert [npc.npc_id for npc in npcs] == ["dana"]
    assert state.flags.get("flag_sq_cerel_rampager_offered") is not True

    story_service.play_node(state, "goblin_cave_entrance_intro")
    npcs = _filter_location_npcs(location_view, state)
    assert "cerel" in [npc.npc_id for npc in npcs]
    story_service.play_node(state, "cerel_goblin_escalation_quest_offer")
    assert state.flags.get("flag_sq_cerel_rampager_offered") is True


def test_camp_menu_does_not_include_summons() -> None:
    state = _camp_state()
    weapons_repo = WeaponsRepository()
    armour_repo = ArmourRepository()
    summons_repo = SummonsRepository()
    classes_repo = ClassesRepository(
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        summons_repo=summons_repo,
    )
    state.player = create_player_from_class_id(
        class_id="beastmaster",
        name="Hero",
        classes_repo=classes_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        rng=state.rng,
    )
    summon_service = SummonLoadoutService(classes_repo=classes_repo, summons_repo=summons_repo)

    entries = _build_camp_menu_entries(state, summon_service)
    labels = [label for label, _ in entries]
    assert "Summons" not in labels


def test_main_menu_includes_load_but_not_save() -> None:
    options = _main_menu_options()
    labels = [label for label, _ in options]
    assert labels == [
        "New Game",
        "Load Game",
        "Options",
        "Information",
        "Quit",
    ]
    assert "Save Game" not in labels


def test_startup_banner_includes_name_and_version(capsys) -> None:
    _print_startup_banner()
    output = capsys.readouterr().out
    assert "Echoes of the Cycle" in output
    assert "v0.0.1" in output
    assert "Demo" in output


def test_main_menu_header_includes_name_and_version(capsys) -> None:
    _print_main_menu_header()
    output = capsys.readouterr().out
    assert "Echoes of the Cycle" in output
    assert "v0.0.1" in output


def test_placeholder_screens_return_safely(monkeypatch, capsys) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "")
    _show_placeholder_screen("Options", ["Placeholder"])
    _show_placeholder_screen("Information", ["Placeholder"])
    output = capsys.readouterr().out
    assert "Options" in output
    assert "Information" in output


def test_information_menu_has_required_entries() -> None:
    labels = [label for label, _ in _information_menu_options()]
    assert labels == [
        "About This Demo",
        "Available Content",
        "Locked / Future Content",
        "How to Progress",
        "Save & Replay Expectations",
        "Credits & Version",
        "Back",
    ]


def test_information_menu_sections_render_and_return(monkeypatch, capsys) -> None:
    # Choose each section, then Back.
    selections = iter(["1", "", "2", "", "3", "", "4", "", "5", "", "6", "", "7"])
    monkeypatch.setattr("builtins.input", lambda _: next(selections))
    _run_information_menu()
    output = capsys.readouterr().out
    assert "About This Demo" in output
    assert "Available Content" in output
    assert "Locked / Future Content" in output
    assert "How to Progress" in output
    assert "Save & Replay Expectations" in output
    assert "Credits & Version" in output


def test_camp_menu_debug_option_hidden_without_flag(monkeypatch) -> None:
    monkeypatch.delenv("TBG_DEBUG", raising=False)
    state = _camp_state()
    entries = _build_camp_menu_entries(state, _summon_service())
    labels = [label for label, _ in entries]
    assert all("Location Debug" not in label for label in labels)


def test_town_menu_debug_option_hidden_without_flag(monkeypatch) -> None:
    monkeypatch.delenv("TBG_DEBUG", raising=False)
    state = _camp_state()
    entries = _build_town_menu_entries(state, _summon_service())
    labels = [label for label, _ in entries]
    assert all("Location Debug" not in label for label in labels)


def test_camp_menu_debug_option_visible_with_flag(monkeypatch) -> None:
    monkeypatch.setenv("TBG_DEBUG", "1")
    state = _camp_state()
    entries = _build_camp_menu_entries(state, _summon_service())
    labels = [label for label, _ in entries]
    assert any("Location Debug" in label for label in labels)


def test_town_menu_debug_option_visible_with_flag(monkeypatch) -> None:
    monkeypatch.setenv("TBG_DEBUG", "1")
    state = _camp_state()
    entries = _build_town_menu_entries(state, _summon_service())
    labels = [label for label, _ in entries]
    assert any("Location Debug" in label for label in labels)


def test_interlude_reselects_menu_after_travel(monkeypatch) -> None:
    state = _camp_state()

    class _StubAreaService:
        def __init__(self):
            self._calls = 0

        def get_current_location_view(self, _state):
            self._calls += 1
            tags = ("town",) if self._calls == 1 else ("plains",)
            return type("LocationViewStub", (), {"tags": tags})()

    area_service = _StubAreaService()

    def fake_town_menu(*args, **kwargs):
        return _MENU_RESELECT

    def fake_camp_menu(*args, **kwargs):
        return []

    monkeypatch.setattr(app, "_run_town_menu", fake_town_menu)
    monkeypatch.setattr(app, "_run_camp_menu", fake_camp_menu)

    follow_up = app._run_post_battle_interlude(
        message="",
        story_service=object(),
        inventory_service=object(),
        quest_service=object(),
        shop_service=object(),
        summon_loadout_service=_summon_service(),
        attribute_service=object(),
        state=state,
        save_service=object(),
        slot_store=object(),
        battle_service=object(),
        area_service=area_service,
    )

    assert follow_up == []


def test_town_menu_shops_dispatch(monkeypatch) -> None:
    state = _camp_state()
    calls = {"count": 0}

    def fake_handle_shop_menu(shop_service, area_service, state_arg):
        del shop_service, area_service, state_arg
        calls["count"] += 1

    def fake_menu_entries(_state, _summon_service):
        return [("Shops", "shops"), ("Quit Game", "quit")]

    choices = iter([0, 1])

    monkeypatch.setattr(app, "_handle_shop_menu", fake_handle_shop_menu)
    monkeypatch.setattr(app, "_build_town_menu_entries", fake_menu_entries)
    monkeypatch.setattr(app, "_prompt_menu_index", lambda _count: next(choices))
    monkeypatch.setattr(app, "render_menu", lambda *args, **kwargs: None)

    result = app._run_town_menu(
        story_service=object(),
        inventory_service=object(),
        quest_service=object(),
        shop_service=object(),
        summon_loadout_service=_summon_service(),
        attribute_service=object(),
        state=state,
        save_service=object(),
        slot_store=object(),
        battle_service=object(),
        area_service=object(),
    )

    assert result is None
    assert calls["count"] == 1


def test_shop_menu_debug_option_visibility(monkeypatch) -> None:
    state = _camp_state()
    shop_summary = ShopSummaryView(shop_id="shop", name="Shop", shop_type="item")
    shop_view = ShopView(shop_id="shop", name="Shop", shop_type="item", gold=10, entries=[])
    captured = {"options": []}

    def fake_build_shop_view(_state, _location_id, _shop_id):
        return shop_view

    def fake_render_menu(_title, options):
        captured["options"] = options

    class _StubShopService:
        def build_shop_view(self, state, location_id, shop_id):
            return fake_build_shop_view(state, location_id, shop_id)

    monkeypatch.setattr(app, "render_heading", lambda *args, **kwargs: None)
    monkeypatch.setattr(app, "render_menu", fake_render_menu)
    monkeypatch.setattr(app, "_prompt_menu_index", lambda _count: 2)
    monkeypatch.delenv("TBG_DEBUG", raising=False)

    _run_shop_menu(_StubShopService(), state, "threshold_inn", shop_summary)
    assert "Give Gold (DEBUG)" not in captured["options"]

    monkeypatch.setenv("TBG_DEBUG", "1")
    _run_shop_menu(_StubShopService(), state, "threshold_inn", shop_summary)
    assert "Give Gold (DEBUG)" in captured["options"]


def test_town_menu_allocate_attributes_flow(monkeypatch) -> None:
    from tbg.data.repositories import ArmourRepository, ClassesRepository, PartyMembersRepository, WeaponsRepository
    from tbg.services.attribute_allocation_service import AttributeAllocationService
    from tbg.services.factories import create_player_from_class_id
    from tbg.services.inventory_service import InventoryService
    from tbg.services.summon_loadout_service import SummonLoadoutService
    from tbg.data.repositories import SummonsRepository

    state = _camp_state()
    weapons_repo = WeaponsRepository()
    armour_repo = ArmourRepository()
    summons_repo = SummonsRepository()
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
    summon_service = SummonLoadoutService(classes_repo=classes_repo, summons_repo=summons_repo)
    attribute_service = AttributeAllocationService(classes_repo=classes_repo)
    player = create_player_from_class_id(
        class_id="warrior",
        name="Hero",
        classes_repo=classes_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        rng=state.rng,
    )
    state.player = player
    starting_level = classes_repo.get_starting_level("warrior")
    state.member_levels[player.id] = starting_level + 1
    state.player_attribute_points_spent = 0
    base_str = player.attributes.STR

    last_menu: dict[str, list[str] | str] = {}
    choices = {
        "Town Menu": ["Allocate Attributes", "Quit Game"],
        "Allocation Options": ["STR", "Back"],
    }

    def fake_render_menu(title, options):
        last_menu["title"] = title
        last_menu["options"] = options
        if title == "Town Menu":
            assert "Allocate Attributes" in options

    def fake_prompt(_count: int) -> int:
        title = last_menu.get("title")
        options = last_menu.get("options", [])
        assert isinstance(title, str)
        assert isinstance(options, list)
        next_label = choices[title].pop(0)
        return options.index(next_label)

    monkeypatch.setattr(app, "render_heading", lambda *args, **kwargs: None)
    monkeypatch.setattr(app, "_render_boxed_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(app, "render_menu", fake_render_menu)
    monkeypatch.setattr(app, "_prompt_menu_index", fake_prompt)

    result = app._run_town_menu(
        story_service=object(),
        inventory_service=inventory_service,
        quest_service=object(),
        shop_service=object(),
        summon_loadout_service=summon_service,
        attribute_service=attribute_service,
        state=state,
        save_service=object(),
        slot_store=object(),
        battle_service=object(),
        area_service=object(),
    )

    assert result is None
    assert state.player.attributes.STR == base_str + 1
    assert state.player_attribute_points_spent == 1


def test_allocate_attributes_menu_debug_option_visibility(monkeypatch) -> None:
    from tbg.data.repositories import ArmourRepository, ClassesRepository, PartyMembersRepository, WeaponsRepository
    from tbg.services.attribute_allocation_service import AttributeAllocationService
    from tbg.services.factories import create_player_from_class_id
    from tbg.services.inventory_service import InventoryService

    state = _camp_state()
    weapons_repo = WeaponsRepository()
    armour_repo = ArmourRepository()
    classes_repo = ClassesRepository(
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
    )
    party_repo = PartyMembersRepository()
    inventory_service = InventoryService(
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        party_members_repo=party_repo,
    )
    attribute_service = AttributeAllocationService(classes_repo=classes_repo)
    state.player = create_player_from_class_id(
        class_id="warrior",
        name="Hero",
        classes_repo=classes_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        rng=state.rng,
    )
    state.member_levels[state.player.id] = classes_repo.get_starting_level("warrior")
    state.player_attribute_points_spent = 0

    captured: dict[str, list[str]] = {}

    def fake_render_menu(title, options):
        if title == "Allocation Options":
            captured["options"] = list(options)

    monkeypatch.setattr(app, "render_heading", lambda *args, **kwargs: None)
    monkeypatch.setattr(app, "_render_boxed_panel", lambda *args, **kwargs: None)
    monkeypatch.setattr(app, "render_menu", fake_render_menu)
    def choose_back(_count: int) -> int:
        options = captured.get("options", [])
        return options.index("Back")

    monkeypatch.setattr(app, "_prompt_menu_index", choose_back)

    monkeypatch.delenv("TBG_DEBUG", raising=False)
    app._run_attribute_allocation_menu(attribute_service, inventory_service, state)
    assert "DEBUG: Grant Attribute Points" not in captured["options"]

    monkeypatch.setenv("TBG_DEBUG", "1")
    app._run_attribute_allocation_menu(attribute_service, inventory_service, state)
    assert "DEBUG: Grant Attribute Points" in captured["options"]


def test_inventory_equipment_summons_visible_for_non_beastmaster(monkeypatch, capsys) -> None:
    from tbg.data.repositories import ArmourRepository, ClassesRepository, PartyMembersRepository, WeaponsRepository
    from tbg.services.factories import create_player_from_class_id
    from tbg.services.inventory_service import InventoryService
    from tbg.services.summon_loadout_service import SummonLoadoutService
    from tbg.data.repositories import SummonsRepository

    state = _camp_state()
    weapons_repo = WeaponsRepository()
    armour_repo = ArmourRepository()
    summons_repo = SummonsRepository()
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
    summon_service = SummonLoadoutService(classes_repo=classes_repo, summons_repo=summons_repo)
    player = create_player_from_class_id(
        class_id="warrior",
        name="Hero",
        classes_repo=classes_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        rng=state.rng,
    )
    state.player = player

    menus: list[list[str]] = []

    def fake_render_menu(_title, options):
        menus.append(list(options))

    monkeypatch.setattr(app, "render_heading", lambda *args, **kwargs: None)
    monkeypatch.setattr(app, "render_menu", fake_render_menu)
    monkeypatch.setattr(app, "_prompt_menu_index", lambda _count: menus[-1].index("Back"))

    app._run_member_equipment_menu(
        inventory_service.list_party_members(state)[0],
        inventory_service,
        summon_service,
        state,
    )

    out = capsys.readouterr().out
    assert "No summons available." in out
    assert any("Manage Summons" in options for options in menus)


def test_party_member_equipment_has_manage_summons(monkeypatch) -> None:
    from tbg.data.repositories import ArmourRepository, ClassesRepository, PartyMembersRepository, WeaponsRepository
    from tbg.services.factories import create_player_from_class_id
    from tbg.services.inventory_service import InventoryService
    from tbg.services.summon_loadout_service import SummonLoadoutService
    from tbg.data.repositories import SummonsRepository

    state = _camp_state()
    weapons_repo = WeaponsRepository()
    armour_repo = ArmourRepository()
    summons_repo = SummonsRepository()
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
    summon_service = SummonLoadoutService(classes_repo=classes_repo, summons_repo=summons_repo)
    state.player = create_player_from_class_id(
        class_id="warrior",
        name="Hero",
        classes_repo=classes_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        rng=state.rng,
    )
    state.party_members = ["emma"]
    member_def = party_repo.get("emma")
    state.party_member_attributes["emma"] = member_def.starting_attributes

    captured: dict[str, list[str]] = {}

    def fake_render_menu(_title, options):
        captured["options"] = list(options)

    monkeypatch.setattr(app, "render_heading", lambda *args, **kwargs: None)
    monkeypatch.setattr(app, "render_menu", fake_render_menu)
    monkeypatch.setattr(app, "_prompt_menu_index", lambda _count: captured["options"].index("Back"))

    app._run_member_equipment_menu(
        inventory_service.list_party_members(state)[1],
        inventory_service,
        summon_service,
        state,
    )

    assert "Manage Summons" in captured["options"]


def test_shared_inventory_has_no_summon_section(monkeypatch, capsys) -> None:
    from tbg.data.repositories import ArmourRepository, ClassesRepository, PartyMembersRepository, WeaponsRepository
    from tbg.services.factories import create_player_from_class_id
    from tbg.services.inventory_service import InventoryService
    from tbg.services.summon_loadout_service import SummonLoadoutService
    from tbg.data.repositories import SummonsRepository

    state = _camp_state()
    weapons_repo = WeaponsRepository()
    armour_repo = ArmourRepository()
    summons_repo = SummonsRepository()
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
    summon_service = SummonLoadoutService(classes_repo=classes_repo, summons_repo=summons_repo)
    state.player = create_player_from_class_id(
        class_id="warrior",
        name="Hero",
        classes_repo=classes_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        rng=state.rng,
    )

    monkeypatch.setattr(app, "render_heading", lambda *args, **kwargs: None)
    monkeypatch.setattr(app, "render_menu", lambda *args, **kwargs: None)
    monkeypatch.setattr(app, "_prompt_menu_index", lambda _count: _count - 1)

    app._run_inventory_flow(inventory_service, summon_service, state)
    out = capsys.readouterr().out
    assert "Summons:" not in out


def test_beastmaster_can_manage_summons_via_equipment(monkeypatch) -> None:
    from tbg.data.repositories import ArmourRepository, ClassesRepository, PartyMembersRepository, WeaponsRepository
    from tbg.services.factories import create_player_from_class_id
    from tbg.services.inventory_service import InventoryService
    from tbg.services.summon_loadout_service import SummonLoadoutService
    from tbg.data.repositories import SummonsRepository

    state = _camp_state()
    weapons_repo = WeaponsRepository()
    armour_repo = ArmourRepository()
    summons_repo = SummonsRepository()
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
    summon_service = SummonLoadoutService(classes_repo=classes_repo, summons_repo=summons_repo)
    player = create_player_from_class_id(
        class_id="beastmaster",
        name="Hero",
        classes_repo=classes_repo,
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        rng=state.rng,
    )
    state.player = player

    choices = iter([3, 0, 0, 3, 4])

    monkeypatch.setattr(app, "render_heading", lambda *args, **kwargs: None)
    monkeypatch.setattr(app, "render_menu", lambda *args, **kwargs: None)
    monkeypatch.setattr(app, "_prompt_menu_index", lambda _count: next(choices))

    app._run_member_equipment_menu(
        inventory_service.list_party_members(state)[0],
        inventory_service,
        summon_service,
        state,
    )

    assert summon_service.get_equipped_summons(state, state.player.id)


def test_prompt_index_batch_parses_and_dedupes(monkeypatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt: "1, 3, 1,5")
    assert _prompt_index_batch(5, "Select: ") == [1, 3, 5]


def test_prompt_index_batch_rejects_invalid(monkeypatch, capsys) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt: "1,,2")
    assert _prompt_index_batch(5, "Select: ") is None
    assert "Selections cannot be empty." in capsys.readouterr().out

    monkeypatch.setattr("builtins.input", lambda _prompt: "a,2")
    assert _prompt_index_batch(5, "Select: ") is None

    monkeypatch.setattr("builtins.input", lambda _prompt: "0")
    assert _prompt_index_batch(5, "Select: ") is None


def test_handle_story_events_recursion_receives_area_service(monkeypatch) -> None:
    state = _camp_state()
    floors_repo = FloorsRepository()
    locations_repo = LocationsRepository(floors_repo=floors_repo)
    area_service = AreaServiceV2(floors_repo=floors_repo, locations_repo=locations_repo)
    area_service.initialize_state(state)
    quest_service = object()

    captured: dict[str, object] = {}

    def fake_post_battle_interlude(
        message,
        story_service,
        inventory_service,
        quest_service_arg,
        shop_service_arg,
        summon_loadout_service,
        attribute_service,
        state_arg,
        save_service,
        slot_store,
        battle_service,
        area_service_arg,
    ):
        del shop_service_arg, summon_loadout_service, attribute_service
        captured["area_service"] = area_service_arg
        captured["quest_service"] = quest_service_arg
        return [object()]

    monkeypatch.setattr(app, "_run_post_battle_interlude", fake_post_battle_interlude)
    monkeypatch.setattr(app, "_render_story_if_needed", lambda *args, **kwargs: False)
    events = [GameMenuEnteredEvent(message="Rest up")]

    result = app._handle_story_events(
        events,
        battle_service=object(),
        story_service=object(),
        inventory_service=object(),
        quest_service=quest_service,
        shop_service=object(),
        summon_loadout_service=_summon_service(),
        attribute_service=object(),
        state=state,
        save_service=object(),
        slot_store=object(),
        area_service=area_service,
        print_header=True,
    )

    assert result is True
    assert captured["area_service"] is area_service
    assert captured["quest_service"] is quest_service


def test_warp_to_checkpoint_location_emits_message(monkeypatch, capsys) -> None:
    monkeypatch.setenv("TBG_DEBUG", "1")
    floors_repo = FloorsRepository()
    locations_repo = LocationsRepository(floors_repo=floors_repo)
    area_service = AreaServiceV2(floors_repo=floors_repo, locations_repo=locations_repo)
    state = _camp_state()
    area_service.initialize_state(state)
    area_service.force_set_location(state, "village")
    state.story_checkpoint_location_id = "village_outskirts"

    did_warp = _warp_to_checkpoint_location(area_service, state)

    assert did_warp is True
    assert state.current_location_id == "village_outskirts"
    out = capsys.readouterr().out
    assert "checkpoint rewind" in out
    assert "DEBUG: checkpoint warp from=village to=village_outskirts" in out


def test_warp_to_checkpoint_skips_when_already_at_location(capsys) -> None:
    floors_repo = FloorsRepository()
    locations_repo = LocationsRepository(floors_repo=floors_repo)
    area_service = AreaServiceV2(floors_repo=floors_repo, locations_repo=locations_repo)
    state = _camp_state()
    area_service.initialize_state(state)
    state.story_checkpoint_location_id = state.current_location_id

    assert _warp_to_checkpoint_location(area_service, state) is False
    assert capsys.readouterr().out == ""


def test_converse_auto_resume_does_not_end_demo() -> None:
    from tbg.data.repositories import (
        ArmourRepository,
        ClassesRepository,
        PartyMembersRepository,
        StoryRepository,
        WeaponsRepository,
    )
    from tbg.services.inventory_service import InventoryService
    from tbg.services.story_service import StoryService

    weapons_repo = WeaponsRepository()
    armour_repo = ArmourRepository()
    party_repo = PartyMembersRepository()
    inventory_service = InventoryService(
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        party_members_repo=party_repo,
    )
    story_service = StoryService(
        story_repo=StoryRepository(),
        classes_repo=ClassesRepository(weapons_repo=weapons_repo, armour_repo=armour_repo),
        weapons_repo=weapons_repo,
        armour_repo=armour_repo,
        party_members_repo=party_repo,
        inventory_service=inventory_service,
        quest_service=None,
    )
    state = story_service.start_new_game(seed=12, player_name="Hero")
    story_service.play_node(state, "threshold_inn_hub_router")
    follow_up = _play_node_with_auto_resume(story_service, state, "dana_turn_in_check")
    assert follow_up is not None
    assert story_service.get_current_node_view(state).choices


def test_attribute_lines_include_bond() -> None:
    from tbg.domain.attribute_scaling import build_attribute_scaling_breakdown
    from tbg.domain.entities import Attributes, BaseStats, Stats
    from tbg.presentation.cli.app import _build_attribute_lines

    attributes = Attributes(STR=1, DEX=2, INT=3, VIT=4, BOND=5)
    base_stats = BaseStats(max_hp=10, max_mp=5, attack=2, defense=1, speed=3)
    breakdown = build_attribute_scaling_breakdown(
        base_stats,
        attributes,
        current_hp=10,
        current_mp=5,
    )
    lines = _build_attribute_lines(breakdown)
    joined = " ".join(lines)
    for label in ("STR", "DEX", "INT", "VIT", "BOND"):
        assert label in joined
    assert "(+" in joined
    assert "increases" in joined


def test_attribute_debug_lines_do_not_show_base_current() -> None:
    from tbg.domain.attribute_scaling import build_attribute_scaling_breakdown
    from tbg.domain.entities import Attributes, BaseStats
    from tbg.presentation.cli.app import _build_attribute_debug_lines

    attributes = Attributes(STR=2, DEX=1, INT=1, VIT=1, BOND=0)
    base_stats = BaseStats(max_hp=40, max_mp=10, attack=8, defense=3, speed=4)
    breakdown = build_attribute_scaling_breakdown(
        base_stats,
        attributes,
        current_hp=55,
        current_mp=12,
    )
    lines = _build_attribute_debug_lines(breakdown)
    base_line = next(line for line in lines if "MAX HP" in line and "MAX MP" in line)
    assert "/" not in base_line


def test_filter_turn_ins_by_location_npcs() -> None:
    from tbg.presentation.cli.app import _filter_turn_ins_for_location
    from tbg.services.quest_service import QuestTurnInView

    location_view = type(
        "LocationViewStub",
        (),
        {"npcs_present": [type("Npc", (), {"npc_id": "dana"})()], "id": "threshold_inn"},
    )()
    turn_ins = [
        QuestTurnInView(quest_id="q1", name="Dana Quest", npc_id="dana", node_id="node1"),
        QuestTurnInView(quest_id="q2", name="Cerel Quest", npc_id="cerel", node_id="node2"),
        QuestTurnInView(quest_id="q3", name="Unknown", npc_id=None, node_id="node3"),
    ]
    state = _camp_state()
    filtered = _filter_turn_ins_for_location(turn_ins, location_view, state)
    assert [entry.quest_id for entry in filtered] == ["q1"]


def test_turn_in_check_nodes_do_not_end_demo(monkeypatch, capsys) -> None:
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
    ) = app._build_services()
    for node_id in ("dana_turn_in_check", "dana_protoquest_turn_in_check", "cerel_turn_in_check"):
        state = story_service.start_new_game(seed=101, player_name="Hero")
        area_service.initialize_state(state)
        story_service.play_node(state, node_id)

        called = {"prompted": False}

        def fake_prompt(_count: int) -> int:
            called["prompted"] = True
            raise RuntimeError("stop")

        monkeypatch.setattr(app, "_prompt_choice", fake_prompt)
        monkeypatch.setattr(app, "_render_node_view", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(app, "_run_post_battle_interlude", lambda *args, **kwargs: None)
        try:
            result = app._run_story_loop(
                story_service,
                battle_service,
                inventory_service,
                quest_service,
                shop_service,
                summon_loadout_service,
                attribute_service,
                state,
                save_service,
                app.SaveSlotStore(),
                area_service,
                from_load=False,
            )
        except RuntimeError:
            result = None

        out = capsys.readouterr().out
        assert "End of demo slice" not in out
        assert result in (None, False)
