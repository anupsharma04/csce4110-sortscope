"""Property-based tests (hypothesis): for ANY list of integers, every algorithm

* returns a sorted permutation of its input,
* reports non-negative counts with writes >= 2 * swaps (a swap is 2 writes),
* reports identical counts for the same seed (counts are deterministic, so results are reproducible),
* does exactly the same work as its step-generator twin (the visualizer shows the benchmark's real work).

Hypothesis shrinks any failure to a minimal counterexample and prints it.
"""

from collections import Counter

import pytest

# hypothesis is the one test-only dependency beyond the proposal's stack. Without it this file
# is reported as skipped and the rest of the suite (which needs only pytest) still runs.
pytest.importorskip("hypothesis")

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from sortscope.counter import OpCounter
from sortscope.registry import get_sort, names
from sortscope.steps import get_steps

INTS = st.integers(min_value=-(10**18), max_value=10**18)
# Mix in small-range lists so duplicates (the hard case for Quick Sort) are common.
LISTS = st.one_of(st.lists(INTS, max_size=80), st.lists(st.integers(-3, 3), max_size=80))
SEEDS = st.integers(min_value=0, max_value=2**32 - 1)
SETTINGS = settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])


def counted(name: str, xs: list[int], seed: int) -> tuple[list[int], OpCounter]:
    a, c = list(xs), OpCounter()
    get_sort(name, seed=seed)(a, c)
    return a, c


@SETTINGS
@given(LISTS, SEEDS)
def test_sorted_permutation_and_sane_counts(xs: list[int], seed: int) -> None:
    for name in names():
        a, c = counted(name, xs, seed)
        assert a == sorted(xs), name
        assert Counter(a) == Counter(xs), name
        assert min(c.comparisons, c.swaps, c.writes, c.max_depth) >= 0, name
        assert c.writes >= 2 * c.swaps, name


@SETTINGS
@given(LISTS, SEEDS)
def test_same_seed_same_counts(xs: list[int], seed: int) -> None:
    for name in names():
        assert counted(name, xs, seed)[1].as_dict() == counted(name, xs, seed)[1].as_dict(), name


@SETTINGS
@given(LISTS, SEEDS)
def test_steps_do_the_same_work(xs: list[int], seed: int) -> None:
    for name in names():
        a, c = counted(name, xs, seed)
        replay = list(xs)
        cmp = swp = wr = 0
        for ev in get_steps(name, seed=seed)(xs):
            if ev[0] == "compare":
                cmp += 1
            elif ev[0] == "swap":
                replay[ev[1]], replay[ev[2]] = replay[ev[2]], replay[ev[1]]
                swp += 1
                wr += 2
            elif ev[0] == "write":
                replay[ev[1]] = ev[2]
                wr += 1
        assert replay == a, name
        assert (cmp, swp, wr) == (c.comparisons, c.swaps, c.writes), name
