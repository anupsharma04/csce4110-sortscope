"""Bubble Sort with early exit (M1, owner: Ingeet)."""

from __future__ import annotations

from sortscope.counter import OpCounter


def bubble_sort(arr: list[int], counter: OpCounter) -> None:
    """Sort ``arr`` in place with Bubble Sort (early exit).

    Each pass bubbles the largest remaining element to the end, so the range
    shrinks by one per pass. If a pass makes no swaps the array is sorted and
    we stop.

    Time:  best Θ(n) (already sorted: one pass, n-1 comparisons, 0 swaps);
           average and worst Θ(n²) (reverse: n(n-1)/2 comparisons and swaps).
    Space: Θ(1) extra.
    Stable: yes — we swap only when the right element is *strictly* less.
    """
    n = len(arr)
    for end in range(n - 1, 0, -1):  # compare pairs (i, i+1) for i < end
        swapped = False
        for i in range(end):
            if counter.less(arr[i + 1], arr[i]):
                counter.swap(arr, i, i + 1)
                swapped = True
        if not swapped:
            break
