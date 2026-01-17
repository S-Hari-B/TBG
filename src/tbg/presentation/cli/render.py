"""Shared CLI rendering helpers."""
from __future__ import annotations

import os
from typing import Iterable, Sequence


def debug_enabled() -> bool:
    """Return True only when TBG_DEBUG is explicitly set to '1'."""
    return os.getenv("TBG_DEBUG") == "1"


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



