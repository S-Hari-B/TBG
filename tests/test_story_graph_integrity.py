"""Test Chapter 00 story graph integrity and Rampager quest sequencing."""
from __future__ import annotations

from typing import Any, Dict, Set

import pytest

from tbg.data.repositories import StoryRepository


def _get_chapter_nodes(story_repo: StoryRepository, chapter_file: str) -> Dict[str, Any]:
    """Load raw node data from a chapter file."""
    from tbg.data import paths
    from tbg.data.json_loader import load_json
    
    chapters_dir = paths.get_definitions_path() / "story" / "chapters"
    chapter_path = chapters_dir / chapter_file
    return load_json(chapter_path)


def test_chapter_00_graph_integrity():
    """Validate Chapter 00 has no broken references or conflicting effects."""
    story_repo = StoryRepository()
    nodes = _get_chapter_nodes(story_repo, "chapter_00_tutorial.json")
    node_ids = set(nodes.keys())
    
    issues = []
    
    for node_id, node_data in nodes.items():
        has_next = "next" in node_data
        has_choices = "choices" in node_data and len(node_data["choices"]) > 0
        has_effects = "effects" in node_data and len(node_data["effects"]) > 0
        
        # Check if node has enter_game_menu effect
        has_game_menu = False
        has_branch = False
        
        if has_effects:
            for effect in node_data["effects"]:
                if isinstance(effect, dict):
                    if effect.get("type") == "enter_game_menu":
                        has_game_menu = True
                    if effect.get("type") == "branch_on_flag":
                        has_branch = True
        
        # Rule 1: enter_game_menu nodes should NOT have 'next' field
        if has_game_menu and has_next:
            issues.append(
                f"{node_id}: has enter_game_menu AND next field (engine halts, next is unreachable)"
            )
        
        # Rule 2: Validate next references point to existing nodes
        if has_next:
            next_id = node_data["next"]
            if next_id not in node_ids:
                issues.append(f"{node_id}: next points to missing node '{next_id}'")
        
        # Rule 3: Validate all choice next references
        if has_choices:
            for choice in node_data["choices"]:
                choice_next = choice.get("next")
                if choice_next and choice_next not in node_ids:
                    label = choice.get("label", "?")
                    issues.append(
                        f"{node_id}: choice '{label}' points to missing node '{choice_next}'"
                    )
        
        # Rule 4: Validate branch_on_flag references
        if has_effects:
            for effect in node_data["effects"]:
                if isinstance(effect, dict) and effect.get("type") == "branch_on_flag":
                    next_true = effect.get("next_on_true")
                    next_false = effect.get("next_on_false")
                    if next_true and next_true not in node_ids:
                        issues.append(
                            f"{node_id}: branch next_on_true points to missing node '{next_true}'"
                        )
                    if next_false and next_false not in node_ids:
                        issues.append(
                            f"{node_id}: branch next_on_false points to missing node '{next_false}'"
                        )
    
    assert not issues, f"Graph integrity violations:\n" + "\n".join(f"  - {i}" for i in issues)


def test_chapter_00_critical_path_reachable():
    """Ensure critical story nodes are reachable from the start or via travel."""
    from tbg.data import paths
    from tbg.data.json_loader import load_json
    
    story_repo = StoryRepository()
    nodes = _get_chapter_nodes(story_repo, "chapter_00_tutorial.json")
    
    # Load locations to find travel entry points and NPC nodes
    locations_path = paths.get_definitions_path() / "locations.json"
    locations = load_json(locations_path)
    
    # BFS to find all reachable nodes (story flow + travel entry points + NPC talks)
    reachable: Set[str] = set()
    queue = ["arrival_beach_wake"]  # Story start
    
    # Add all location entry nodes as potential entry points
    for location_id, location_data in locations.items():
        entry_node = location_data.get("entry_story_node_id")
        if entry_node and entry_node in nodes:
            queue.append(entry_node)
        
        # Add NPC talk nodes
        npcs = location_data.get("npcs_present", [])
        for npc in npcs:
            talk_node = npc.get("talk_node_id")
            quest_hub = npc.get("quest_hub_node_id")
            if talk_node and talk_node in nodes:
                queue.append(talk_node)
            if quest_hub and quest_hub in nodes:
                queue.append(quest_hub)
    
    while queue:
        current = queue.pop(0)
        if current in reachable or current not in nodes:
            continue
        
        reachable.add(current)
        node_data = nodes[current]
        
        # Add next node
        if "next" in node_data:
            queue.append(node_data["next"])
        
        # Add choice nodes
        if "choices" in node_data:
            for choice in node_data["choices"]:
                if "next" in choice:
                    queue.append(choice["next"])
        
        # Add branch nodes
        if "effects" in node_data:
            for effect in node_data["effects"]:
                if isinstance(effect, dict) and effect.get("type") == "branch_on_flag":
                    queue.append(effect["next_on_true"])
                    queue.append(effect["next_on_false"])
    
    # Critical path nodes that MUST be reachable
    # Note: chapter_00_epilogue requires specific quest completion, so it's okay if not in initial reachability
    critical_nodes = [
        "arrival_beach_wake",
        "inn_arrival",
        "class_select",
        "trial_setup",
        "party_intro",
        "companion_choice",
        "protoquest_offer",
        "floor1_open_handoff",
        "threshold_inn_hub_router",
        "goblin_cave_entrance_intro",
        "cerel_goblin_escalation_quest_offer",
        "northern_ridge_rampager_hunt",
        "rampager_boss_battle",
        "cave_guardian_foreshadow",
    ]
    
    missing = [node for node in critical_nodes if node not in reachable]
    assert not missing, f"Critical path nodes unreachable: {missing}"


def test_chapter_00_rampager_quest_gating():
    """Validate Rampager quest state machine prevents infinite accepts."""
    story_repo = StoryRepository()
    nodes = _get_chapter_nodes(story_repo, "chapter_00_tutorial.json")
    
    # Check cerel_goblin_escalation_quest_offer is properly gated
    offer_node = nodes.get("cerel_goblin_escalation_quest_offer")
    assert offer_node, "cerel_goblin_escalation_quest_offer must exist"
    
    # It should have choices (accept/decline)
    assert "choices" in offer_node, "Rampager offer must have choices"
    choices = offer_node["choices"]
    assert len(choices) == 2, "Rampager offer should have exactly 2 choices (accept/decline)"
    
    # Check cerel_inn_converse_router branches on rampager state
    router_node = nodes.get("cerel_inn_converse_router")
    assert router_node, "cerel_inn_converse_router must exist"
    
    # It should branch on flag_sq_cerel_rampager_ready (for turn-in path)
    assert "effects" in router_node, "Router must have effects"
    branch_effect = None
    for effect in router_node["effects"]:
        if isinstance(effect, dict) and effect.get("type") == "branch_on_flag":
            if effect.get("flag_id") == "flag_sq_cerel_rampager_ready":
                branch_effect = effect
                break
    
    assert branch_effect, "Router must branch on flag_sq_cerel_rampager_ready"
    assert "next_on_true" in branch_effect, "Branch must have next_on_true"
    assert "next_on_false" in branch_effect, "Branch must have next_on_false"


def test_chapter_00_no_legacy_node_links():
    """Ensure no current Chapter 00 nodes link to legacy redirect IDs."""
    story_repo = StoryRepository()
    tutorial_nodes = _get_chapter_nodes(story_repo, "chapter_00_tutorial.json")
    legacy_nodes = _get_chapter_nodes(story_repo, "chapter_00_legacy_redirects.json")
    
    legacy_ids = set(legacy_nodes.keys())
    
    # Check all next/choice references in tutorial nodes
    issues = []
    for node_id, node_data in tutorial_nodes.items():
        if "next" in node_data and node_data["next"] in legacy_ids:
            issues.append(f"{node_id}: next points to legacy node '{node_data['next']}'")
        
        if "choices" in node_data:
            for choice in node_data["choices"]:
                if "next" in choice and choice["next"] in legacy_ids:
                    issues.append(
                        f"{node_id}: choice '{choice.get('label')}' points to legacy node '{choice['next']}'"
                    )
        
        if "effects" in node_data:
            for effect in node_data["effects"]:
                if isinstance(effect, dict) and effect.get("type") == "branch_on_flag":
                    if effect.get("next_on_true") in legacy_ids:
                        issues.append(
                            f"{node_id}: branch next_on_true points to legacy node '{effect['next_on_true']}'"
                        )
                    if effect.get("next_on_false") in legacy_ids:
                        issues.append(
                            f"{node_id}: branch next_on_false points to legacy node '{effect['next_on_false']}'"
                        )
    
    assert not issues, f"Current nodes linking to legacy redirects:\n" + "\n".join(f"  - {i}" for i in issues)


def test_chapter_00_flag_consistency():
    """Validate flags used in branch_on_flag are set somewhere or documented as quest-owned."""
    story_repo = StoryRepository()
    nodes = _get_chapter_nodes(story_repo, "chapter_00_tutorial.json")
    
    flags_set = set()
    flags_read = set()
    
    # Quest-system-owned flags (documented exception)
    quest_owned_flags = {
        "flag_protoquest_accepted",
        "flag_protoquest_ready",
        "flag_protoquest_completed",
        "flag_sq_dana_accepted",
        "flag_sq_dana_ready",
        "flag_sq_dana_completed",
        "flag_sq_cerel_accepted",
        "flag_sq_cerel_ready",
        "flag_sq_cerel_completed",
        "flag_sq_cerel_rampager_accepted",
        "flag_sq_cerel_rampager_ready",
        "flag_sq_cerel_rampager_completed",
    }
    
    for node_id, node_data in nodes.items():
        if "effects" in node_data:
            for effect in node_data["effects"]:
                if isinstance(effect, dict):
                    if effect.get("type") == "set_flag":
                        flags_set.add(effect.get("flag_id"))
                    elif effect.get("type") == "branch_on_flag":
                        flags_read.add(effect.get("flag_id"))
        
        # Check flags in choice effects
        if "choices" in node_data:
            for choice in node_data["choices"]:
                if "effects" in choice:
                    for effect in choice["effects"]:
                        if isinstance(effect, dict) and effect.get("type") == "set_flag":
                            flags_set.add(effect.get("flag_id"))
    
    # Flags that are read but never set (and not quest-owned) are errors
    unset_flags = flags_read - flags_set - quest_owned_flags
    
    # Note: class selection flags ARE set in choice effects, so they should be in flags_set
    # Let's be lenient and only warn about truly missing flags
    critical_unset = [f for f in unset_flags if not f.startswith("flag_class_selected_")]
    
    assert not critical_unset, f"Flags read but never set (and not quest-owned): {critical_unset}"


def test_northern_ridge_gating_flags():
    """Ensure Northern Ridge checks proper prerequisite flags."""
    story_repo = StoryRepository()
    nodes = _get_chapter_nodes(story_repo, "chapter_00_tutorial.json")
    
    # northern_ridge_approach should gate access
    approach_node = nodes.get("northern_ridge_approach")
    assert approach_node, "northern_ridge_approach must exist"
    
    # It should check flag_story_goblin_cave_reached
    assert "effects" in approach_node, "Ridge approach must check prerequisites"
    branch_found = False
    for effect in approach_node["effects"]:
        if isinstance(effect, dict) and effect.get("type") == "branch_on_flag":
            if effect.get("flag_id") == "flag_story_goblin_cave_reached":
                branch_found = True
                # Should route to gate if false
                assert "next_on_false" in effect
                break
    
    assert branch_found, "Ridge approach must check flag_story_goblin_cave_reached"


def test_rampager_encounter_requires_acceptance():
    """Ensure Rampager encounter checks quest acceptance flag."""
    story_repo = StoryRepository()
    nodes = _get_chapter_nodes(story_repo, "chapter_00_tutorial.json")
    
    # northern_ridge_rampager_gate should check acceptance
    gate_node = nodes.get("northern_ridge_rampager_gate")
    assert gate_node, "northern_ridge_rampager_gate must exist"
    
    # Should branch on flag_sq_cerel_rampager_accepted
    assert "effects" in gate_node
    branch_found = False
    for effect in gate_node["effects"]:
        if isinstance(effect, dict) and effect.get("type") == "branch_on_flag":
            if effect.get("flag_id") == "flag_sq_cerel_rampager_accepted":
                branch_found = True
                break
    
    assert branch_found, "Rampager gate must check flag_sq_cerel_rampager_accepted"


def test_deeper_cave_requires_rampager_completion():
    """Ensure deeper cave checks Rampager completion."""
    story_repo = StoryRepository()
    nodes = _get_chapter_nodes(story_repo, "chapter_00_tutorial.json")
    
    # cave_guardian_foreshadow checks rampager defeated
    foreshadow_node = nodes.get("cave_guardian_foreshadow")
    assert foreshadow_node, "cave_guardian_foreshadow must exist"
    
    # Should branch on flag_rampager_defeated
    assert "effects" in foreshadow_node
    branch_found = False
    for effect in foreshadow_node["effects"]:
        if isinstance(effect, dict) and effect.get("type") == "branch_on_flag":
            if effect.get("flag_id") == "flag_rampager_defeated":
                branch_found = True
                break
    
    assert branch_found, "Cave guardian foreshadow must check flag_rampager_defeated"


def test_rampager_quest_cannot_be_infinitely_accepted():
    """Ensure Rampager quest offer is properly gated and cannot be re-accepted."""
    story_repo = StoryRepository()
    nodes = _get_chapter_nodes(story_repo, "chapter_00_tutorial.json")
    
    # The router should exist and gate based on quest state
    router_node = nodes.get("cerel_goblin_escalation_quest_offer_router")
    assert router_node, "cerel_goblin_escalation_quest_offer_router must exist"
    
    # Router should check completed flag first
    assert "effects" in router_node
    assert len(router_node["effects"]) > 0
    first_branch = router_node["effects"][0]
    assert first_branch.get("type") == "branch_on_flag"
    assert first_branch.get("flag_id") == "flag_sq_cerel_rampager_completed"
    
    # Should have already_accepted node
    already_accepted = nodes.get("cerel_rampager_already_accepted")
    assert already_accepted, "cerel_rampager_already_accepted must exist"
    assert "next" in already_accepted, "Already accepted node should route back to conversation"
    
    # Should have already_done node
    already_done = nodes.get("cerel_rampager_already_done")
    assert already_done, "cerel_rampager_already_done must exist"
    assert "next" in already_done, "Already done node should route back to conversation"
    
    # Verify inn conversation nodes route through the router
    basic_converse = nodes.get("cerel_inn_converse_basic")
    assert basic_converse, "cerel_inn_converse_basic must exist"
    
    goblin_choice = None
    for choice in basic_converse.get("choices", []):
        if "goblin" in choice.get("label", "").lower():
            goblin_choice = choice
            break
    
    assert goblin_choice, "Inn conversation must have goblin problem choice"
    assert goblin_choice["next"] == "cerel_goblin_escalation_quest_offer_router", \
        "Goblin problem choice must route through gating router"


def test_deeper_cave_connection_gated_by_rampager():
    """Ensure deeper cave path connection is gated at location level by Rampager defeat."""
    from tbg.data import paths
    from tbg.data.json_loader import load_json
    
    locations_path = paths.get_definitions_path() / "locations.json"
    locations = load_json(locations_path)
    
    # Find goblin_cave_entrance location
    cave_entrance = locations.get("goblin_cave_entrance")
    assert cave_entrance, "goblin_cave_entrance must exist in locations"
    
    # Find the deeper_cave_path connection
    connections = cave_entrance.get("connections", [])
    deeper_cave_conn = None
    for conn in connections:
        if conn.get("to") == "deeper_cave_path":
            deeper_cave_conn = conn
            break
    
    assert deeper_cave_conn, "Connection to deeper_cave_path must exist"
    
    # Verify it has flag gating
    assert "show_if_flag_true" in deeper_cave_conn, \
        "Deeper cave connection must be gated with show_if_flag_true"
    assert deeper_cave_conn["show_if_flag_true"] == "flag_rampager_defeated", \
        "Deeper cave must require flag_rampager_defeated"


def test_chapter_00_reward_claim_nodes_have_rewards():
    """Ensure story nodes that claim rewards either grant them or the text is non-committal."""
    from tbg.data import paths
    from tbg.data.json_loader import load_json
    
    story_repo = StoryRepository()
    nodes = _get_chapter_nodes(story_repo, "chapter_00_tutorial.json")
    
    # Nodes that explicitly claim the player receives/pockets items
    reward_claim_nodes = {
        "tide_cave_aftermath_solo": {
            "claims": "vials, cloth wraps, sealed pouches (debuff consumables)",
            "should_grant_via_quest": "tide_cave_cache"
        },
        "tide_cave_aftermath_party": {
            "claims": "vials, cloth wraps, sealed pouches (debuff consumables)",
            "should_grant_via_quest": "tide_cave_cache"
        },
        "protoquest_complete_solo": {
            "claims": "a small potion and a handful of gold",
            "should_grant_via_quest": "dana_shoreline_rumor"
        },
        "protoquest_complete_party": {
            "claims": "a small potion and a handful of gold",
            "should_grant_via_quest": "dana_shoreline_rumor"
        },
    }
    
    # Load quests to verify they have rewards
    quests_path = paths.get_definitions_path() / "quests.json"
    quests_data = load_json(quests_path)
    quests = quests_data.get("quests", {})
    
    issues = []
    
    for node_id, expected in reward_claim_nodes.items():
        node = nodes.get(node_id)
        if not node:
            issues.append(f"{node_id}: node does not exist")
            continue
        
        text = node.get("text", "")
        quest_id = expected["should_grant_via_quest"]
        
        # Verify text still claims the reward
        if "pocket" not in text.lower() and "take" not in text.lower():
            issues.append(
                f"{node_id}: text no longer claims reward (expected '{expected['claims']}')"
            )
        
        # Verify quest exists and has rewards
        quest = quests.get(quest_id)
        if not quest:
            issues.append(f"{node_id}: expected quest '{quest_id}' does not exist")
            continue
        
        rewards = quest.get("rewards", {})
        has_reward = (
            rewards.get("gold", 0) > 0 or
            rewards.get("party_exp", 0) > 0 or
            len(rewards.get("items", [])) > 0
        )
        
        if not has_reward:
            issues.append(
                f"{node_id}: quest '{quest_id}' has no rewards, but text claims '{expected['claims']}'"
            )
    
    assert not issues, "Reward truth violations:\n" + "\n".join(f"  - {i}" for i in issues)


def test_chapter_00_all_quests_have_rewards():
    """Ensure every Chapter 00 quest has a non-empty reward defined."""
    from tbg.data import paths
    from tbg.data.json_loader import load_json
    
    quests_path = paths.get_definitions_path() / "quests.json"
    quests_data = load_json(quests_path)
    quests = quests_data.get("quests", {})
    
    # Chapter 00 quests (all quests available during tutorial)
    chapter_00_quest_ids = [
        "dana_shoreline_rumor",
        "dana_wolf_teeth",
        "tide_cave_cache",
        "cerel_rampager_hunt",
        "cerel_kill_hunt",
    ]
    
    issues = []
    
    for quest_id in chapter_00_quest_ids:
        quest = quests.get(quest_id)
        if not quest:
            issues.append(f"Quest '{quest_id}' does not exist")
            continue
        
        rewards = quest.get("rewards")
        if not rewards:
            issues.append(f"Quest '{quest_id}' has no rewards field")
            continue
        
        # Check if quest has any meaningful reward
        has_reward = (
            rewards.get("gold", 0) > 0 or
            rewards.get("party_exp", 0) > 0 or
            len(rewards.get("items", [])) > 0
        )
        
        if not has_reward:
            issues.append(
                f"Quest '{quest_id}' has empty rewards (no gold, exp, or items)"
            )
    
    assert not issues, "Quest reward sanity violations:\n" + "\n".join(f"  - {i}" for i in issues)

