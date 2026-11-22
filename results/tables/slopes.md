### Log–log slopes of runtime

numpy.polyfit(log n, log t, 1) over measured sizes n ≥ 500. In parentheses: the growth class expected for that algorithm on that input (slope ≈ 2 for n², ≈ 1 for n, ≈ 1.0–1.15 for n log n).

| algorithm     | random         | sorted         | reverse        | nearly_sorted  | many_duplicates |
|---------------|----------------|----------------|----------------|----------------|-----------------|
| bubble        | 2.09 (n²)      | 1.07 (n)       | 2.06 (n²)      | 2.09 (n²)      | 2.10 (n²)       |
| selection     | 1.99 (n²)      | 2.01 (n²)      | 2.05 (n²)      | 2.00 (n²)      | 2.00 (n²)       |
| insertion     | 2.02 (n²)      | 0.95 (n)       | 2.12 (n²)      | 2.04 (n²)      | 2.08 (n²)       |
| merge         | 1.11 (n log n) | 1.09 (n log n) | 1.11 (n log n) | 1.12 (n log n) | 1.12 (n log n)  |
| quick_first   | 1.10 (n log n) | 2.04 (n²)      | 2.06 (n²)      | 1.19 (n log n) | 1.12 (n log n)  |
| quick_random  | 1.07 (n log n) | 1.06 (n log n) | 1.07 (n log n) | 1.07 (n log n) | 1.09 (n log n)  |
| quick_median3 | 1.08 (n log n) | 1.10 (n log n) | 1.06 (n log n) | 1.10 (n log n) | 1.11 (n log n)  |
| heap          | 1.15 (n log n) | 1.15 (n log n) | 1.15 (n log n) | 1.14 (n log n) | 1.17 (n log n)  |
