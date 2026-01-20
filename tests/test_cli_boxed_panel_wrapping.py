"""Integration test for boxed panel text wrapping in battle UI."""
import pytest
from unittest.mock import patch
from io import StringIO

from tbg.services.battle_service import BattleService
from tbg.services.story_service import StoryService
from tbg.data.repositories.classes_repo import ClassesRepository
from tbg.data.repositories.enemies_repo import EnemiesRepository
from tbg.data.repositories.items_repo import ItemsRepository
from tbg.data.repositories.loot_tables_repo import LootTablesRepository
from tbg.data.repositories.party_members_repo import PartyMembersRepository
from tbg.data.repositories.skills_repo import SkillsRepository
from tbg.data.repositories.story_repo import StoryRepository
from tbg.data.repositories.weapons_repo import WeaponsRepository
from tbg.data.repositories.armour_repo import ArmourRepository
from tbg.data.repositories.knowledge_repo import KnowledgeRepository
from tbg.domain.state import GameState
from tbg.presentation.cli.app import _render_boxed_panel


def test_party_talk_long_text_wraps_in_battle_ui() -> None:
    """
    Test that long Party Talk knowledge text wraps cleanly inside boxed RESULTS panel.
    
    This is a regression test for the text truncation bug where long lines were
    hard-chopped at 56 characters mid-word, breaking readability.
    """
    # Create a long knowledge-style line that would exceed 56 chars
    long_line = "- Emma: Goblin Grunts typically have low HP but attack in groups to overwhelm isolated targets and exploit numerical advantage."
    
    # Capture output
    output = StringIO()
    with patch('sys.stdout', output):
        _render_boxed_panel("RESULTS", [long_line])
    
    result = output.getvalue()
    lines = result.split('\n')
    
    # Verify borders are intact (60 chars wide)
    assert lines[0] == "+----------------------------------------------------------+"
    assert lines[-2] == "+----------------------------------------------------------+"  # last non-empty line
    
    # Verify no line exceeds 60 chars
    for line in lines:
        if line:  # skip empty lines
            assert len(line) == 60, f"Line exceeds 60 chars: {line}"
    
    # Verify content is preserved (not truncated)
    content_lines = [line for line in lines if line.startswith("| -") or line.startswith("|  ")]
    full_content = " ".join(line[2:-2].strip() for line in content_lines)
    
    expected_content = "Emma: Goblin Grunts typically have low HP but attack in groups to overwhelm isolated targets and exploit numerical advantage."
    assert expected_content in full_content or full_content.replace("  ", " ").strip().startswith("- Emma:")
    
    # Verify text was wrapped (should be multiple content lines)
    assert len(content_lines) >= 2, "Long text should wrap to multiple lines"


def test_results_panel_multiple_long_lines() -> None:
    """Test that multiple long lines in a RESULTS panel all wrap correctly."""
    lines = [
        "- Warrior uses Power Slash on Goblin Grunt Alpha for 45 damage.",
        "- Emma: Watch out for the alpha's enrage mechanic when its HP drops below 30 percent threshold.",
        "- Goblin Grunt Alpha is defeated and drops loot."
    ]
    
    output = StringIO()
    with patch('sys.stdout', output):
        _render_boxed_panel("RESULTS", lines)
    
    result = output.getvalue()
    output_lines = result.split('\n')
    
    # All lines should be exactly 60 chars (including borders)
    for line in output_lines:
        if line:
            assert len(line) == 60, f"Line length mismatch: {len(line)} != 60, line: {line}"
    
    # Should have borders + title + wrapped content
    assert output_lines[0].startswith("+---")
    assert "RESULTS" in output_lines[1]
    
    # Check that at least some wrapping occurred (should be more lines than input)
    content_lines = [l for l in output_lines if l.startswith("| -") or l.startswith("|  ")]
    assert len(content_lines) >= len(lines), "Should have at least as many output lines as input"


def test_short_text_does_not_wrap() -> None:
    """Test that short text that fits within width doesn't get unnecessarily wrapped."""
    short_line = "- Attack hits for 10 damage."
    
    output = StringIO()
    with patch('sys.stdout', output):
        _render_boxed_panel("RESULTS", [short_line])
    
    result = output.getvalue()
    lines = result.split('\n')
    
    # Should have: border + title + short_line + border = 4 non-empty lines
    non_empty = [l for l in lines if l]
    assert len(non_empty) == 4
    
    # The content line should contain the full short text
    content_line = [l for l in lines if "Attack hits" in l][0]
    assert "Attack hits for 10 damage." in content_line
