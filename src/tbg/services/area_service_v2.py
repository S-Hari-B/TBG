"""AreaServiceV2 for floor-based locations (scaffold only)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from tbg.data.repositories import FloorsRepository, LocationsRepository
from tbg.domain.defs import LocationConnectionDef, LocationDef
from tbg.domain.state import GameState
from tbg.services.errors import TravelBlockedError
from tbg.services.quest_service import QuestService

TRAVEL_BLOCKED_MESSAGE = "You can't push onward yet. Something unresolved still blocks your path."


@dataclass(slots=True)
class TravelOptionView:
    """Renderable connection to another area."""

    destination_id: str
    label: str
    progresses_story: bool


@dataclass(slots=True)
class NpcPresenceView:
    npc_id: str
    talk_node_id: str
    quest_hub_node_id: str | None


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
    npcs_present: Tuple[NpcPresenceView, ...]


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
class TravelDecision:
    allowed: bool
    reason: str | None = None


class AreaServiceV2:
    """Parallel area service for floor-based location data."""

    def __init__(
        self,
        *,
        floors_repo: FloorsRepository,
        locations_repo: LocationsRepository,
        quest_service: QuestService | None = None,
    ) -> None:
        self._floors_repo = floors_repo
        self._locations_repo = locations_repo
        self._quest_service = quest_service

    def initialize_state_v2(self, state: GameState) -> None:
        """Ensure the game state has a valid current location for v2 definitions."""
        if state.current_location_id:
            return
        start_floor = self._select_start_floor()
        state.current_location_id = start_floor.starting_location_id
        if state.current_location_id not in state.visited_locations:
            state.visited_locations.append(state.current_location_id)
        location_def = self._locations_repo.get(state.current_location_id)
        if state.current_location_id not in state.location_entry_seen:
            state.location_entry_seen[state.current_location_id] = (
                location_def.entry_story_node_id is None
            )
        state.location_visits.setdefault(state.current_location_id, 0)

    def initialize_state(self, state: GameState) -> None:
        """Compatibility wrapper to mirror v1 init."""
        self.initialize_state_v2(state)

    def get_current_location_view(self, state: GameState) -> LocationView:
        location_def = self._locations_repo.get(self._ensure_current_location_id(state))
        return self._build_location_view(location_def, state)

    def build_debug_view(self, state: GameState) -> LocationDebugView:
        location_view = self.get_current_location_view(state)
        visited = tuple(state.visited_locations)
        entry_flags = tuple(sorted(state.location_entry_seen.items()))
        return LocationDebugView(
            location=location_view,
            visited_locations=visited,
            entry_seen_flags=entry_flags,
        )

    def force_set_location(self, state: GameState, location_id: str) -> None:
        location_def = self._locations_repo.get(location_id)
        state.current_location_id = location_def.id
        if location_def.id not in state.visited_locations:
            state.visited_locations.append(location_def.id)

    def can_travel_to(self, state: GameState, destination_id: str) -> TravelDecision:
        current = self._locations_repo.get(self._ensure_current_location_id(state))
        connections = {
            conn.to_id: conn
            for conn in current.connections
            if self._connection_is_visible(conn, state)
        }
        connection = connections.get(destination_id)
        if connection is None:
            return TravelDecision(allowed=False, reason="Destination not available.")
        checkpoint_thread = state.story_checkpoint_thread_id or "main_story"
        checkpoint_active = bool(state.story_checkpoint_node_id and checkpoint_thread == "main_story")
        if checkpoint_active and connection.progresses_story:
            return TravelDecision(allowed=False, reason=TRAVEL_BLOCKED_MESSAGE)
        return TravelDecision(allowed=True)

    def travel_to(self, state: GameState, destination_id: str) -> TravelResult:
        current_id = self._ensure_current_location_id(state)
        current_location = self._locations_repo.get(current_id)
        destination_id = destination_id.strip()
        if not destination_id:
            raise ValueError("Destination id must not be empty.")
        connection_lookup = {conn.to_id: conn for conn in current_location.connections}
        connection = connection_lookup.get(destination_id)
        if connection is None:
            raise ValueError(f"Destination '{destination_id}' is not reachable from '{current_id}'.")
        if not self._connection_is_visible(connection, state):
            raise ValueError(f"Destination '{destination_id}' is not available from '{current_id}'.")
        checkpoint_thread = state.story_checkpoint_thread_id or "main_story"
        checkpoint_active = bool(state.story_checkpoint_node_id and checkpoint_thread == "main_story")
        if checkpoint_active and connection.progresses_story:
            raise TravelBlockedError(TRAVEL_BLOCKED_MESSAGE)

        destination_def = self._locations_repo.get(destination_id)
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
        events: List[object] = [
            TravelPerformedEvent(
                from_location_id=current_location.id,
                from_location_name=current_location.name,
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

    def _ensure_current_location_id(self, state: GameState) -> str:
        if not state.current_location_id:
            self.initialize_state_v2(state)
        return state.current_location_id

    def _build_location_view(self, location_def: LocationDef, state: GameState) -> LocationView:
        return LocationView(
            id=location_def.id,
            name=location_def.name,
            description=location_def.description,
            tags=location_def.tags,
            connections=tuple(
                TravelOptionView(
                    destination_id=conn.to_id,
                    label=conn.label,
                    progresses_story=conn.progresses_story,
                )
                for conn in location_def.connections
                if self._connection_is_visible(conn, state)
            ),
            entry_story_node_id=location_def.entry_story_node_id,
            entry_seen=state.location_entry_seen.get(
                location_def.id, location_def.entry_story_node_id is None
            ),
            npcs_present=tuple(
                NpcPresenceView(
                    npc_id=npc.npc_id,
                    talk_node_id=npc.talk_node_id or "",
                    quest_hub_node_id=npc.quest_hub_node_id,
                )
                for npc in location_def.npcs_present
                if npc.talk_node_id is not None
            ),
        )

    @staticmethod
    def _connection_is_visible(connection: LocationConnectionDef, state: GameState) -> bool:
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

    def _select_start_floor(self):
        floors = self._floors_repo.all()
        if not floors:
            raise ValueError("No floors defined.")
        floor_zero = next((floor for floor in floors if floor.id == "floor_zero"), None)
        if floor_zero is not None:
            return floor_zero
        return sorted(floors, key=lambda floor: floor.id)[0]
