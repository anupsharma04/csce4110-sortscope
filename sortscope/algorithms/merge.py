"""Top-down Merge Sort (M1, owner: Ingeet)."""

from __future__ import annotations

from sortscope.counter import OpCounter


def merge_sort(arr: list[int], counter: OpCounter) -> None:
    """Sort ``arr`` in place with top-down Merge Sort.

    Split [lo..hi] at mid = (lo+hi)//2 (left half gets the extra element),
    sort both halves, merge them into one scratch buffer ``aux`` of size n,
    then copy the *whole* segment back into ``arr``. Only the copy-back counts
    as writes (aux is not the input array), so the write count satisfies

        W(1) = 0,  W(n) = W(⌈n/2⌉) + W(⌊n/2⌋) + n
             = n⌈lg n⌉ − 2^⌈lg n⌉ + n          (exact, input-independent)

    and comparisons satisfy the textbook worst-case bound

        C(n) <= n⌈lg n⌉ − 2^⌈lg n⌉ + 1.

    Merge Sort never swaps.

    Time:  Θ(n log n) best, average and worst.
    Space: Θ(n) extra for ``aux`` (allocated once) + Θ(log n) recursion stack.
    Stable: yes — on a tie we take from the left half (we take the right
            element only if it is *strictly* less).
    """
    n = len(arr)
    if n < 2:
        return
    # One buffer reused by every merge, instead of slicing per call, so peak
    # extra memory is a clean Θ(n) and easy to explain.
    aux: list = [None] * n
    _merge_sort(arr, aux, 0, n - 1, counter, 1)


def _merge_sort(arr: list, aux: list, lo: int, hi: int, counter: OpCounter, depth: int) -> None:
    if lo >= hi:  # 0 or 1 element: already sorted, no work
        return
    counter.note_depth(depth)
    mid = (lo + hi) // 2
    _merge_sort(arr, aux, lo, mid, counter, depth + 1)
    _merge_sort(arr, aux, mid + 1, hi, counter, depth + 1)
    _merge(arr, aux, lo, mid, hi, counter)


def _merge(arr: list, aux: list, lo: int, mid: int, hi: int, counter: OpCounter) -> None:
    """Merge sorted arr[lo..mid] and arr[mid+1..hi] via aux, then copy back."""
    i, j, k = lo, mid + 1, lo
    while i <= mid and j <= hi:
        if counter.less(arr[j], arr[i]):  # strictly less -> right first; ties keep left first
            aux[k] = arr[j]
            j += 1
        else:
            aux[k] = arr[i]
            i += 1
        k += 1
    # One side is exhausted; the rest of the other side is already in order
    # and needs no comparisons.
    while i <= mid:
        aux[k] = arr[i]
        i += 1
        k += 1
    while j <= hi:
        aux[k] = arr[j]
        j += 1
        k += 1
    for k in range(lo, hi + 1):
        counter.write(arr, k, aux[k])
