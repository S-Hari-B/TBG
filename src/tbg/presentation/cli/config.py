"""CLI configuration helpers for options persistence."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict

_DEFAULT_TEXT_MODE = "instant"


def get_user_data_dir() -> Path:
    """Return the per-user data directory."""
    if os.name == "nt":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / "EchoesOfTheCycle"
        return Path.home() / "EchoesOfTheCycle"
    return Path.home() / ".config" / "echoes_of_the_cycle"


def get_default_config_path() -> Path:
    """Return the default per-user config path."""
    return get_user_data_dir() / "config.json"


def get_save_dir() -> Path:
    """Return the per-user save directory."""
    return get_user_data_dir() / "saves"


def _normalize_text_mode(value: object) -> str:
    return "step" if value == "step" else _DEFAULT_TEXT_MODE


def load_config(path: Path | None = None) -> Dict[str, str]:
    """Load config from disk or return defaults."""
    config_path = path or get_default_config_path()
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"text_display_mode": _DEFAULT_TEXT_MODE}
    except Exception:
        return {"text_display_mode": _DEFAULT_TEXT_MODE}
    if not isinstance(raw, dict):
        return {"text_display_mode": _DEFAULT_TEXT_MODE}
    return {"text_display_mode": _normalize_text_mode(raw.get("text_display_mode"))}


def save_config(config: Dict[str, str], path: Path | None = None) -> None:
    """Persist config to disk."""
    config_path = path or get_default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"text_display_mode": _normalize_text_mode(config.get("text_display_mode"))}
    config_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
