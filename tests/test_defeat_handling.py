from __future__ import annotations

from dataclasses import dataclass

from tbg.core.rng import RNG
from tbg.domain.entities import Attributes, BaseStats, Player, Stats
from tbg.domain.state import GameState
from tbg.presentation.cli import app


@dataclass
class _StubStoryService:
    rewound: bool = False
    cleared: bool = False

    def rewind_to_checkpoint(self, state: GameState) -> bool:
        self.rewound = True
        state.pending_story_node_id = state.story_checkpoint_node_id
        return True

    def clear_checkpoint(self, state: GameState, thread_id: str = "main_story") -> None:
        self.cleared = True
        state.story_checkpoint_node_id = None
        state.story_checkpoint_location_id = None
        state.story_checkpoint_thread_id = None


@dataclass
class _StubBattleService:
    def restore_party_resources(self, state: GameState, *, restore_hp: bool, restore_mp: bool) -> None:
        if not state.player:
            return
        if restore_hp:
            state.player.stats.hp = state.player.stats.max_hp
        if restore_mp:
            state.player.stats.mp = state.player.stats.max_mp


class _StubInventoryService:
    pass


class _StubSaveService:
    pass


class _StubSlotStore:
    pass


class _StubAreaService:
    def __init__(self, tags: tuple[str, ...]) -> None:
        self._tags = tags

    def get_current_location_view(self, state: GameState):
        del state
        return type("LocationViewStub", (), {"tags": self._tags})()


def _make_state() -> GameState:
    state = GameState(seed=1, rng=RNG(1), mode="battle", current_node_id="dummy")
    state.player = Player(
        id="hero",
        name="Hero",
        class_id="warrior",
        stats=Stats(max_hp=30, hp=0, max_mp=10, mp=0, attack=5, defense=2, speed=5),
        attributes=Attributes(STR=6, DEX=4, INT=2, VIT=6, BOND=0),
        base_stats=BaseStats(max_hp=30, max_mp=10, attack=5, defense=2, speed=5),
        equipped_summons=[],
    )
    state.gold = 100
    return state


def test_open_area_defeat_does_not_rewind_and_keeps_location(monkeypatch) -> None:
    state = _make_state()
    state.story_checkpoint_node_id = "battle_node"
    state.story_checkpoint_location_id = "open_plains"
    state.current_location_id = "open_plains"

    story_service = _StubStoryService()
    battle_service = _StubBattleService()

    monkeypatch.setattr(app, "_run_post_battle_interlude", lambda *args, **kwargs: [])

    result = app._handle_defeat_flow(
        battle_service=battle_service,
        story_service=story_service,
        inventory_service=_StubInventoryService(),
        quest_service=object(),
        shop_service=object(),
        summon_loadout_service=_StubInventoryService(),
        attribute_service=object(),
        state=state,
        save_service=_StubSaveService(),
        slot_store=_StubSlotStore(),
        area_service=_StubAreaService(tags=("open", "floor_one")),
    )

    assert result is True
    assert story_service.rewound is False
    assert story_service.cleared is False
    assert state.story_checkpoint_node_id == "battle_node"
    assert state.current_location_id == "open_plains"
    assert state.player.stats.hp == 1
    assert state.player.stats.mp == 1
    assert state.gold == 50


def test_story_defeat_rewinds_and_restores(monkeypatch) -> None:
    state = _make_state()
    state.story_checkpoint_node_id = "battle_node"
    state.story_checkpoint_location_id = "threshold_inn"
    state.current_location_id = "goblin_cave_entrance"

    story_service = _StubStoryService()
    battle_service = _StubBattleService()

    monkeypatch.setattr(app, "_run_post_battle_interlude", lambda *args, **kwargs: [])

    result = app._handle_defeat_flow(
        battle_service=battle_service,
        story_service=story_service,
        inventory_service=_StubInventoryService(),
        quest_service=object(),
        shop_service=object(),
        summon_loadout_service=_StubInventoryService(),
        attribute_service=object(),
        state=state,
        save_service=_StubSaveService(),
        slot_store=_StubSlotStore(),
        area_service=_StubAreaService(tags=("hub", "floor_one")),
    )

    assert result is True
    assert story_service.rewound is True
    assert story_service.cleared is False
    assert state.player.stats.hp == state.player.stats.max_hp
    assert state.player.stats.mp == state.player.stats.max_mp
    assert state.gold == 50


def test_open_area_defeat_does_not_leak_context(monkeypatch) -> None:
    state = _make_state()
    state.story_checkpoint_node_id = "battle_node"
    state.story_checkpoint_location_id = "threshold_inn"
    state.current_location_id = "open_plains"

    story_service = _StubStoryService()
    battle_service = _StubBattleService()

    monkeypatch.setattr(app, "_run_post_battle_interlude", lambda *args, **kwargs: [])

    app._handle_defeat_flow(
        battle_service=battle_service,
        story_service=story_service,
        inventory_service=_StubInventoryService(),
        quest_service=object(),
        shop_service=object(),
        summon_loadout_service=_StubInventoryService(),
        attribute_service=object(),
        state=state,
        save_service=_StubSaveService(),
        slot_store=_StubSlotStore(),
        area_service=_StubAreaService(tags=("open",)),
    )

    # Move to non-open location and ensure story defeat path triggers rewind.
    state.current_location_id = "threshold_inn"
    story_service.rewound = False
    app._handle_defeat_flow(
        battle_service=battle_service,
        story_service=story_service,
        inventory_service=_StubInventoryService(),
        quest_service=object(),
        shop_service=object(),
        summon_loadout_service=_StubInventoryService(),
        attribute_service=object(),
        state=state,
        save_service=_StubSaveService(),
        slot_store=_StubSlotStore(),
        area_service=_StubAreaService(tags=("hub",)),
    )
    assert story_service.rewound is True
