"""Bubble Sort (early exit) as an event generator — mirrors algorithms/bubble.py."""

from __future__ import annotations

from typing import Iterator

from sortscope.steps.quick import Event


def bubble_steps(arr: list[int]) -> Iterator[Event]:
    """Yield the animation events of Bubble Sort (early exit) on a copy of ``arr``.

    Same algorithm and same counts as ``algorithms.bubble.bubble_sort``.
    Time: best Θ(n) (sorted), average/worst Θ(n²). Extra space: Θ(1) for the sort itself
    (plus the copy). Events: one per comparison/swap, so Θ(n²) events in the worst case.
    """
    a = list(arr)
    n = len(a)
    for end in range(n - 1, 0, -1):
        swapped = False
        for i in range(end):
            yield ("compare", i + 1, i)            # counter.less(a[i+1], a[i])
            if a[i + 1] < a[i]:
                a[i], a[i + 1] = a[i + 1], a[i]    # counter.swap(a, i, i+1)
                yield ("swap", i, i + 1)
                swapped = True
        yield ("sorted", end)                      # the pass carried the max to `end`
        if not swapped:
            # No swaps: a[0..end-1] is already in order -> all final.
            for k in range(end):
                yield ("sorted", k)
            return
    if n >= 1:
        yield ("sorted", 0)                        # last remaining element
