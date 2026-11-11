"""Registry contents, seed determinism, and Quick Sort recursion depth (risk R1)."""

import math
import random

import pytest

from sortscope.algorithms.quick import quick_sort
from sortscope.counter import OpCounter
from sortscope.registry import QUICK_VARIANTS, get_sort, names


def test_registry_has_proposal_algorithms() -> None:
    assert names() == [
        "bubble", "selection", "insertion", "merge",
        "quick_first", "quick_random", "quick_median3",
    ]


def test_unknown_name_raises() -> None:
    with pytest.raises(KeyError):
        get_sort("bogo")


def test_random_pivot_requires_rng() -> None:
    with pytest.raises(ValueError):
        quick_sort([2, 1], OpCounter(), pivot="random")


def counts(name: str, arr: list[int], seed: int) -> dict[str, int]:
    c = OpCounter()
    get_sort(name, seed=seed)(list(arr), c)
    return c.as_dict()


def test_quick_random_counts_are_deterministic_per_seed() -> None:
    arr = random.Random(3).sample(range(10_000), 2000)
    assert counts("quick_random", arr, 5) == counts("quick_random", arr, 5)
    # Different seeds pick different pivots, so counts (almost surely) differ.
    assert counts("quick_random", arr, 5) != counts("quick_random", arr, 6)


@pytest.mark.parametrize("name", QUICK_VARIANTS)
@pytest.mark.parametrize("kind", ["sorted", "reverse", "all_equal", "random"])
def test_quick_depth_is_logarithmic_for_every_pivot(name: str, kind: str) -> None:
    # n=2000 > Python's default recursion limit (1000): naive recursion on the
    # first-pivot worst case would raise RecursionError here.
    n = 2000
    arr = {
        "sorted": list(range(n)),
        "reverse": list(range(n, 0, -1)),
        "all_equal": [7] * n,
        "random": random.Random(0).sample(range(n), n),
    }[kind]
    c = OpCounter()
    get_sort(name, seed=1)(arr, c)
    assert arr == sorted(arr)
    assert 1 <= c.max_depth <= math.floor(math.log2(n)) + 1
