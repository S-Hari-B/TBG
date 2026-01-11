"""Application service for area travel and location views."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from tbg.data.repositories import AreasRepository
from tbg.domain.defs import AreaDef
from tbg.domain.state import GameState

DEFAULT_STARTING_AREA_ID = "village_outskirts"


@dataclass(slots=True)
class TravelOptionView:
    """Renderable connection to another area."""

    destination_id: str
    label: str


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


class AreaService:
    """Coordinates travel between areas and related state."""

    def __init__(self, areas_repo: AreasRepository) -> None:
        self._areas_repo = areas_repo

    def initialize_state(self, state: GameState, starting_location_id: str | None = None) -> None:
        """Ensure the game state has a valid current location."""
        default_id = starting_location_id or DEFAULT_STARTING_AREA_ID
        area_def = self._areas_repo.get(default_id)
        state.current_location_id = area_def.id
        if area_def.id not in state.visited_locations:
            state.visited_locations.append(area_def.id)
        if area_def.id not in state.location_entry_seen:
            state.location_entry_seen[area_def.id] = area_def.entry_story_node_id is None

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
        connection_targets = {conn.to_id for conn in current_area.connections}
        if destination_id not in connection_targets:
            raise ValueError(f"Destination '{destination_id}' is not reachable from '{current_id}'.")
        destination_def = self._areas_repo.get(destination_id)
        state.current_location_id = destination_def.id
        if destination_def.id not in state.visited_locations:
            state.visited_locations.append(destination_def.id)
        entry_seen = state.location_entry_seen.get(destination_def.id)
        if entry_seen is None:
            entry_seen = destination_def.entry_story_node_id is None
            state.location_entry_seen[destination_def.id] = entry_seen
        entry_story_node_id = None
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
        return TravelResult(
            events=events,
            location_view=location_view,
            entry_story_node_id=entry_story_node_id,
        )

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
                TravelOptionView(destination_id=conn.to_id, label=conn.label)
                for conn in area_def.connections
            ),
            entry_story_node_id=area_def.entry_story_node_id,
            entry_seen=state.location_entry_seen.get(
                area_def.id, area_def.entry_story_node_id is None
            ),
        )

