"""Stability: Bubble/Insertion/Merge keep equal keys in order; Selection/Quick are shown unstable.

Records compare by key only (``__lt__`` ignores ``idx``), and every sort compares
only through ``counter.less`` -> ``<``, so ``idx`` reveals the final order of ties.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import pytest

from sortscope.counter import OpCounter
from sortscope.registry import get_info, get_sort, names


@dataclass(frozen=True, eq=False)
class Rec:
    key: int
    idx: int

    def __lt__(self, other: "Rec") -> bool:
        return self.key < other.key


def records(keys: list[int]) -> list[Rec]:
    return [Rec(k, i) for i, k in enumerate(keys)]


def is_stable_result(out: list[Rec]) -> bool:
    """Sorted by key, and equal keys appear in increasing original index."""
    return all(
        (a.key, a.idx) < (b.key, b.idx) for a, b in zip(out, out[1:])
    )


STABLE = [n for n in names() if get_info(n).stable]
UNSTABLE = [n for n in names() if not get_info(n).stable]


def test_registry_stability_flags_match_proposal() -> None:
    assert set(STABLE) == {"bubble", "insertion", "merge"}
    assert set(UNSTABLE) == {"selection", "quick_first", "quick_random", "quick_median3"}


@pytest.mark.parametrize("name", STABLE)
def test_stable_sorts_keep_equal_keys_in_order(name: str) -> None:
    rng = random.Random(99)
    for _ in range(300):
        n = rng.randint(0, 120)
        arr = records([rng.randint(0, 9) for _ in range(n)])  # lots of ties
        get_sort(name)(arr, OpCounter())
        assert is_stable_result(arr)


@pytest.mark.parametrize(
    "name, keys, expected_idx",
    [
        # Long-distance swap of 2a with 1 jumps it over 2b.
        ("selection", [2, 2, 1], [2, 1, 0]),
        # Hoare stops on keys equal to the pivot and swaps them.
        ("quick_first", [1, 1], [1, 0]),
        ("quick_median3", [1, 1], [1, 0]),
    ],
)
def test_known_counterexamples_show_instability(name: str, keys: list[int], expected_idx: list[int]) -> None:
    arr = records(keys)
    get_sort(name)(arr, OpCounter())
    assert [r.idx for r in arr] == expected_idx
    assert not is_stable_result(arr)


def test_quick_random_is_unstable_for_some_seed() -> None:
    # Whether [1a, 1b] flips depends on the random pivot, so we show that a
    # fixed, deterministic set of seeds contains a counterexample.
    flipped = []
    for seed in range(20):
        arr = records([1, 1])
        get_sort("quick_random", seed=seed)(arr, OpCounter())
        if not is_stable_result(arr):
            flipped.append(seed)
    assert flipped, "expected at least one seed to reorder equal keys"
