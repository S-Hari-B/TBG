"""Deterministic RNG wrapper built on top of random.Random."""
from __future__ import annotations

from random import Random
from typing import MutableSequence, Sequence, TypeVar

T_co = TypeVar("T_co")


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


