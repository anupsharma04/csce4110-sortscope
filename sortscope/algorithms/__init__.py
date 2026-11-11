"""Counted sort implementations used for benchmarking (M1, owner: Ingeet). One file per sort.

All share the interface ``sort_fn(arr, counter) -> None`` (Quick Sort also takes
``pivot`` and ``rng``; the registry binds those).
"""

from sortscope.algorithms.bubble import bubble_sort
from sortscope.algorithms.insertion import insertion_sort
from sortscope.algorithms.merge import merge_sort
from sortscope.algorithms.quick import quick_sort
from sortscope.algorithms.selection import selection_sort

__all__ = ["bubble_sort", "insertion_sort", "merge_sort", "quick_sort", "selection_sort"]
