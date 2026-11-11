### Log–log slopes of key comparisons

Same fit as the runtime slopes, but on the deterministic comparison counts (n ≥ 500), so timing noise cannot affect it. Bubble/Insertion on sorted input make n−1 comparisons → slope 1.

| algorithm | random | sorted | reverse | nearly_sorted | many_duplicates |
|---|---|---|---|---|---|
| bubble | 2.00 (n²) | 1.00 (n) | 2.00 (n²) | 2.01 (n²) | 2.00 (n²) |
| selection | 2.00 (n²) | 2.00 (n²) | 2.00 (n²) | 2.00 (n²) | 2.00 (n²) |
| insertion | 1.99 (n²) | 1.00 (n) | 2.00 (n²) | 1.99 (n²) | 2.02 (n²) |
| merge | 1.13 (n log n) | 1.12 (n log n) | 1.11 (n log n) | 1.15 (n log n) | 1.13 (n log n) |
| quick_first | 1.11 (n log n) | 2.00 (n²) | 2.00 (n²) | 1.20 (n log n) | 1.14 (n log n) |
| quick_random | 1.10 (n log n) | 1.11 (n log n) | 1.11 (n log n) | 1.10 (n log n) | 1.12 (n log n) |
| quick_median3 | 1.10 (n log n) | 1.09 (n log n) | 1.09 (n log n) | 1.10 (n log n) | 1.11 (n log n) |
