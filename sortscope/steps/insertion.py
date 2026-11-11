"""Insertion Sort as an event generator — mirrors algorithms/insertion.py."""

from __future__ import annotations

from typing import Iterator

from sortscope.steps.quick import Event


def insertion_steps(arr: list[int]) -> Iterator[Event]:
    """Yield the animation events of Insertion Sort on a copy of ``arr``.

    Same algorithm and same counts as ``algorithms.insertion.insertion_sort``:
    write events = inversions + (n-1); no swap events (it shifts instead).
    Time: best Θ(n) (sorted), average/worst Θ(n²) — precisely Θ(n + inversions).
    Extra space: Θ(1) for the sort itself (plus the copy).
    """
    a = list(arr)
    for i in range(1, len(a)):
        key = a[i]
        j = i - 1
        # Counted version: `while j >= 0 and counter.less(key, a[j])`.
        # Split into two lines here so the compare event comes before the test.
        # While shifting, the key is "in hand"; it belongs in the hole at j+1,
        # so the comparison is shown between positions j+1 and j.
        while j >= 0:
            yield ("compare", j + 1, j)
            if not key < a[j]:
                break
            a[j + 1] = a[j]                        # counter.write(a, j+1, a[j])  (shift)
            yield ("write", j + 1, a[j])
            j -= 1
        a[j + 1] = key                             # counter.write(a, j+1, key)   (place)
        yield ("write", j + 1, key)
    # Insertion Sort only knows positions are final once it has finished.
    for k in range(len(a)):
        yield ("sorted", k)
