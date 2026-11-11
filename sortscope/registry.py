"""Registry: algorithm name -> sort function + metadata (M1, owner: Ingeet).

The benchmark, visualizer, menu and tests all look algorithms up here, so a
name like ``"quick_random"`` means the same thing everywhere.

Random-pivot reproducibility: sort functions take no seed (shared interface)
and there is no global RNG. Instead :func:`get_sort` builds a fresh
``random.Random(seed)`` and binds it, so the same (name, seed) always yields
the same pivots and therefore the same counts.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from functools import partial
from typing import Callable

from sortscope.algorithms import bubble_sort, insertion_sort, merge_sort, quick_sort, selection_sort
from sortscope.counter import OpCounter

SortFn = Callable[[list, OpCounter], None]


@dataclass(frozen=True)
class SortInfo:
    """Metadata for one algorithm: label, complexity classes, stability, and how to build it."""
    name: str
    label: str
    time_best: str
    time_avg: str
    time_worst: str
    space: str
    stable: bool
    # Takes a seed and returns a ready-to-call sort_fn(arr, counter).
    factory: Callable[[int], SortFn]


def _fixed(fn: SortFn) -> Callable[[int], SortFn]:
    return lambda seed: fn


def _quick(pivot: str) -> Callable[[int], SortFn]:
    if pivot == "random":
        return lambda seed: partial(quick_sort, pivot="random", rng=random.Random(seed))
    return lambda seed: partial(quick_sort, pivot=pivot)


ALGORITHMS: dict[str, SortInfo] = {
    info.name: info
    for info in [
        SortInfo("bubble", "Bubble (early exit)", "n", "n^2", "n^2", "1", True, _fixed(bubble_sort)),
        SortInfo("selection", "Selection", "n^2", "n^2", "n^2", "1", False, _fixed(selection_sort)),
        SortInfo("insertion", "Insertion", "n", "n^2", "n^2", "1", True, _fixed(insertion_sort)),
        SortInfo("merge", "Merge", "n log n", "n log n", "n log n", "n", True, _fixed(merge_sort)),
        SortInfo("quick_first", "Quick (first pivot)", "n log n", "n log n", "n^2", "log n", False, _quick("first")),
        SortInfo("quick_random", "Quick (random pivot)", "n log n", "n log n", "n^2", "log n", False, _quick("random")),
        SortInfo("quick_median3", "Quick (median-of-3)", "n log n", "n log n", "n^2", "log n", False, _quick("median3")),
    ]
}

QUADRATIC = ("bubble", "selection", "insertion")
QUICK_VARIANTS = ("quick_first", "quick_random", "quick_median3")


def names() -> list[str]:
    """Registered algorithm names, in report order."""
    return list(ALGORITHMS)


def get_info(name: str) -> SortInfo:
    """Metadata for ``name``; KeyError listing the valid names if unknown."""
    try:
        return ALGORITHMS[name]
    except KeyError:
        raise KeyError(f"unknown algorithm {name!r}; choose from {names()}") from None


def get_sort(name: str, seed: int = 0) -> SortFn:
    """Return ``sort_fn(arr, counter)`` for ``name``; ``seed`` only affects ``quick_random``."""
    return get_info(name).factory(seed)
