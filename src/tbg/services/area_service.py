"""Application service for area travel and location views."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from tbg.data.repositories import AreasRepository
from tbg.domain.defs import AreaDef
from tbg.domain.state import GameState
from tbg.services.errors import TravelBlockedError
from tbg.services.quest_service import QuestService

DEFAULT_STARTING_AREA_ID = "threshold_inn"
TRAVEL_BLOCKED_MESSAGE = "You can't push onward yet. Something unresolved still blocks your path."


@dataclass(slots=True)
class TravelOptionView:
    """Renderable connection to another area."""

    destination_id: str
    label: str
    progresses_story: bool


@dataclass(slots=True)
class LocationView:
    """Presentation data for the player's current area."""

    id: str
    name: str
    description: str
    tags: Tuple[str, ...]
    connections: Tuple[TravelOptionView, ...]
    entry_story_node_id: str | None
    entry_seen: bool
    npcs_present: Tuple["NpcPresenceView", ...]


@dataclass(slots=True)
class LocationDebugView:
    """Extra debug information for location state."""

    location: LocationView
    visited_locations: Tuple[str, ...]
    entry_seen_flags: Tuple[Tuple[str, bool], ...]


@dataclass(slots=True)
class TravelEvent:
    """Base class for travel-related events."""


@dataclass(slots=True)
class TravelPerformedEvent(TravelEvent):
    """Emitted when the party moves between areas."""

    from_location_id: str
    from_location_name: str
    to_location_id: str
    to_location_name: str


@dataclass(slots=True)
class LocationEnteredEvent(TravelEvent):
    """Emitted after the player arrives at an area."""

    location: LocationView


@dataclass(slots=True)
class TravelResult:
    """Return payload from a travel action."""

    events: List[TravelEvent]
    location_view: LocationView
    entry_story_node_id: str | None


@dataclass(slots=True)
class NpcPresenceView:
    npc_id: str
    talk_node_id: str
    quest_hub_node_id: str | None


class AreaService:
    """Coordinates travel between areas and related state."""

    def __init__(self, areas_repo: AreasRepository, *, quest_service: QuestService | None = None) -> None:
        self._areas_repo = areas_repo
        self._quest_service = quest_service

    def initialize_state(self, state: GameState, starting_location_id: str | None = None) -> None:
        """Ensure the game state has a valid current location."""
        default_id = starting_location_id or DEFAULT_STARTING_AREA_ID
        area_def = self._areas_repo.get(default_id)
        state.current_location_id = area_def.id
        if area_def.id not in state.visited_locations:
            state.visited_locations.append(area_def.id)
        if area_def.id not in state.location_entry_seen:
            state.location_entry_seen[area_def.id] = area_def.entry_story_node_id is None
        state.location_visits.setdefault(area_def.id, 0)

    def get_current_location_view(self, state: GameState) -> LocationView:
        """Return the view for the player's current location."""
        area_def = self._areas_repo.get(self._ensure_current_location_id(state))
        return self._build_location_view(area_def, state)

    def build_debug_view(self, state: GameState) -> LocationDebugView:
        """Return debug metadata for rendering."""
        location_view = self.get_current_location_view(state)
        visited = tuple(state.visited_locations)
        entry_flags = tuple(sorted(state.location_entry_seen.items()))
        return LocationDebugView(
            location=location_view,
            visited_locations=visited,
            entry_seen_flags=entry_flags,
        )

    def travel_to(self, state: GameState, destination_id: str) -> TravelResult:
        """Move the party to a connected destination."""
        current_id = self._ensure_current_location_id(state)
        current_area = self._areas_repo.get(current_id)
        destination_id = destination_id.strip()
        if not destination_id:
            raise ValueError("Destination id must not be empty.")
        connection_lookup = {conn.to_id: conn for conn in current_area.connections}
        connection = connection_lookup.get(destination_id)
        if connection is None:
            raise ValueError(f"Destination '{destination_id}' is not reachable from '{current_id}'.")
        if not self._connection_is_visible(connection, state):
            raise ValueError(f"Destination '{destination_id}' is not available from '{current_id}'.")
        checkpoint_thread = state.story_checkpoint_thread_id or "main_story"
        checkpoint_active = bool(state.story_checkpoint_node_id and checkpoint_thread == "main_story")
        if checkpoint_active and connection.progresses_story:
            raise TravelBlockedError(TRAVEL_BLOCKED_MESSAGE)
        destination_def = self._areas_repo.get(destination_id)
        state.current_location_id = destination_def.id
        state.location_visits[destination_def.id] = state.location_visits.get(destination_def.id, 0) + 1
        if destination_def.id not in state.visited_locations:
            state.visited_locations.append(destination_def.id)
        entry_story_node_id = None
        checkpoint_thread = state.story_checkpoint_thread_id or "main_story"
        checkpoint_active = bool(state.story_checkpoint_node_id and checkpoint_thread == "main_story")
        if not checkpoint_active:
            entry_seen = state.location_entry_seen.get(destination_def.id)
            if entry_seen is None:
                entry_seen = destination_def.entry_story_node_id is None
                state.location_entry_seen[destination_def.id] = entry_seen
            if destination_def.entry_story_node_id and not entry_seen:
                entry_story_node_id = destination_def.entry_story_node_id
                state.location_entry_seen[destination_def.id] = True

        location_view = self._build_location_view(destination_def, state)
        events: List[TravelEvent] = [
            TravelPerformedEvent(
                from_location_id=current_area.id,
                from_location_name=current_area.name,
                to_location_id=destination_def.id,
                to_location_name=destination_def.name,
            ),
            LocationEnteredEvent(location=location_view),
        ]
        result = TravelResult(
            events=events,
            location_view=location_view,
            entry_story_node_id=entry_story_node_id,
        )
        if self._quest_service:
            self._quest_service.record_area_visit(state, destination_def.id)
        return result

    def force_set_location(self, state: GameState, location_id: str) -> None:
        """Teleport the party without triggering story hooks or travel events."""
        location_def = self._areas_repo.get(location_id)
        state.current_location_id = location_def.id
        if location_def.id not in state.visited_locations:
            state.visited_locations.append(location_def.id)

    def _ensure_current_location_id(self, state: GameState) -> str:
        if not state.current_location_id:
            self.initialize_state(state)
        return state.current_location_id

    def _build_location_view(self, area_def: AreaDef, state: GameState) -> LocationView:
        return LocationView(
            id=area_def.id,
            name=area_def.name,
            description=area_def.description,
            tags=area_def.tags,
            connections=tuple(
                TravelOptionView(
                    destination_id=conn.to_id,
                    label=conn.label,
                    progresses_story=conn.progresses_story,
                )
                for conn in area_def.connections
                if self._connection_is_visible(conn, state)
            ),
            entry_story_node_id=area_def.entry_story_node_id,
            entry_seen=state.location_entry_seen.get(
                area_def.id, area_def.entry_story_node_id is None
            ),
            npcs_present=tuple(
                NpcPresenceView(
                    npc_id=npc.npc_id,
                    talk_node_id=npc.talk_node_id,
                    quest_hub_node_id=npc.quest_hub_node_id,
                )
                for npc in area_def.npcs_present
            ),
        )

    @staticmethod
    def _connection_is_visible(connection: AreaConnectionDef, state: GameState) -> bool:
        if connection.show_if_flag_true:
            if not state.flags.get(connection.show_if_flag_true, False):
                return False
        if connection.hide_if_flag_true:
            if state.flags.get(connection.hide_if_flag_true, False):
                return False
        if connection.requires_quest_active:
            if connection.requires_quest_active not in state.quests_active:
                return False
        if connection.hide_if_quest_completed:
            if connection.hide_if_quest_completed in state.quests_completed:
                return False
        if connection.hide_if_quest_turned_in:
            if connection.hide_if_quest_turned_in in state.quests_turned_in:
                return False
        return True

