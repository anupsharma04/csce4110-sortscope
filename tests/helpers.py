"""Independent reference computations for the count tests.

Nothing here imports the sorting code, so the tests compare our sorts against
separately written formulas/oracles.
"""

from __future__ import annotations

import math


def count_inversions(arr: list[int]) -> int:
    """Inversions via merge-count: O(n log n). Independent of sortscope code.

    While merging sorted halves L and R, whenever R[j] < L[i], R[j] is smaller
    than every remaining element of L, contributing len(L) - i inversions.
    """

    def sort_count(a: list[int]) -> tuple[list[int], int]:
        if len(a) <= 1:
            return list(a), 0
        mid = len(a) // 2
        left, x = sort_count(a[:mid])
        right, y = sort_count(a[mid:])
        merged, inv, i, j = [], x + y, 0, 0
        while i < len(left) and j < len(right):
            if right[j] < left[i]:
                merged.append(right[j])
                inv += len(left) - i
                j += 1
            else:
                merged.append(left[i])
                i += 1
        merged.extend(left[i:])
        merged.extend(right[j:])
        return merged, inv

    return sort_count(arr)[1]


def brute_inversions(arr: list[int]) -> int:
    """O(n²) definition, used only to validate the fast counters on small inputs."""
    n = len(arr)
    return sum(1 for i in range(n) for j in range(i + 1, n) if arr[i] > arr[j])


def strict_prefix_minima(arr: list[int]) -> int:
    """Number of i >= 1 with arr[i] < min(arr[:i]) (keys that slide all the way to index 0)."""
    count, cur = 0, None
    for i, v in enumerate(arr):
        if i == 0:
            cur = v
        elif v < cur:
            count += 1
            cur = v
    return count


def ceil_lg(n: int) -> int:
    return (n - 1).bit_length() if n > 1 else 0  # exact ⌈lg n⌉ without floats


def merge_writes_closed_form(n: int) -> int:
    k = ceil_lg(n)
    return n * k - (1 << k) + n if n >= 1 else 0


def merge_worst_comparisons_closed_form(n: int) -> int:
    k = ceil_lg(n)
    return n * k - (1 << k) + 1 if n >= 1 else 0


def split_recurrence(n: int, cost) -> int:
    """T(0)=T(1)=0, T(n) = T(⌈n/2⌉) + T(⌊n/2⌋) + cost(n)."""
    memo: dict[int, int] = {0: 0, 1: 0}

    def t(m: int) -> int:
        if m not in memo:
            memo[m] = t((m + 1) // 2) + t(m // 2) + cost(m)
        return memo[m]

    return t(n)


def merge_worst_case_input(n: int) -> list[int]:
    """An input on which *every* merge of our Merge Sort needs size-1 comparisons.

    "Unmerge" the sorted list: put even-ranked keys in the left half (which gets
    ⌈m/2⌉ elements in our split) and odd-ranked keys in the right, recursively.
    Each merge then alternates sides and stops only when one element is left.
    """

    def build(keys: list[int]) -> list[int]:
        if len(keys) <= 1:
            return keys
        return build(keys[0::2]) + build(keys[1::2])

    return build(list(range(n)))


def hoare_random_expected_comparisons(n: int) -> float:
    """Exact E[comparisons] of our Quick Sort with a uniform random pivot, distinct keys.

    E(0)=E(1)=0, and for m >= 2 (rank r of the pivot uniform in 1..m):
        cost of the partition = m+1 if r == 1 else m+2
        split                 = (1, m-1) if r == 1 else (r-1, m-r+1)
    so  E(m) = m + 2 - 1/m + [E(1) + E(m-1) + sum_{r=2..m} (E(r-1) + E(m-r+1))] / m
             = m + 2 - 1/m + [E(m-1) + 2·S(m-1)] / m,   S(k) = E(1) + ... + E(k).
    (Derivation and the exhaustive check of both facts are in test_counts.py.)
    """
    if n < 2:
        return 0.0
    e_prev = 0.0  # E(m-1)
    s_prev = 0.0  # S(m-1)
    for m in range(2, n + 1):
        e = m + 2 - 1 / m + (e_prev + 2 * s_prev) / m
        s_prev += e
        e_prev = e
    return e_prev


def two_n_ln_n(n: int) -> float:
    return 2 * n * math.log(n)
