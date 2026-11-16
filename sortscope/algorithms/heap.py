"""Heap Sort (M1, owner: Ingeet) — the proposal's stretch goal, added as a sixth algorithm."""

from __future__ import annotations

from sortscope.counter import OpCounter


def heap_sort(arr: list[int], counter: OpCounter) -> None:
    """Sort ``arr`` in place with Heap Sort (binary max-heap stored in the array itself).

    The children of index i are 2i+1 and 2i+2. Two phases:

    1. **Build** a max-heap bottom-up (Floyd): sift down every internal node,
       from the last one (n//2 - 1) back to the root. A sift-down from a node of
       height h costs at most 2h comparisons and h swaps, and the heights of all
       nodes of an n-node heap add up to n - popcount(n), so the build makes at
       most 2(n - popcount(n)) < 2n comparisons: it is Θ(n), not Θ(n log n).
    2. **Extract** n-1 times: swap the maximum (root) with the last element of
       the heap, shrink the heap by one, and sift the new root down. A heap of
       m elements has height ⌊lg m⌋, so each extraction costs at most 2⌊lg m⌋
       comparisons.

    Total: comparisons <= 2(n - popcount(n)) + 2·Σ_{m=1}^{n-1} ⌊lg m⌋ ≈ 2n lg n,
    and exactly n-1 root swaps plus the sift-down swaps (writes = 2·swaps).

    Time:  Θ(n log n) worst and average. Best case with *distinct* keys is also
           Θ(n log n); with all keys equal every sift-down stops at once, so
           that input costs only 3n - 6 comparisons (Θ(n)).
    Space: Θ(1) extra — no buffer and no recursion (sift-down is a loop).
    Stable: no — the root swap moves an element across the whole heap, past
            equal keys, e.g. [1a, 1b] -> [1b, 1a].
    """
    n = len(arr)
    _build_max_heap(arr, counter)
    for end in range(n - 1, 0, -1):
        # arr[0] is the largest of arr[0..end]; put it in its final slot `end`.
        counter.swap(arr, 0, end)
        _sift_down(arr, 0, end, counter)  # the heap is now arr[0..end-1]


def _build_max_heap(arr: list, counter: OpCounter) -> None:
    """Phase 1: turn ``arr`` into a max-heap. Leaves (indices >= n//2) are already heaps of size 1."""
    n = len(arr)
    for i in range(n // 2 - 1, -1, -1):
        _sift_down(arr, i, n, counter)


def _sift_down(arr: list, i: int, size: int, counter: OpCounter) -> None:
    """Move arr[i] down inside the heap arr[0..size-1] until neither child is larger.

    Per level: one comparison to pick the larger child (skipped when there is
    only one child) and one comparison of the parent against that child.
    Only ``<`` is used, like every other sort here.
    """
    while True:
        child = 2 * i + 1                       # left child
        if child >= size:                       # i is a leaf: done (index check, not counted)
            return
        if child + 1 < size and counter.less(arr[child], arr[child + 1]):
            child += 1                          # the right child is strictly larger
        if not counter.less(arr[i], arr[child]):
            return                              # parent >= larger child: heap order holds
        counter.swap(arr, i, child)
        i = child
