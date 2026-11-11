"""Top-down Merge Sort as an event generator — mirrors algorithms/merge.py."""

from __future__ import annotations

from typing import Iterator

from sortscope.steps.quick import Event


def merge_steps(arr: list[int]) -> Iterator[Event]:
    """Yield the animation events of top-down Merge Sort on a copy of ``arr``.

    Same algorithm and same counts as ``algorithms.merge.merge_sort``: copies into the
    scratch buffer are not shown (not writes into the array); each copy-back is a write event,
    n⌈lg n⌉ - 2^⌈lg n⌉ + n of them for any input.
    Time: Θ(n log n) best/average/worst. Extra space: Θ(n) scratch buffer + Θ(log n) recursion.
    """
    a = list(arr)
    n = len(a)
    if n >= 2:
        aux: list = [None] * n
        yield from _merge_sort(a, aux, 0, n - 1)
    # Merge Sort knows nothing is final until the top-level merge is done.
    for k in range(n):
        yield ("sorted", k)


def _merge_sort(a: list, aux: list, lo: int, hi: int) -> Iterator[Event]:
    if lo >= hi:
        return
    mid = (lo + hi) // 2
    yield from _merge_sort(a, aux, lo, mid)
    yield from _merge_sort(a, aux, mid + 1, hi)
    yield from _merge(a, aux, lo, mid, hi)


def _merge(a: list, aux: list, lo: int, mid: int, hi: int) -> Iterator[Event]:
    i, j, k = lo, mid + 1, lo
    while i <= mid and j <= hi:
        yield ("compare", j, i)                    # counter.less(a[j], a[i])
        if a[j] < a[i]:
            aux[k] = a[j]
            j += 1
        else:
            aux[k] = a[i]
            i += 1
        k += 1
    while i <= mid:
        aux[k] = a[i]
        i += 1
        k += 1
    while j <= hi:
        aux[k] = a[j]
        j += 1
        k += 1
    # Copies into aux are not shown (not writes into the array); the copy-back is.
    for k in range(lo, hi + 1):
        a[k] = aux[k]                              # counter.write(a, k, aux[k])
        yield ("write", k, aux[k])
