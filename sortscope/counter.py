"""Operation counters (M1, owner: Ingeet).

Every sort performs *all* key comparisons and *all* array mutations through a
counter object, so no operation can be missed and the counting rules live in
exactly one place:

* ``less(a, b)``      -> ``a < b``; +1 comparison.
* ``swap(arr, i, j)`` -> exchange ``arr[i]`` and ``arr[j]``; +1 swap, +2 writes.
* ``write(arr, i, v)``-> ``arr[i] = v``; +1 write.
* ``note_depth(d)``   -> records the maximum recursion depth reached (Merge/Quick).

Counting definitions (identical for every algorithm, also documented in README):

* comparison = one key-vs-key comparison between two elements (loop-index and
  bounds checks are never counted).
* swap       = an exchange of two array slots that is actually performed.
* write      = an assignment of an element into the *input array* (a swap is
  2 writes; an insertion shift is 1; placing the insertion key is 1; a merge
  copy-back is 1). Copies into scratch buffers are not writes.

Only ``<`` is ever used to compare keys. That keeps the algorithms honest about
stability (ties are never broken by a hidden ``<=``) and lets tests sort record
objects whose ``__lt__`` looks at the key only.
"""

from __future__ import annotations

from typing import Any


class OpCounter:
    """Counts comparisons, swaps, writes and max recursion depth."""

    __slots__ = ("comparisons", "swaps", "writes", "max_depth")

    def __init__(self) -> None:
        self.comparisons = 0
        self.swaps = 0
        self.writes = 0
        self.max_depth = 0

    def less(self, a: Any, b: Any) -> bool:
        """Return ``a < b`` and count one comparison."""
        self.comparisons += 1
        return a < b

    def swap(self, arr: list, i: int, j: int) -> None:
        """Exchange ``arr[i]`` and ``arr[j]``: one swap, two writes."""
        self.swaps += 1
        self.writes += 2
        arr[i], arr[j] = arr[j], arr[i]

    def write(self, arr: list, i: int, value: Any) -> None:
        """Assign ``arr[i] = value``: one write."""
        self.writes += 1
        arr[i] = value

    def note_depth(self, depth: int) -> None:
        """Record that a recursive call at ``depth`` (root = 1) did work."""
        if depth > self.max_depth:
            self.max_depth = depth

    def as_dict(self) -> dict[str, int]:
        """The four counters as a plain dict (used for CSV rows and test comparisons)."""
        return {
            "comparisons": self.comparisons,
            "swaps": self.swaps,
            "writes": self.writes,
            "max_depth": self.max_depth,
        }

    def __repr__(self) -> str:
        return f"OpCounter({self.as_dict()})"


class NullCounter(OpCounter):
    """Same interface as :class:`OpCounter` but records nothing.

    Used for timing runs. It still costs one Python method call per operation;
    that overhead is the same constant factor for every algorithm, so it does
    not change log-log slopes or doubling ratios (see README, "Measurement").
    All fields stay 0.
    """

    __slots__ = ()

    def less(self, a: Any, b: Any) -> bool:
        """Return ``a < b`` without counting (timing runs)."""
        return a < b

    def swap(self, arr: list, i: int, j: int) -> None:
        """Exchange ``arr[i]`` and ``arr[j]`` without counting."""
        arr[i], arr[j] = arr[j], arr[i]

    def write(self, arr: list, i: int, value: Any) -> None:
        """Assign ``arr[i] = value`` without counting."""
        arr[i] = value

    def note_depth(self, depth: int) -> None:
        """Ignore recursion depth (timing runs)."""
        pass
