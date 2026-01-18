"""Shared CLI rendering helpers."""
from __future__ import annotations

import os
import textwrap
from typing import Iterable, Sequence


def debug_enabled() -> bool:
    """Return True only when TBG_DEBUG is explicitly set to '1'."""
    return os.getenv("TBG_DEBUG") == "1"


def wrap_text_for_box(text: str, width: int, *, indent_continuation: bool = True) -> list[str]:
    """
    Wrap text to fit within a fixed width, breaking on word boundaries.
    
    Args:
        text: The text to wrap
        width: Maximum width per line
        indent_continuation: If True, indent continuation lines with 2 spaces
    
    Returns:
        List of wrapped lines, each <= width characters
    """
    if not text or width <= 0:
        return [text] if text else [""]
    
    # Handle bullet-prefixed lines specially
    if text.startswith("- "):
        # Extract the prefix and content
        prefix = "- "
        content = text[2:]
        subsequent_indent = "  " if indent_continuation else ""
        
        # Use textwrap for proper word-boundary wrapping
        wrapped = textwrap.fill(
            content,
            width=width - len(prefix),
            initial_indent="",
            subsequent_indent=subsequent_indent,
            break_long_words=False,
            break_on_hyphens=False
        )
        
        # Add the prefix back to the first line
        lines = wrapped.split('\n')
        if lines:
            lines[0] = prefix + lines[0]
            # Add indent to continuation lines if enabled
            if indent_continuation and len(lines) > 1:
                for i in range(1, len(lines)):
                    lines[i] = "  " + lines[i]
        return lines
    else:
        # No bullet prefix, wrap normally
        subsequent_indent = "  " if indent_continuation else ""
        wrapped = textwrap.fill(
            text,
            width=width,
            initial_indent="",
            subsequent_indent=subsequent_indent,
            break_long_words=False,
            break_on_hyphens=False
        )
        return wrapped.split('\n')


def render_heading(title: str) -> None:
    """Print a consistent section heading."""
    print(f"\n=== {title} ===")


def render_story(segments: Sequence[tuple[str, str]]) -> None:
    """Render story narration segments with optional node ids."""
    if not segments:
        return
    render_heading("Story")
    for idx, (node_id, text) in enumerate(segments):
        if debug_enabled():
            print(f"[{node_id}]")
        print(text)
        if idx < len(segments) - 1:
            print("\n---")


def render_choices(choices: Sequence[str]) -> None:
    """Display numbered story choices."""
    if not choices:
        return
    render_heading("Choices")
    for idx, label in enumerate(choices, start=1):
        print(f"{idx}. {label}")


def render_events_header() -> None:
    """Start an events block."""
    render_heading("Events")


def render_menu(title: str, options: Sequence[str]) -> None:
    """Display a menu section with numbered options."""
    render_heading(title)
    for idx, label in enumerate(options, start=1):
        print(f"{idx}. {label}")


def render_bullet_lines(lines: Iterable[str]) -> None:
    """Print bullet-prefixed lines."""
    for line in lines:
        print(f"- {line}")



