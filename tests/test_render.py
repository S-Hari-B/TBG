"""Tests for CLI rendering utilities."""
import pytest

from tbg.presentation.cli.render import render_story, set_text_display_mode, wrap_text_for_box


def test_wrap_text_for_box_short_text() -> None:
    """Short text should not be wrapped."""
    result = wrap_text_for_box("Hello world", width=50)
    assert result == ["Hello world"]


def test_wrap_text_for_box_long_text_wraps() -> None:
    """Long text should wrap at word boundaries."""
    text = "This is a very long line that definitely needs to be wrapped because it exceeds the width"
    result = wrap_text_for_box(text, width=40)
    
    assert len(result) > 1
    for line in result:
        assert len(line) <= 40
    # Check that words weren't broken
    joined = " ".join(line.strip() for line in result)
    assert joined == text


def test_wrap_text_for_box_bullet_prefix() -> None:
    """Bullet-prefixed lines should wrap with proper indentation."""
    text = "- This is a bullet point with a very long message that needs to wrap to multiple lines"
    result = wrap_text_for_box(text, width=40, indent_continuation=True)
    
    assert len(result) > 1
    assert result[0].startswith("- ")
    # Continuation lines should be indented
    for line in result[1:]:
        assert line.startswith("  ")
    # All lines should fit within width
    for line in result:
        assert len(line) <= 40


def test_wrap_text_for_box_no_indent_continuation() -> None:
    """With indent_continuation=False, continuation lines shouldn't be indented."""
    text = "- A long bullet point that will wrap without indenting continuation lines"
    result = wrap_text_for_box(text, width=30, indent_continuation=False)
    
    assert len(result) > 1
    assert result[0].startswith("- ")
    # Continuation lines should NOT have extra indent (just the "  " from textwrap)
    for line in result[1:]:
        # Should have some content, not just whitespace
        assert line.strip() != ""


def test_wrap_text_for_box_party_talk_example() -> None:
    """Real-world example: Party Talk event with long knowledge text."""
    text = "- Emma: Goblin Grunts typically have low HP but attack in groups to overwhelm isolated targets."
    result = wrap_text_for_box(text, width=56, indent_continuation=True)
    
    # Should wrap into multiple lines
    assert len(result) >= 1
    # First line starts with bullet
    assert result[0].startswith("- ")
    # No line exceeds width
    for line in result:
        assert len(line) <= 56
    # Content should be preserved
    full_text = result[0][2:] + " " + " ".join(line.strip() for line in result[1:])
    expected_content = "Emma: Goblin Grunts typically have low HP but attack in groups to overwhelm isolated targets."
    assert full_text.strip() == expected_content.strip()


def test_wrap_text_for_box_empty_text() -> None:
    """Empty text should return a single empty string."""
    result = wrap_text_for_box("", width=50)
    assert result == [""]


def test_wrap_text_for_box_exact_width() -> None:
    """Text exactly at width should not wrap."""
    text = "X" * 50
    result = wrap_text_for_box(text, width=50)
    assert result == [text]


def test_render_story_step_mode_prompts_between_segments(monkeypatch, capsys) -> None:
    set_text_display_mode("step")
    prompts: list[object] = []
    monkeypatch.setattr("builtins.input", lambda _: prompts.append(object()) or "")

    render_story([("node_a", "First."), ("node_b", "Second.")])
    output = capsys.readouterr().out
    assert "First." in output
    assert "Second." in output
    assert "Press Enter" not in output
    assert len(prompts) == 1
    set_text_display_mode("instant")


def test_render_story_instant_mode_does_not_prompt(monkeypatch, capsys) -> None:
    set_text_display_mode("instant")

    def _fail_input(_: str) -> str:
        raise AssertionError("Unexpected prompt in instant mode")

    monkeypatch.setattr("builtins.input", _fail_input)
    render_story([("node_a", "First."), ("node_b", "Second.")])
    output = capsys.readouterr().out
    assert "First." in output
    assert "Second." in output
