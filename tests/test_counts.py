"""Exact operation-count checks: closed forms derived for OUR implementations.

Notation: n = len(arr), inv = number of inversions (pairs i<j, arr[i] > arr[j]),
lg = log base 2, k = ⌈lg n⌉. Each block's comment is the derivation (for the report);
the test below it asserts the result.
"""

from __future__ import annotations

import itertools
import math
import random
import statistics

import pytest
from helpers import (
    brute_inversions,
    count_inversions,
    hoare_random_expected_comparisons,
    merge_worst_case_input,
    merge_worst_comparisons_closed_form,
    merge_writes_closed_form,
    split_recurrence,
    strict_prefix_minima,
    two_n_ln_n,
)

from sortscope.algorithms.quick import _choose_first, _hoare_partition
from sortscope.counter import OpCounter
from sortscope.inputs import generate, input_kinds
from sortscope.registry import get_sort


def run(name: str, arr: list[int], seed: int = 0) -> OpCounter:
    c = OpCounter()
    get_sort(name, seed=seed)(list(arr), c)
    return c


def sample_inputs(max_n: int = 60, per_kind_seeds: int = 3, random_lists: int = 200):
    """All generator kinds at every n <= max_n, plus random lists with negatives/duplicates."""
    cases = []
    for kind in input_kinds():
        for n in range(max_n + 1):
            for s in range(per_kind_seeds):
                cases.append(generate(kind, n, seed=s))
    rng = random.Random(4110)
    for _ in range(random_lists):
        cases.append([rng.randint(-20, 20) for _ in range(rng.randint(0, 80))])
    return cases


CASES = sample_inputs()


def test_reference_inversion_counter_matches_definition() -> None:
    rng = random.Random(0)
    for _ in range(300):
        arr = [rng.randint(-10, 10) for _ in range(rng.randint(0, 40))]
        assert count_inversions(arr) == brute_inversions(arr)


# ---------------------------------------------------------------------------
# Selection Sort
#
# The inner loop for position i scans j = i+1 .. n-1 with no early exit, so it
# makes n-1-i comparisons regardless of the data. Summing over i = 0 .. n-2:
#     C(n) = Σ_{i=0}^{n-2} (n-1-i) = (n-1) + (n-2) + ... + 1 = n(n-1)/2.
# Swaps: at most one per outer iteration, and we skip the swap when the minimum
# is already at i, so 0 <= swaps <= n-1; writes = 2·swaps.
# Reverse input 0..n-1 reversed: step i swaps positions i and n-1-i, which puts
# both in their final place; steps i >= ⌊n/2⌋ find the minimum already in place.
# Hence swaps(reverse) = ⌊n/2⌋.
# ---------------------------------------------------------------------------
def test_selection_comparisons_are_n_choose_2_for_every_input() -> None:
    for arr in CASES:
        n = len(arr)
        c = run("selection", arr)
        assert c.comparisons == n * (n - 1) // 2
        assert 0 <= c.swaps <= max(n - 1, 0)
        assert c.writes == 2 * c.swaps


@pytest.mark.parametrize("n", list(range(0, 50)) + [100, 501])
def test_selection_reverse_swaps(n: int) -> None:
    assert run("selection", generate("reverse", n)).swaps == n // 2


# ---------------------------------------------------------------------------
# Bubble Sort (early exit)
#
# Pass with bound `end` compares pairs (i, i+1) for i < end: `end` comparisons.
# * Sorted: the first pass (end = n-1) finds no out-of-order pair, makes no
#   swap and exits. C = n-1, swaps = 0  (n >= 1).
# * Reverse: by induction the unsorted prefix stays strictly decreasing after
#   every pass (each pass just carries the prefix maximum to the end), so every
#   comparison swaps and no pass exits early. Passes end = n-1, ..., 1:
#   C = Σ_{e=1}^{n-1} e = n(n-1)/2, swaps = n(n-1)/2.
# * Any input: an adjacent swap of an out-of-order pair removes exactly one
#   inversion and creates none, and the sort ends with 0 inversions, so
#   swaps = inv exactly; writes = 2·inv.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("n", list(range(1, 60)) + [500])
def test_bubble_sorted_and_reverse(n: int) -> None:
    c = run("bubble", generate("sorted", n))
    assert (c.comparisons, c.swaps, c.writes) == (n - 1, 0, 0)
    c = run("bubble", generate("reverse", n))
    q = n * (n - 1) // 2
    assert (c.comparisons, c.swaps, c.writes) == (q, q, 2 * q)


def test_bubble_swaps_equal_inversions() -> None:
    for arr in CASES:
        c = run("bubble", arr)
        inv = count_inversions(arr)
        assert c.swaps == inv
        assert c.writes == 2 * inv


# ---------------------------------------------------------------------------
# Insertion Sort
#
# For key arr[i], the elements shifted right are exactly the earlier elements
# strictly greater than it — the inversions (j, i) with j < i. Each shift is one
# write, so total shifts = Σ_i #{j < i : arr[j] > arr[i]} = inv.
# The key is always written back once per i = 1..n-1, so
#     writes = inv + (n-1)      (n >= 1).
# Comparisons for key i: one per shift, plus one final *failing* comparison
# unless the scan runs off the left end (j = -1), which happens exactly when
# the key is strictly smaller than everything before it (a strict prefix
# minimum). With z = #strict prefix minima among i >= 1:
#     comparisons = inv + (n-1) - z,   hence  inv <= comparisons <= inv + n-1.
# Insertion Sort does no swaps.
# ---------------------------------------------------------------------------
def test_insertion_shifts_equal_inversions_and_comparisons_exact() -> None:
    for arr in CASES:
        n = len(arr)
        c = run("insertion", arr)
        inv = count_inversions(arr)
        key_writes = max(n - 1, 0)
        assert c.writes - key_writes == inv            # shift-writes == inversions
        assert c.swaps == 0
        assert c.comparisons == inv + key_writes - strict_prefix_minima(arr)
        assert inv <= c.comparisons <= inv + key_writes


# ---------------------------------------------------------------------------
# Merge Sort (top-down, mid = (lo+hi)//2, left half gets ⌈m/2⌉)
#
# Writes: every merge of a segment of size m copies all m elements back, so
#     W(1) = 0,  W(m) = W(⌈m/2⌉) + W(⌊m/2⌋) + m.
# Closed form: splitting sizes as ⌈m/2⌉,⌊m/2⌋ keeps sizes on each level within 1
# of each other, so all n leaves sit at depth k or k-1 (k = ⌈lg n⌉). With a leaves
# at depth k-1 and b at depth k: a + b = n and a·2 + b = 2^k (a full tree of
# depth k has 2^k slots), so a = 2^k - n, b = 2n - 2^k. W(n) counts each element
# once per segment containing it above the leaf = its leaf depth, so
#     W(n) = (k-1)(2^k - n) + k(2n - 2^k) = n·k - 2^k + n.        (any input)
# Worst-case comparisons: a merge of m elements makes at most m-1 comparisons
# (each comparison outputs one element, and the last element needs none), so
#     C_w(m) = C_w(⌈m/2⌉) + C_w(⌊m/2⌋) + m - 1 = W(n) - (#merges) = W(n) - (n-1)
#            = n·k - 2^k + 1.
# The bound is tight: "unmerging" the sorted keys (even ranks left, odd ranks
# right, recursively) forces every merge to alternate until one element remains.
# Best cases (exact): sorted input -> every left element wins, the merge stops
# when the left half (⌈m/2⌉) runs out; reverse input -> every right element wins,
# stops after ⌊m/2⌋. Merge Sort never swaps.
# ---------------------------------------------------------------------------
MERGE_NS = list(range(0, 300)) + [511, 512, 513, 1000, 1024]


@pytest.mark.parametrize("n", MERGE_NS)
def test_merge_closed_forms_agree_with_recurrences(n: int) -> None:
    assert merge_writes_closed_form(n) == split_recurrence(n, lambda m: m)
    assert merge_worst_comparisons_closed_form(n) == split_recurrence(n, lambda m: m - 1)


def test_merge_writes_exact_and_comparisons_bounded_for_every_input() -> None:
    for arr in CASES:
        n = len(arr)
        c = run("merge", arr)
        assert c.writes == merge_writes_closed_form(n)
        assert c.comparisons <= merge_worst_comparisons_closed_form(n)
        # Lower bound: a merge stops when one half is exhausted, and the half that
        # empties first holds >= ⌊m/2⌋ elements, each output by one comparison.
        # So comparisons >= B(n), B(m) = B(⌈m/2⌉) + B(⌊m/2⌋) + ⌊m/2⌋ (reverse input
        # attains it; B(n) ≈ (n/2) lg n).
        assert c.comparisons >= split_recurrence(n, lambda m: m // 2)
        assert c.swaps == 0


@pytest.mark.parametrize("n", MERGE_NS)
def test_merge_worst_case_bound_is_attained(n: int) -> None:
    arr = merge_worst_case_input(n)
    assert run("merge", arr).comparisons == merge_worst_comparisons_closed_form(n)


@pytest.mark.parametrize("n", MERGE_NS)
def test_merge_sorted_and_reverse_exact(n: int) -> None:
    assert run("merge", generate("sorted", n)).comparisons == split_recurrence(n, lambda m: (m + 1) // 2)
    assert run("merge", generate("reverse", n)).comparisons == split_recurrence(n, lambda m: m // 2)


# ---------------------------------------------------------------------------
# Quick Sort — facts about OUR Hoare partition (pivot value p = arr[lo], i=lo-1,
# j=hi+1; repeat { j-- while p < arr[j]; i++ while arr[i] < p; swap if i<j }).
#
# Each scan compares a position at most once (pointers only move inward), so the
# comparisons in one partition are (hi - j + 1) + (i - lo + 1) = m + 1 + (i - j)
# at termination. With distinct keys and pivot rank r (1 = smallest):
# * r = 1: no key is < p, so j scans all the way down to lo and i stops at lo
#   immediately: the pointers MEET (i = j = lo): m + 1 comparisons, no swap,
#   split (1, m-1).
# * r >= 2: the first round stops j at a key < p and i at lo; they swap, which
#   moves p to the right part. After that j stays strictly left of p's slot, so
#   the pointers can never meet on p, and the only key that can stop both scans
#   is p itself -> they CROSS (i = j + 1): m + 2 comparisons; the left part is
#   exactly the r-1 keys < p, split (r-1, m-r+1).
# test_hoare_partition_facts_exhaustive checks both facts on all 5,912
# permutations with 2 <= m <= 7.
# ---------------------------------------------------------------------------
def test_hoare_partition_facts_exhaustive() -> None:
    for m in range(2, 8):
        for perm in itertools.permutations(range(m)):
            arr, c = list(perm), OpCounter()
            r = arr[0] + 1
            j = _hoare_partition(arr, 0, m - 1, c, _choose_first)
            assert j + 1 == (1 if r == 1 else r - 1)
            assert c.comparisons == (m + 1 if r == 1 else m + 2)
            assert max(arr[: j + 1]) < min(arr[j + 1 :]) or r == 1


# ---------------------------------------------------------------------------
# Quick Sort, first-element pivot, sorted input
#
# Every segment arr[lo..hi] stays sorted, so the pivot always has rank 1: cost
# m + 1, split (1, m-1), no swaps. The loop runs on sizes n, n-1, ..., 2:
#     C(n) = Σ_{m=2}^{n} (m + 1) = (n(n+1)/2 - 1) + (n - 1) = (n² + 3n - 4)/2.
# (Textbook n(n-1)/2 is for a partition doing m-1 comparisons; Hoare's two
# scans overlap by two positions.) swaps = writes = 0. Θ(n²) time.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("n", list(range(1, 120)) + [1000, 2000])
def test_quick_first_on_sorted_exact(n: int) -> None:
    c = run("quick_first", generate("sorted", n))
    assert c.comparisons == (n * n + 3 * n - 4) // 2
    assert (c.swaps, c.writes) == (0, 0)


# ---------------------------------------------------------------------------
# Quick Sort, first-element pivot, ALL-EQUAL input (why we use Hoare, risk R2)
#
# Every comparison is false, so each round both scans stop after one step and
# swap; round t has j = hi-t+1, i = lo+t-1. With m = 2h: h swapping rounds,
# then they cross -> m + 2 comparisons, split (h, h). With m = 2h+1: h swaps,
# then they meet in the middle -> m + 1 comparisons, split (h+1, h).
# So splits are perfectly balanced, (⌈m/2⌉, ⌊m/2⌋):
#     C(m) = C(⌈m/2⌉) + C(⌊m/2⌋) + m + 1 + [m even],   S(m) = ... + ⌊m/2⌋
# i.e. Θ(n log n). (Lomuto would put everything on one side: Θ(n²).)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("n", list(range(0, 100)) + [1000, 4096])
def test_quick_first_on_all_equal_is_balanced(n: int) -> None:
    c = run("quick_first", [7] * n)
    assert c.comparisons == split_recurrence(n, lambda m: m + 1 + (m % 2 == 0))
    assert c.swaps == split_recurrence(n, lambda m: m // 2)


# ---------------------------------------------------------------------------
# Quick Sort, random pivot — expected comparisons
#
# randrange picks a position uniformly, so the pivot's rank r is uniform on
# 1..m independently of how the segment is arranged. By the partition facts
# above, cost and split depend only on r, so for distinct keys
#     E(m) = m + 2 - 1/m + (1/m)[E(1) + E(m-1) + Σ_{r=2}^{m} (E(r-1) + E(m-r+1))]
#          = m + 2 - 1/m + (E(m-1) + 2·S(m-1)) / m,     E(0) = E(1) = 0,
# which is exact for ANY arrangement of distinct keys (see helpers).
# Asymptotically E(n) = 2n ln n + Θ(n): the standard analysis gives 2n ln n as
# the leading term for any partition that costs m + O(1). The Θ(n) term is
# POSITIVE for us (≈ +1.1n): we pay m+2 instead of the textbook m-1 per
# partition and the pivot stays inside a subproblem. So mean/(2n ln n) > 1 and
# approaches 1 only like 1 + c/ln n.
#
# Test A (stated tolerance vs 2n ln n): at n = 1000, 200 seeds, the mean must be
# within 10% of 2n ln n. Measured ≈ 1.075; the 10% covers the +Θ(n) term
# (≈ 1.1n / 2n ln n ≈ 8%) — it is a leading-term check, not an exact one.
# Test B (exact): the mean must be within 4 standard errors of E(n).
# Comparisons per run have sd ≈ 0.65n, so SE ≈ 0.65n/√200 ≈ 0.046n.
# Both use a fresh random permutation per seed and the same seed for the pivot.
# ---------------------------------------------------------------------------
N_RANDOM, SEEDS = 1000, 200


@pytest.fixture(scope="module")
def quick_random_samples() -> list[int]:
    return [
        run("quick_random", generate("random", N_RANDOM, seed=s), seed=s).comparisons
        for s in range(SEEDS)
    ]


def test_quick_random_mean_is_about_2n_ln_n(quick_random_samples: list[int]) -> None:
    ratio = statistics.fmean(quick_random_samples) / two_n_ln_n(N_RANDOM)
    assert 1.0 <= ratio <= 1.10, ratio


def test_quick_random_mean_matches_exact_expectation(quick_random_samples: list[int]) -> None:
    mean = statistics.fmean(quick_random_samples)
    se = statistics.stdev(quick_random_samples) / math.sqrt(SEEDS)
    expected = hoare_random_expected_comparisons(N_RANDOM)
    assert abs(mean - expected) <= 4 * se, (mean, expected, se)


def test_expected_recurrence_small_cases_by_enumeration() -> None:
    # E(2): ranks 1 and 2 cost 3 and 4 -> 3.5. Check E(m) for m <= 6 by averaging
    # the exact recurrence of costs over all (permutation, pivot-position) pairs.
    def exact_avg(m: int) -> float:
        if m < 2:
            return 0.0
        total = 0.0
        for r in range(1, m + 1):
            cost = m + 1 if r == 1 else m + 2
            left, right = (1, m - 1) if r == 1 else (r - 1, m - r + 1)
            total += cost + exact_avg(left) + exact_avg(right)
        return total / m

    for m in range(0, 9):
        assert hoare_random_expected_comparisons(m) == pytest.approx(exact_avg(m))
