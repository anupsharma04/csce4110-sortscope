"""Quick Sort (Hoare, three pivot rules) as an event generator — mirrors algorithms/quick.py.

Extra bookkeeping only for the picture: ``ppos`` tracks where the pivot
*element* currently sits, because Hoare's swaps can move it. Compare events
involving the pivot value use ``ppos`` as one of the two indices.

How values come back out of a generator (worth knowing for the demo):
``p = yield from _hoare_partition(...)`` passes every event the partition yields
straight through to whoever is animating, and when the partition finishes with
``return j``, that ``j`` becomes the value of the ``yield from`` expression.
"""

from __future__ import annotations

import random
from typing import Callable, Iterator, Union

Event = Union[tuple[str, int], tuple[str, int, int]]
# A pivot chooser returns (pivot index, compare events it made while choosing).
_Chooser = Callable[[list, int, int], tuple[int, list[Event]]]


def quick_steps(arr: list[int], pivot: str = "first", rng: random.Random | None = None) -> Iterator[Event]:
    """Yield the animation events of Quick Sort (Hoare partition) on a copy of ``arr``.

    Same algorithm, pivot choices and counts as ``algorithms.quick.quick_sort`` (for
    ``pivot="random"`` pass a ``random.Random`` seeded the same way). Adds ("pivot", i) events.
    Time: best/average Θ(n log n), worst Θ(n²) (first pivot on sorted/reverse input).
    Extra space: Θ(log n) recursion (smaller-side recursion), plus the copy.
    """
    a = list(arr)
    chooser = _make_chooser(pivot, rng)
    yield from _quick(a, 0, len(a) - 1, chooser)


def _make_chooser(pivot: str, rng: random.Random | None) -> _Chooser:
    if pivot == "first":
        return _choose_first
    if pivot == "median3":
        return _choose_median3
    if pivot == "random":
        if rng is None:
            raise ValueError("pivot='random' needs an explicit random.Random(seed) for reproducibility")
        return lambda a, lo, hi: (rng.randrange(lo, hi + 1), [])   # same RNG call as the counted version
    raise ValueError(f"unknown pivot rule: {pivot!r}")


def _choose_first(a: list, lo: int, hi: int) -> tuple[int, list[Event]]:
    return lo, []


def _choose_median3(a: list, lo: int, hi: int) -> tuple[int, list[Event]]:
    """Median of a[lo], a[mid], a[hi], with the 2-3 comparisons it took (same branches as the
    counted version, so the same comparisons are made)."""
    if hi - lo < 2:
        return lo, []
    mid = (lo + hi) // 2
    x, y, z = a[lo], a[mid], a[hi]
    events: list[Event] = [("compare", lo, mid)]
    if x < y:
        events.append(("compare", mid, hi))
        if y < z:
            return mid, events
        events.append(("compare", lo, hi))
        return (hi if x < z else lo), events
    events.append(("compare", lo, hi))
    if x < z:
        return lo, events
    events.append(("compare", mid, hi))
    return (hi if y < z else mid), events


def _quick(a: list, lo: int, hi: int, chooser: _Chooser) -> Iterator[Event]:
    while lo < hi:
        p = yield from _hoare_partition(a, lo, hi, chooser)   # events pass through; p = returned j
        if p - lo < hi - p:
            yield from _quick(a, lo, p, chooser)
            lo = p + 1
        else:
            yield from _quick(a, p + 1, hi, chooser)
            hi = p
    # Every index ends up alone in a size-1 segment exactly once: that is
    # the moment it is known to be final (Hoare does not fix the pivot's slot).
    if lo == hi:
        yield ("sorted", lo)


def _hoare_partition(a: list, lo: int, hi: int, chooser: _Chooser) -> Iterator[Event]:
    k, choose_events = chooser(a, lo, hi)
    yield from choose_events
    yield ("pivot", k)
    if k != lo:
        a[lo], a[k] = a[k], a[lo]                  # counter.swap(a, lo, k)
        yield ("swap", lo, k)
        yield ("pivot", lo)
    ppos = lo
    pivot = a[lo]
    i = lo - 1
    j = hi + 1
    while True:
        j -= 1
        while True:                                # while counter.less(pivot, a[j])
            yield ("compare", ppos, j)
            if not pivot < a[j]:
                break
            j -= 1
        i += 1
        while True:                                # while counter.less(a[i], pivot)
            yield ("compare", i, ppos)
            if not a[i] < pivot:
                break
            i += 1
        if i < j:
            a[i], a[j] = a[j], a[i]                # counter.swap(a, i, j)
            yield ("swap", i, j)
            if ppos in (i, j):                     # the pivot element moved
                ppos = j if ppos == i else i
                yield ("pivot", ppos)
        else:
            yield ("pivot", -1)
            return j
