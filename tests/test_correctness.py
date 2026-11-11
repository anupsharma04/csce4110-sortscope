"""Every registered sort produces the same result as ``sorted()``."""

import random

import pytest

from sortscope.counter import NullCounter, OpCounter
from sortscope.registry import get_sort, names

ALL = names()


@pytest.mark.parametrize("name", ALL)
def test_matches_sorted_on_1000_random_lists(name: str) -> None:
    rng = random.Random(4110)
    for trial in range(1000):
        n = rng.randint(0, 200)
        arr = [rng.randint(-1000, 1000) for _ in range(n)]
        expected = sorted(arr)
        get_sort(name, seed=trial)(arr, OpCounter())
        assert arr == expected, f"{name} failed on trial {trial} (n={n})"


EDGE_CASES = {
    "empty": [],
    "single": [7],
    "two_sorted": [1, 2],
    "two_reversed": [2, 1],
    "two_equal": [5, 5],
    "all_equal": [4] * 50,
    "negatives": [-3, -1, -7, 0, -2, 5, -10],
    "sorted": list(range(60)),
    "reverse": list(range(60, 0, -1)),
    "many_duplicates": [3, 1, 2, 3, 1, 2, 2, 3, 1, 1, 3, 2] * 5,
    "max_at_front": [99] + list(range(30)),
    "min_at_end": list(range(1, 31)) + [0],
}


@pytest.mark.parametrize("name", ALL)
@pytest.mark.parametrize("case", list(EDGE_CASES))
def test_edge_cases(name: str, case: str) -> None:
    arr = list(EDGE_CASES[case])
    expected = sorted(arr)
    get_sort(name)(arr, OpCounter())
    assert arr == expected


@pytest.mark.parametrize("name", ALL)
def test_sorts_in_place_and_returns_none(name: str) -> None:
    arr = [3, 1, 2]
    same = arr
    assert get_sort(name)(arr, OpCounter()) is None
    assert same is arr and arr == [1, 2, 3]


@pytest.mark.parametrize("name", ALL)
def test_null_counter_gives_same_result(name: str) -> None:
    rng = random.Random(1)
    for _ in range(50):
        arr = [rng.randint(-50, 50) for _ in range(rng.randint(0, 100))]
        a, b = list(arr), list(arr)
        get_sort(name, seed=7)(a, OpCounter())
        get_sort(name, seed=7)(b, NullCounter())
        assert a == b == sorted(arr)
