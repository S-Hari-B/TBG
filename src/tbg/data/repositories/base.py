"""Base repository implementation for JSON definition data."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Generic, TypeVar

from tbg.data.errors import DataValidationError
from tbg.data.json_loader import load_json
from tbg.data import paths

T = TypeVar("T")


class RepositoryBase(Generic[T]):
    """Common caching and loading behavior for repositories."""

    def __init__(self, filename: str, base_path: Path | str | None = None) -> None:
        self._filename = filename
        self._base_path = Path(base_path) if base_path is not None else None
        self._definitions: Dict[str, T] | None = None

    def _get_file_path(self) -> Path:
        definitions_dir = paths.get_definitions_path(self._base_path)
        return definitions_dir / self._filename

    def _load_raw(self) -> dict[str, object]:
        file_path = self._get_file_path()
        raw = load_json(file_path)
        if not isinstance(raw, dict):
            raise DataValidationError(f"Expected top-level object in {file_path}")
        return raw

    def _build(self, raw: dict[str, object]) -> Dict[str, T]:
        """Convert a raw dict into typed definitions."""
        raise NotImplementedError

    def _ensure_loaded(self) -> None:
        if self._definitions is None:
            raw = self._load_raw()
            self._definitions = self._build(raw)

    def get(self, def_id: str) -> T:
        """Return a definition by id."""
        self._ensure_loaded()
        assert self._definitions is not None
        try:
            return self._definitions[def_id]
        except KeyError as exc:
            raise KeyError(def_id) from exc

    def all(self) -> list[T]:
        """Return all definitions sorted deterministically by id."""
        self._ensure_loaded()
        assert self._definitions is not None
        return [self._definitions[key] for key in sorted(self._definitions.keys())]

    @staticmethod
    def _require_mapping(value: object, context: str) -> dict[str, object]:
        if not isinstance(value, dict):
            raise DataValidationError(f"{context} must be an object/dict.")
        return value

    @staticmethod
    def _require_type(value: object, expected_type: type, context: str) -> object:
        if not isinstance(value, expected_type):
            raise DataValidationError(f"{context} must be of type {expected_type.__name__}.")
        return value


