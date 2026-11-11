"""Generator versions of each sort that yield animation events (M3, owner: Anup).

Each ``*_steps(arr)`` generator mirrors the counted version in
``sortscope/algorithms/`` line for line: wherever the counted version calls
``counter.less(x, y)`` the step version yields ``("compare", i, j)`` and then
evaluates ``x < y``; wherever it calls ``counter.swap`` / ``counter.write`` the
step version performs the same assignment and yields the event. That is what
makes ``tests/test_steps_equivalence.py`` able to prove both versions do the
same work.

Events (all indices refer to the array being sorted):

* ``("compare", i, j)`` — one key comparison involving positions i and j.
  (Insertion Sort: i is the "hole" where the held key would go. Quick Sort:
  one side is the pivot's current position.)
* ``("swap", i, j)``    — arr[i] and arr[j] exchanged (= 1 swap, 2 writes).
* ``("write", i, v)``   — arr[i] = v (= 1 write).
* ``("sorted", i)``     — position i holds its final value. Emitted exactly once
  per index.
* ``("pivot", i)``      — Quick Sort: the pivot element is now at position i;
  ``("pivot", -1)`` means the partition finished (no active pivot).

Counting from events: comparisons = #compare, swaps = #swap,
writes = #write + 2·#swap. Generators work on their own copy of ``arr``, so
the caller's list is not modified; replaying swap/write events on a copy of the
input reproduces every intermediate state.
"""

from __future__ import annotations

import random
from typing import Callable, Iterator

from sortscope.steps.bubble import bubble_steps
from sortscope.steps.insertion import insertion_steps
from sortscope.steps.merge import merge_steps
from sortscope.steps.quick import Event, quick_steps
from sortscope.steps.selection import selection_steps

StepsFn = Callable[[list[int]], Iterator[Event]]


def _quick(pivot: str) -> Callable[[int], StepsFn]:
    if pivot == "random":
        # Same construction as registry.get_sort -> same pivots for the same seed.
        return lambda seed: (lambda arr: quick_steps(arr, "random", random.Random(seed)))
    return lambda seed: (lambda arr: quick_steps(arr, pivot))


_STEPS: dict[str, Callable[[int], StepsFn]] = {
    "bubble": lambda seed: bubble_steps,
    "selection": lambda seed: selection_steps,
    "insertion": lambda seed: insertion_steps,
    "merge": lambda seed: merge_steps,
    "quick_first": _quick("first"),
    "quick_random": _quick("random"),
    "quick_median3": _quick("median3"),
}


def step_names() -> list[str]:
    """Algorithm names that have a step generator (same as the registry)."""
    return list(_STEPS)


def get_steps(name: str, seed: int = 0) -> StepsFn:
    """Return ``steps_fn(arr) -> iterator of events`` for a registry name."""
    try:
        return _STEPS[name](seed)
    except KeyError:
        raise KeyError(f"unknown algorithm {name!r}; choose from {step_names()}") from None


__all__ = [
    "Event", "StepsFn", "get_steps", "step_names",
    "bubble_steps", "insertion_steps", "merge_steps", "quick_steps", "selection_steps",
]
