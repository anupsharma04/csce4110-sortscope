"""Input generators: length, determinism, and that each kind really has its property."""

from collections import Counter

import pytest

import random

from helpers import brute_inversions, count_inversions

from sortscope.inputs import (
    duplicates_distinct_count,
    generate,
    input_kinds,
    inversion_count,
    nearly_displaced_count,
    parse_user_list,
)

KINDS = input_kinds()
SIZES = [0, 1, 2, 3, 10, 49, 50, 100, 500, 1000, 5000]
RANDOMIZED = ["random", "nearly_sorted", "many_duplicates"]


def displaced(arr: list[int]) -> int:
    """Positions not holding the value they would hold in sorted 0..n-1."""
    return sum(1 for i, v in enumerate(arr) if v != i)


def test_kinds_match_proposal() -> None:
    assert KINDS == ["random", "sorted", "reverse", "nearly_sorted", "many_duplicates"]


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("n", SIZES)
def test_length(kind: str, n: int) -> None:
    assert len(generate(kind, n, seed=1)) == n


@pytest.mark.parametrize("kind", KINDS)
def test_negative_n_rejected(kind: str) -> None:
    with pytest.raises(ValueError):
        generate(kind, -1)


def test_unknown_kind_rejected() -> None:
    with pytest.raises(KeyError):
        generate("zigzag", 10)


@pytest.mark.parametrize("kind", KINDS)
def test_same_seed_same_output(kind: str) -> None:
    assert generate(kind, 1000, seed=42) == generate(kind, 1000, seed=42)


@pytest.mark.parametrize("kind", RANDOMIZED)
def test_different_seed_different_output(kind: str) -> None:
    assert generate(kind, 1000, seed=1) != generate(kind, 1000, seed=2)


@pytest.mark.parametrize("kind", ["random", "sorted", "reverse", "nearly_sorted"])
@pytest.mark.parametrize("n", SIZES)
def test_permutation_kinds_are_permutations_of_range(kind: str, n: int) -> None:
    assert sorted(generate(kind, n, seed=3)) == list(range(n))


@pytest.mark.parametrize("n", SIZES)
def test_sorted_and_reverse(n: int) -> None:
    assert generate("sorted", n) == list(range(n))
    assert generate("reverse", n) == list(range(n))[::-1]


def test_random_is_actually_shuffled() -> None:
    arr = generate("random", 1000, seed=0)
    assert displaced(arr) > 900  # a random permutation has ~n-1 displaced on average


@pytest.mark.parametrize("n", SIZES)
@pytest.mark.parametrize("seed", range(5))
def test_nearly_sorted_has_exact_displaced_count(n: int, seed: int) -> None:
    assert displaced(generate("nearly_sorted", n, seed)) == nearly_displaced_count(n)


@pytest.mark.parametrize("n", [100, 500, 1000, 2000, 5000, 10_000, 100_000])
def test_nearly_sorted_is_about_five_percent(n: int) -> None:
    frac = displaced(generate("nearly_sorted", n, seed=0)) / n
    assert abs(frac - 0.05) < 0.005


def test_nearly_sorted_tiny_sizes() -> None:
    assert nearly_displaced_count(0) == nearly_displaced_count(1) == 0
    assert nearly_displaced_count(2) == 2
    assert generate("nearly_sorted", 2, seed=0) == [1, 0]


@pytest.mark.parametrize("n", SIZES)
def test_duplicates_have_few_distinct_values(n: int) -> None:
    arr = generate("many_duplicates", n, seed=4)
    k = duplicates_distinct_count(n)
    assert k == max(1, n // 50)
    assert all(0 <= v < k for v in arr)
    assert len(set(arr)) <= k


@pytest.mark.parametrize("n", [1000, 5000, 100_000])
def test_duplicates_really_repeat(n: int) -> None:
    arr = generate("many_duplicates", n, seed=0)
    k = duplicates_distinct_count(n)
    counts = Counter(arr)
    assert len(counts) == k               # with ~50 copies expected, every value appears
    assert sum(counts.values()) / len(counts) == pytest.approx(50, rel=0.05)


def test_inversion_count_matches_brute_force_and_merge_count() -> None:
    rng = random.Random(7)
    for _ in range(300):
        arr = [rng.randint(-15, 15) for _ in range(rng.randint(0, 50))]
        assert inversion_count(arr) == brute_inversions(arr) == count_inversions(arr)


@pytest.mark.parametrize("n", [0, 1, 2, 10, 1000])
def test_inversion_count_extremes(n: int) -> None:
    assert inversion_count(generate("sorted", n)) == 0
    assert inversion_count(generate("reverse", n)) == n * (n - 1) // 2


def test_inversion_count_orders_the_input_kinds() -> None:
    n = 2000
    inv = {k: inversion_count(generate(k, n, seed=0)) for k in input_kinds()}
    # random permutation: E[inv] = n(n-1)/4
    assert inv["random"] == pytest.approx(n * (n - 1) / 4, rel=0.05)
    assert inv["sorted"] < inv["nearly_sorted"] < inv["random"] < inv["reverse"]
    # many_duplicates: ties are not inversions, so E[inv] = n(n-1)/4 · (1 - 1/k)
    k = duplicates_distinct_count(n)
    assert inv["many_duplicates"] == pytest.approx(n * (n - 1) / 4 * (1 - 1 / k), rel=0.05)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("5, 3, -2, 8", [5, 3, -2, 8]),
        ("5 3 -2 8", [5, 3, -2, 8]),
        ("[5,3,-2,8]", [5, 3, -2, 8]),
        ("  7  ", [7]),
        ("1,,2", [1, 2]),
        ("﻿4, 2", [4, 2]),   # byte-order mark from Windows PowerShell pipes
    ],
)
def test_parse_user_list(text: str, expected: list[int]) -> None:
    assert parse_user_list(text) == expected


@pytest.mark.parametrize("text", ["", "   ", "[]", "1, two, 3", "1.5"])
def test_parse_user_list_rejects_bad_input(text: str) -> None:
    with pytest.raises(ValueError):
        parse_user_list(text)


def test_parse_user_list_length_limit() -> None:
    with pytest.raises(ValueError):
        parse_user_list(" ".join(["1"] * 11), max_len=10)
    assert len(parse_user_list(" ".join(["1"] * 10), max_len=10)) == 10
