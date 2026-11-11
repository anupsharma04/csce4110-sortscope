"""Input generators (M2, owner: Ingeet).

Every generator has the signature ``gen(n: int, seed: int) -> list[int]`` and
uses its own ``random.Random(seed)`` (no global RNG), so the same (kind, n, seed)
always produces the same list. Generators that need no randomness (sorted,
reverse) still accept ``seed`` so callers can treat all kinds uniformly.

Definitions (documented in the README and report):

* ``random``          — a uniformly random permutation of 0..n-1 (distinct keys,
                        which is the assumption behind the 2n ln n average-case
                        analysis of Quick Sort).
* ``sorted``          — 0, 1, ..., n-1.
* ``reverse``         — n-1, ..., 1, 0.
* ``nearly_sorted``   — start sorted, pick m = round(0.05·n) positions at
                        random (at least 2 when n >= 2) and rotate their values
                        one step along a random cycle. Every chosen position
                        receives a different value, so *exactly* m positions
                        are out of place (≈5%) and the rest are untouched.
* ``many_duplicates`` — n values drawn uniformly from range(k), k = max(1, n // 50),
                        so each value appears ~50 times on average.
                        (n < 100 gives k = 1, i.e. all equal.)
"""

from __future__ import annotations

import random
from typing import Callable

Generator = Callable[[int, int], list[int]]


def _check_n(n: int) -> None:
    if n < 0:
        raise ValueError(f"n must be non-negative, got {n}")


def random_input(n: int, seed: int = 0) -> list[int]:
    """Uniformly random permutation of 0..n-1."""
    _check_n(n)
    arr = list(range(n))
    random.Random(seed).shuffle(arr)
    return arr


def sorted_input(n: int, seed: int = 0) -> list[int]:
    """0, 1, ..., n-1 (seed unused)."""
    _check_n(n)
    return list(range(n))


def reverse_input(n: int, seed: int = 0) -> list[int]:
    """n-1, ..., 0 (seed unused)."""
    _check_n(n)
    return list(range(n - 1, -1, -1))


NEARLY_SORTED_FRACTION = 0.05


def nearly_displaced_count(n: int) -> int:
    """How many positions ``nearly_sorted_input(n, ·)`` puts out of place."""
    if n < 2:
        return 0
    # A cycle needs >= 2 positions to actually move anything.
    return max(2, round(NEARLY_SORTED_FRACTION * n))


def nearly_sorted_input(n: int, seed: int = 0) -> list[int]:
    """Sorted list with exactly ``nearly_displaced_count(n)`` (≈5%) positions out of place."""
    _check_n(n)
    arr = list(range(n))
    m = nearly_displaced_count(n)
    if m == 0:
        return arr
    rng = random.Random(seed)
    pos = rng.sample(range(n), m)  # random positions in random order = a random cycle
    first = arr[pos[0]]
    for a, b in zip(pos, pos[1:]):
        arr[a] = arr[b]
    arr[pos[-1]] = first
    # Because keys are distinct (arr[i] == i before rotating), each position
    # in the cycle now holds some other position's key -> exactly m displaced.
    return arr


def duplicates_distinct_count(n: int) -> int:
    """Size of the value range used by ``many_duplicates_input``: max(1, n // 50)."""
    return max(1, n // 50)


def many_duplicates_input(n: int, seed: int = 0) -> list[int]:
    """n values drawn uniformly from range(max(1, n // 50))."""
    _check_n(n)
    k = duplicates_distinct_count(n)
    rng = random.Random(seed)
    return [rng.randrange(k) for _ in range(n)]


GENERATORS: dict[str, Generator] = {
    "random": random_input,
    "sorted": sorted_input,
    "reverse": reverse_input,
    "nearly_sorted": nearly_sorted_input,
    "many_duplicates": many_duplicates_input,
}


def input_kinds() -> list[str]:
    """Names of the five input generators, in report order."""
    return list(GENERATORS)


def generate(kind: str, n: int, seed: int = 0) -> list[int]:
    """Generate an input of the given kind; raises KeyError for unknown kinds."""
    try:
        gen = GENERATORS[kind]
    except KeyError:
        raise KeyError(f"unknown input kind {kind!r}; choose from {input_kinds()}") from None
    return gen(n, seed)


def inversion_count(arr: list[int]) -> int:
    """Number of pairs i < j with arr[i] > arr[j] — a measure of "unsortedness".

    0 for sorted input, n(n-1)/2 for strictly reverse input, ~n(n-1)/4 for a
    random permutation. Insertion Sort shifts exactly this many times, so this
    explains its run time across input kinds.

    Method: Fenwick (binary indexed) tree over value ranks. Scan left to right;
    for each element, the number of *earlier* elements strictly greater than it
    is (elements seen so far) - (earlier elements <= it). O(n log n) time,
    O(n) space. Ties are not inversions.
    """
    rank = {v: r for r, v in enumerate(sorted(set(arr)), start=1)}
    size = len(rank)
    tree = [0] * (size + 1)
    inversions = 0
    for seen, v in enumerate(arr):
        r = rank[v]
        # prefix sum: how many earlier elements have rank <= r
        le, k = 0, r
        while k > 0:
            le += tree[k]
            k -= k & -k
        inversions += seen - le
        k = r
        while k <= size:
            tree[k] += 1
            k += k & -k
    return inversions


def parse_user_list(text: str, max_len: int | None = 200) -> list[int]:
    """Parse a user-typed list of integers, e.g. ``"5, 3 -2,8"`` or ``"[5, 3, -2]"``.

    Commas and/or whitespace (including newlines) separate items; surrounding brackets are allowed.
    Every token must be an ASCII integer; the ValueError names the bad token and its position.
    Lists longer than ``max_len`` are rejected (default 200: the visualizer/menu cap).
    The rules live in :func:`sortscope.validation.parse_int_list`, shared by the CLI and the menu.
    """
    from sortscope.validation import parse_int_list

    return parse_int_list(text, max_len)
