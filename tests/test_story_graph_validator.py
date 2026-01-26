import warnings

import pytest

from tbg.data.repositories import (
    FloorsRepository,
    ItemsRepository,
    LocationsRepository,
    QuestsRepository,
    StoryRepository,
)
from tbg.services.story_graph_validator import EntryRoot, format_issue, validate_story_graph
from tbg.services.story_service import START_NODE_ID


_ALLOWLIST_UNREACHABLE = {
    "forest_deeper_path": "Legacy redirect node retained for old save compatibility.",
    "forest_deeper_tracks": "Legacy redirect node retained for old save compatibility.",
    "forest_deeper_follow": "Legacy redirect node retained for old save compatibility.",
    "forest_deeper_road": "Legacy redirect node retained for old save compatibility.",
    "forest_deeper_clearing": "Legacy redirect node retained for old save compatibility.",
}


def _build_entry_roots(story_repo: StoryRepository) -> list[EntryRoot]:
    roots: list[EntryRoot] = [
        EntryRoot(
            node_id=START_NODE_ID,
            source_type="story_start",
            source_id="start_new_game",
            source_field="start_node_id",
        )
    ]
    floors_repo = FloorsRepository()
    locations_repo = LocationsRepository(floors_repo=floors_repo)
    items_repo = ItemsRepository()
    quests_repo = QuestsRepository(
        items_repo=items_repo,
        locations_repo=locations_repo,
        story_repo=story_repo,
    )
    for location in locations_repo.all():
        if location.entry_story_node_id:
            roots.append(
                EntryRoot(
                    node_id=location.entry_story_node_id,
                    source_type="location",
                    source_id=location.id,
                    source_field="entry_story_node_id",
                )
            )
        for npc in location.npcs_present:
            if npc.talk_node_id:
                roots.append(
                    EntryRoot(
                        node_id=npc.talk_node_id,
                        source_type="npc",
                        source_id=f"{location.id}:{npc.npc_id}",
                        source_field="npcs_present.talk_node_id",
                    )
                )
            if npc.quest_hub_node_id:
                roots.append(
                    EntryRoot(
                        node_id=npc.quest_hub_node_id,
                        source_type="npc",
                        source_id=f"{location.id}:{npc.npc_id}",
                        source_field="npcs_present.quest_hub_node_id",
                    )
                )
    for quest in quests_repo.all():
        if quest.turn_in:
            roots.append(
                EntryRoot(
                    node_id=quest.turn_in.node_id,
                    source_type="quest",
                    source_id=quest.quest_id,
                    source_field="turn_in.node_id",
                )
            )
    return roots


def _warn_on_issues(issues):
    for issue in issues:
        if issue.severity == "WARN":
            warnings.warn(format_issue(issue), stacklevel=2)


def test_story_graph_validator_real_data():
    story_repo = StoryRepository()
    story_nodes = {node.id: node for node in story_repo.all()}
    entry_roots = _build_entry_roots(story_repo)

    issues = validate_story_graph(story_nodes, entry_roots)
    errors = [issue for issue in issues if issue.severity == "ERROR"]
    warnings_only = [issue for issue in issues if issue.severity == "WARN"]
    allowlisted = [
        issue
        for issue in warnings_only
        if issue.code == "UNREACHABLE_NODE"
        and issue.context.get("node_id") in _ALLOWLIST_UNREACHABLE
    ]
    warnings_visible = [issue for issue in warnings_only if issue not in allowlisted]

    _warn_on_issues(warnings_visible)
    print(
        "Story graph validation summary: "
        f"nodes={len(story_nodes)} roots={len(entry_roots)} "
        f"errors={len(errors)} warnings={len(warnings_visible)}"
    )
    if allowlisted:
        for issue in allowlisted:
            node_id = issue.context.get("node_id", "unknown")
            reason = _ALLOWLIST_UNREACHABLE.get(node_id, "Allowlisted unreachable node.")
            print(f"Allowlisted unreachable node: {node_id} ({reason})")
    if errors:
        pytest.fail(
            "Story graph validation errors:\n" + "\n".join(format_issue(issue) for issue in errors)
        )


def test_missing_next_reference_fails():
    story_nodes = {"start": {"text": "", "next": "missing"}}
    entry_roots = [EntryRoot("start", "test", "start", "start")]
    issues = validate_story_graph(story_nodes, entry_roots)
    assert any(issue.code == "MISSING_NODE_REF" for issue in issues)


def test_missing_choice_reference_fails():
    story_nodes = {
        "start": {"text": "", "choices": [{"label": "Go", "next": "missing"}]}
    }
    entry_roots = [EntryRoot("start", "test", "start", "start")]
    issues = validate_story_graph(story_nodes, entry_roots)
    assert any(issue.code == "MISSING_NODE_REF" for issue in issues)


def test_missing_branch_reference_fails():
    story_nodes = {
        "start": {
            "text": "",
            "effects": [
                {
                    "type": "branch_on_flag",
                    "flag_id": "flag_test",
                    "next_on_true": "missing",
                    "next_on_false": "fallback",
                }
            ],
        },
        "fallback": {"text": ""},
    }
    entry_roots = [EntryRoot("start", "test", "start", "start")]
    issues = validate_story_graph(story_nodes, entry_roots)
    assert any(issue.code == "MISSING_NODE_REF" for issue in issues)


def test_missing_entry_root_fails():
    story_nodes = {"start": {"text": ""}}
    entry_roots = [EntryRoot("missing_root", "location", "loc", "entry_story_node_id")]
    issues = validate_story_graph(story_nodes, entry_roots)
    assert any(issue.code == "MISSING_ENTRY_ROOT" for issue in issues)


def test_unknown_effect_type_warns():
    story_nodes = {"start": {"text": "", "effects": [{"type": "mystery"}]}}
    entry_roots = [EntryRoot("start", "test", "start", "start")]
    issues = validate_story_graph(story_nodes, entry_roots)
    assert any(issue.code == "UNKNOWN_EFFECT_TYPE" for issue in issues)
    assert not any(issue.severity == "ERROR" for issue in issues)


def test_unreachable_node_warns():
    story_nodes = {
        "start": {"text": "", "next": "reach"},
        "reach": {"text": ""},
        "unreachable": {"text": ""},
    }
    entry_roots = [EntryRoot("start", "test", "start", "start")]
    issues = validate_story_graph(story_nodes, entry_roots)
    assert any(issue.code == "UNREACHABLE_NODE" for issue in issues)


def test_autoadvance_cycle_detected():
    story_nodes = {
        "a": {"text": "", "next": "b"},
        "b": {"text": "", "next": "a"},
    }
    entry_roots = [EntryRoot("a", "test", "a", "start")]
    issues = validate_story_graph(story_nodes, entry_roots)
    assert any(issue.code == "AUTOADVANCE_CYCLE" for issue in issues)
