"""Deterministic RNG wrapper built on top of random.Random."""
from __future__ import annotations

from random import Random
from typing import MutableSequence, Sequence, TypeVar, TypedDict

T_co = TypeVar("T_co")


class RNGStatePayload(TypedDict):
    """JSON-friendly snapshot of the RNG internal state."""

    version: int
    state: list[int]
    gauss: float | None


class RNG:
    """Wrapper around random.Random that provides deterministic helpers."""

    def __init__(self, seed: int) -> None:
        self._random = Random(seed)

    def randint(self, a: int, b: int) -> int:
        """Return a random integer N such that a <= N <= b."""
        return self._random.randint(a, b)

    def random(self) -> float:
        """Return the next random floating point number in the range [0.0, 1.0)."""
        return self._random.random()

    def choice(self, seq: Sequence[T_co]) -> T_co:
        """Return a random element from the non-empty sequence."""
        if not seq:
            raise ValueError("Cannot choose from an empty sequence.")
        return self._random.choice(seq)

    def shuffle(self, seq: MutableSequence[T_co]) -> None:
        """Shuffle the sequence in-place."""
        self._random.shuffle(seq)

    def export_state(self) -> RNGStatePayload:
        """Return a JSON-friendly snapshot of the underlying RNG state."""
        version, state_tuple, gauss = self._random.getstate()
        return {
            "version": int(version),
            "state": [int(value) for value in state_tuple],
            "gauss": gauss if gauss is None else float(gauss),
        }

    def restore_state(self, payload: RNGStatePayload) -> None:
        """Restore RNG internal state from a snapshot."""
        try:
            version = int(payload["version"])
            state_values = payload["state"]
            gauss = payload.get("gauss")
        except KeyError as exc:
            raise ValueError("Invalid RNG state payload (missing keys).") from exc
        if not isinstance(state_values, list):
            raise ValueError("Invalid RNG state payload (state must be a list).")
        try:
            state_tuple = tuple(int(value) for value in state_values)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid RNG state payload (state elements must be integers).") from exc
        if gauss is not None and not isinstance(gauss, (int, float)):
            raise ValueError("Invalid RNG state payload (gauss must be numeric or null).")
        gauss_value = None if gauss is None else float(gauss)
        self._random.setstate((version, state_tuple, gauss_value))


