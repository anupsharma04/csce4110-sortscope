"""Selection Sort as an event generator — mirrors algorithms/selection.py."""

from __future__ import annotations

from typing import Iterator

from sortscope.steps.quick import Event


def selection_steps(arr: list[int]) -> Iterator[Event]:
    """Yield the animation events of Selection Sort on a copy of ``arr``.

    Same algorithm and same counts as ``algorithms.selection.selection_sort``:
    exactly n(n-1)/2 compare events for every input, at most n-1 swaps.
    Time: Θ(n²) best/average/worst. Extra space: Θ(1) for the sort itself (plus the copy).
    """
    a = list(arr)
    n = len(a)
    for i in range(n - 1):
        m = i
        for j in range(i + 1, n):
            yield ("compare", j, m)                # counter.less(a[j], a[m])
            if a[j] < a[m]:
                m = j
        if m != i:
            a[i], a[m] = a[m], a[i]                # counter.swap(a, i, m)
            yield ("swap", i, m)
        yield ("sorted", i)
    if n >= 1:
        yield ("sorted", n - 1)                    # the largest is left in place
