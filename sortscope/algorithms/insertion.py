"""Insertion Sort (M1, owner: Ingeet)."""

from __future__ import annotations

from sortscope.counter import OpCounter


def insertion_sort(arr: list[int], counter: OpCounter) -> None:
    """Sort ``arr`` in place with Insertion Sort (shifting, not swapping).

    For i = 1..n-1, hold ``key = arr[i]`` and shift every larger element in the
    sorted prefix one slot right (1 write each), then place the key (1 write).
    Each shift removes exactly one inversion, so:

    * shifts      == inv(arr)                (number of inversions)
    * writes      == inv(arr) + (n - 1)      (the key is always written back,
                                              even if it did not move)
    * comparisons in [inv, inv + n - 1]      (one extra failing comparison per
                                              key unless it reaches index 0)

    Time:  best Θ(n) (sorted), average and worst Θ(n²) — more precisely Θ(n + inv).
    Space: Θ(1) extra.
    Stable: yes — we stop shifting as soon as ``arr[j]`` is not strictly greater.
    """
    for i in range(1, len(arr)):
        key = arr[i]  # reading is not a write
        j = i - 1
        while j >= 0 and counter.less(key, arr[j]):
            counter.write(arr, j + 1, arr[j])  # shift right
            j -= 1
        counter.write(arr, j + 1, key)  # place the key
