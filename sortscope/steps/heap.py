"""Heap Sort as an event generator — mirrors algorithms/heap.py."""

from __future__ import annotations

from typing import Iterator

from sortscope.steps.quick import Event


def heap_steps(arr: list[int]) -> Iterator[Event]:
    """Yield the animation events of Heap Sort on a copy of ``arr``.

    Same algorithm and same counts as ``algorithms.heap.heap_sort``: build a max-heap
    bottom-up, then swap the root with the last heap element n-1 times. After each of
    those root swaps the slot at the end of the heap holds its final value, so that is
    when its ("sorted", i) event is emitted.
    Time: Θ(n log n) worst/average. Extra space: Θ(1) for the sort itself (plus the copy).
    """
    a = list(arr)
    n = len(a)
    for i in range(n // 2 - 1, -1, -1):            # phase 1: build the max-heap
        yield from _sift_down(a, i, n)
    for end in range(n - 1, 0, -1):                # phase 2: extract the maximum n-1 times
        a[0], a[end] = a[end], a[0]                # counter.swap(a, 0, end)
        yield ("swap", 0, end)
        yield ("sorted", end)
        yield from _sift_down(a, 0, end)
    if n >= 1:
        yield ("sorted", 0)                        # the last remaining element


def _sift_down(a: list, i: int, size: int) -> Iterator[Event]:
    while True:
        child = 2 * i + 1
        if child >= size:
            return
        if child + 1 < size:
            yield ("compare", child, child + 1)    # counter.less(a[child], a[child+1])
            if a[child] < a[child + 1]:
                child += 1
        yield ("compare", i, child)                # counter.less(a[i], a[child])
        if not a[i] < a[child]:
            return
        a[i], a[child] = a[child], a[i]            # counter.swap(a, i, child)
        yield ("swap", i, child)
        i = child
