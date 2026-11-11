"""Rule 3 ("two implementations, one truth"): the step generators and the
counted sorts do the same work.

For every algorithm and 300 seeded inputs of every input kind (plus random lists
with negatives), replaying the events on a copy of the input must give the same
final array as the counted version, and the event counts must equal the
OpCounter values exactly.
"""

from __future__ import annotations

import random
import zlib

import pytest

from sortscope.counter import OpCounter
from sortscope.inputs import generate, input_kinds
from sortscope.registry import get_sort, names
from sortscope.steps import get_steps, step_names


def replay(arr: list[int], events) -> tuple[list[int], dict[str, int], list[int]]:
    """Apply swap/write events to a copy of arr; return (final, counts, sorted indices)."""
    a = list(arr)
    counts = {"comparisons": 0, "swaps": 0, "writes": 0}
    final_marks: list[int] = []
    n = len(a)
    for ev in events:
        kind = ev[0]
        if kind == "compare":
            _, i, j = ev
            assert 0 <= i < n and 0 <= j < n
            counts["comparisons"] += 1
        elif kind == "swap":
            _, i, j = ev
            a[i], a[j] = a[j], a[i]
            counts["swaps"] += 1
            counts["writes"] += 2
        elif kind == "write":
            _, i, v = ev
            a[i] = v
            counts["writes"] += 1
        elif kind == "sorted":
            final_marks.append(ev[1])
        elif kind == "pivot":
            assert -1 <= ev[1] < n
        else:
            raise AssertionError(f"unknown event {ev!r}")
    return a, counts, final_marks


def inputs_for(kind: str, count: int = 300):
    # zlib.crc32, not hash(): str hashes are salted per process (PYTHONHASHSEED),
    # which would make the tested sizes differ from run to run.
    rng = random.Random(zlib.crc32(kind.encode()))
    for s in range(count):
        n = rng.randint(0, 60)
        yield s, generate(kind, n, seed=s)


def test_same_algorithm_names() -> None:
    assert step_names() == names()


@pytest.mark.parametrize("name", names())
@pytest.mark.parametrize("kind", input_kinds() + ["random_with_negatives"])
def test_steps_match_counted_version(name: str, kind: str) -> None:
    if kind == "random_with_negatives":
        rng = random.Random(11)
        cases = [(s, [rng.randint(-30, 30) for _ in range(rng.randint(0, 60))]) for s in range(300)]
    else:
        cases = list(inputs_for(kind))
    for seed, arr in cases:
        original = list(arr)
        counted = list(arr)
        c = OpCounter()
        get_sort(name, seed=seed)(counted, c)

        final, counts, marks = replay(arr, get_steps(name, seed=seed)(arr))

        assert arr == original, "step generator must not modify its input"
        assert final == counted == sorted(original)
        assert counts == {"comparisons": c.comparisons, "swaps": c.swaps, "writes": c.writes}
        # Every index is announced final exactly once.
        assert sorted(marks) == list(range(len(arr)))


@pytest.mark.parametrize("name", names())
def test_sorted_marks_are_truthful(name: str) -> None:
    """When ("sorted", i) is emitted, position i already holds its final value."""
    rng = random.Random(5)
    for s in range(100):
        arr = [rng.randint(0, 20) for _ in range(rng.randint(0, 40))]
        target = sorted(arr)
        a = list(arr)
        for ev in get_steps(name, seed=s)(arr):
            if ev[0] == "swap":
                a[ev[1]], a[ev[2]] = a[ev[2]], a[ev[1]]
            elif ev[0] == "write":
                a[ev[1]] = ev[2]
            elif ev[0] == "sorted":
                assert a[ev[1]] == target[ev[1]]
