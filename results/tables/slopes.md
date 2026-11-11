### Log–log slopes of runtime

numpy.polyfit(log n, log t, 1) over measured sizes n ≥ 500. In parentheses: the growth class expected for that algorithm on that input (slope ≈ 2 for n², ≈ 1 for n, ≈ 1.0–1.15 for n log n).

| algorithm | random | sorted | reverse | nearly_sorted | many_duplicates |
|---|---|---|---|---|---|
| bubble | 2.15 (n²) | 0.90 (n) | 2.04 (n²) | 2.15 (n²) | 2.16 (n²) |
| selection | 2.05 (n²) | 1.62 (n²) | 2.02 (n²) | 2.04 (n²) | 1.99 (n²) |
| insertion | 2.13 (n²) | 1.04 (n) | 2.06 (n²) | 2.02 (n²) | 2.08 (n²) |
| merge | 1.11 (n log n) | 1.12 (n log n) | 1.12 (n log n) | 1.12 (n log n) | 1.14 (n log n) |
| quick_first | 1.12 (n log n) | 2.03 (n²) | 2.05 (n²) | 1.13 (n log n) | 1.11 (n log n) |
| quick_random | 1.09 (n log n) | 1.08 (n log n) | 1.08 (n log n) | 1.06 (n log n) | 0.98 (n log n) |
| quick_median3 | 1.11 (n log n) | 1.08 (n log n) | 1.08 (n log n) | 1.09 (n log n) | 1.09 (n log n) |
