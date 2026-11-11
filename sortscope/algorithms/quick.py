"""Quick Sort with Hoare partitioning and three pivot rules (M1, owner: Ingeet).

Design choices (explainable in the demo):

1. **Hoare partition, not Lomuto.** Lomuto puts every element equal to the
   pivot on one side, so an all-equal or many-duplicates array degrades to
   Θ(n²). Hoare's scans both stop on elements *equal* to the pivot and swap
   them, which splits runs of duplicates roughly in half -> Θ(n log n).

2. **Pivot always moved to arr[lo] first.** The chosen pivot (first / random /
   median-of-three) is swapped to ``lo`` (counted as a swap, skipped if it is
   already there) and then one Hoare routine is used for all three rules.
   With the pivot value taken from ``arr[lo]``, Hoare returns j in [lo, hi-1],
   so both parts [lo..j] and [j+1..hi] are non-empty and recursion terminates.
   Note: unlike Lomuto, the pivot is *not* necessarily in its final position
   after partitioning.

3. **Recurse on the smaller part, loop on the larger.** The smaller part has
   at most half of the elements, so the recursion depth is <= ⌊lg n⌋ + 1 for
   every pivot rule — even first-pivot on sorted input, which still does
   Θ(n²) work but never hits Python's recursion limit.
"""

from __future__ import annotations

import random
from typing import Callable, Literal

from sortscope.counter import OpCounter

PivotRule = Literal["first", "random", "median3"]
# (arr, lo, hi, counter) -> index of the chosen pivot in [lo, hi]
_Chooser = Callable[[list, int, int, OpCounter], int]


def quick_sort(
    arr: list[int],
    counter: OpCounter,
    pivot: PivotRule = "first",
    rng: random.Random | None = None,
) -> None:
    """Sort ``arr`` in place with Quick Sort (Hoare partition).

    ``pivot`` selects the rule: ``"first"`` (arr[lo]), ``"random"`` (uniform in
    [lo, hi] drawn from ``rng``, which is required so runs are reproducible),
    or ``"median3"`` (median of arr[lo], arr[mid], arr[hi]; 2-3 comparisons,
    all counted).

    On already-sorted input with the first-element pivot, a segment of size m
    costs m + 1 comparisons and splits into sizes 1 and m-1, so the total is
    sum_{m=2..n}(m+1) = (n² + 3n − 4)/2 comparisons and 0 swaps.

    Time:  best/average Θ(n log n); worst Θ(n²) (first pivot on sorted or
           reverse input; vanishingly unlikely for random pivots).
    Space: Θ(log n) recursion stack (smaller-side recursion), no other buffers.
    Stable: no — Hoare swaps elements equal to the pivot, e.g. [1a, 1b] -> [1b, 1a].
    """
    chooser = _make_chooser(pivot, rng)
    _quick(arr, 0, len(arr) - 1, counter, chooser, 1)


def _make_chooser(pivot: PivotRule, rng: random.Random | None) -> _Chooser:
    if pivot == "first":
        return _choose_first
    if pivot == "median3":
        return _choose_median3
    if pivot == "random":
        if rng is None:
            raise ValueError("pivot='random' needs an explicit random.Random(seed) for reproducibility")
        return lambda arr, lo, hi, counter: rng.randrange(lo, hi + 1)
    raise ValueError(f"unknown pivot rule: {pivot!r}")


def _choose_first(arr: list, lo: int, hi: int, counter: OpCounter) -> int:
    return lo


def _choose_median3(arr: list, lo: int, hi: int, counter: OpCounter) -> int:
    """Index of the median of arr[lo], arr[mid], arr[hi] (2 or 3 comparisons).

    For segments of size 2 the three positions are not distinct, so we just
    use lo (no comparisons) — this keeps the counts easy to reason about.
    """
    if hi - lo < 2:
        return lo
    mid = (lo + hi) // 2
    a, b, c = arr[lo], arr[mid], arr[hi]
    if counter.less(a, b):          # a < b
        if counter.less(b, c):      # a < b < c
            return mid
        # b is the max, so the median is max(a, c)
        return hi if counter.less(a, c) else lo
    # b <= a
    if counter.less(a, c):          # b <= a < c
        return lo
    # a is the max, so the median is max(b, c)
    return hi if counter.less(b, c) else mid


def _quick(arr: list, lo: int, hi: int, counter: OpCounter, chooser: _Chooser, depth: int) -> None:
    # Why first-pivot on sorted input is still Θ(n²) *time* even though the
    # stack is only O(log n): on sorted data arr[lo] is the minimum, so Hoare
    # splits a segment of size m into sizes 1 and m-1 after scanning the whole
    # segment (m+1 comparisons). The loop below then handles size m-1, m-2, ...
    # Total work = sum_{m=2..n} (m+1) = (n² + 3n − 4)/2 = Θ(n²).
    # Recursing on the smaller side only changes *where* that work happens
    # (a loop iteration instead of a nested call), not how much there is.
    while lo < hi:
        counter.note_depth(depth)
        p = _hoare_partition(arr, lo, hi, counter, chooser)
        # Parts are [lo..p] and [p+1..hi]. Recurse into the smaller one and
        # continue the loop on the larger one (tail-call elimination by hand).
        if p - lo < hi - p:
            _quick(arr, lo, p, counter, chooser, depth + 1)
            lo = p + 1
        else:
            _quick(arr, p + 1, hi, counter, chooser, depth + 1)
            hi = p


def _hoare_partition(arr: list, lo: int, hi: int, counter: OpCounter, chooser: _Chooser) -> int:
    """Hoare partition (CLRS Problem 7-1 form) around the chosen pivot value.

    Afterwards every element of arr[lo..j] is <= pivot and every element of
    arr[j+1..hi] is >= pivot, with lo <= j < hi. No bounds checks are needed in
    the inner scans: the pivot value (and, after the first swap, the swapped
    elements) act as sentinels that stop both scans inside [lo, hi].
    """
    k = chooser(arr, lo, hi, counter)
    if k != lo:
        counter.swap(arr, lo, k)
    pivot = arr[lo]
    i = lo - 1
    j = hi + 1
    while True:
        j -= 1
        while counter.less(pivot, arr[j]):  # arr[j] > pivot: keep scanning left
            j -= 1
        i += 1
        while counter.less(arr[i], pivot):  # arr[i] < pivot: keep scanning right
            i += 1
        if i < j:
            counter.swap(arr, i, j)
        else:
            return j
