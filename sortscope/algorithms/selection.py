"""Selection Sort (M1, owner: Ingeet)."""

from __future__ import annotations

from sortscope.counter import OpCounter


def selection_sort(arr: list[int], counter: OpCounter) -> None:
    """Sort ``arr`` in place with Selection Sort.

    For each position i, scan the unsorted suffix for its minimum and swap it
    into position i. The scan never stops early, so the comparison count is
    exactly n(n-1)/2 for *every* input; only the number of swaps depends on it.
    A swap is skipped when the minimum is already at i (no work is done), so
    swaps <= n-1.

    Time:  Θ(n²) best, average and worst.
    Space: Θ(1) extra.
    Stable: no — the long-distance swap can jump an element over an equal one,
            e.g. [2a, 2b, 1] -> [1, 2b, 2a].
    """
    n = len(arr)
    for i in range(n - 1):
        m = i
        for j in range(i + 1, n):
            if counter.less(arr[j], arr[m]):
                m = j
        if m != i:
            counter.swap(arr, i, m)
