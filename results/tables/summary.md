### Summary — random input, measurements at n = 5,000

One row per algorithm. n = 5,000 is the largest size every algorithm ran.

- **expected**: growth class on random input
- **slope**: log–log fit of runtime over n ≥ 500 (≈2 for n², ≈1.0–1.15 for n log n)
- **T(2m)/T(m)**: doubling ratio (≈4 for n², slightly above 2 for n log n)
- **median ms**: median runtime at n = 5,000
- **comparisons / swaps / writes**: exact operation counts at n = 5,000
- **peak KB / max depth**: tracemalloc peak memory and recursion depth at n = 5,000

| algorithm            | expected | slope | T(2000)/T(1000) | median ms | comparisons |     swaps |     writes | peak KB | max depth | stable |
|----------------------|----------|------:|----------------:|----------:|------------:|----------:|-----------:|--------:|----------:|--------|
| Bubble (early exit)  | n²       |  2.09 |            4.31 |  1689.047 |  12,496,597 | 6,208,308 | 12,416,616 |    0.23 |         0 | yes    |
| Selection            | n²       |  1.99 |            3.78 |   848.996 |  12,497,500 |     4,988 |      9,976 |   0.262 |         0 | no     |
| Insertion            | n²       |  2.02 |            3.90 |   923.361 |   6,213,301 |         0 |  6,213,307 |   0.137 |         0 | yes    |
| Merge                | n log n  |  1.11 |            1.92 |    15.308 |      55,207 |         0 |     61,808 |  40.043 |        13 | yes    |
| Quick (first pivot)  | n log n  |  1.10 |            1.99 |       9.6 |      95,533 |    14,434 |     28,868 |   0.805 |         9 | no     |
| Quick (random pivot) | n log n  |  1.07 |            2.07 |    13.103 |      87,522 |    18,148 |     36,296 |    1.07 |         9 | no     |
| Quick (median-of-3)  | n log n  |  1.08 |            2.07 |    12.095 |      90,023 |    17,968 |     35,936 |   0.742 |        10 | no     |
| Heap                 | n log n  |  1.15 |            2.05 |    17.209 |     107,724 |    57,176 |    114,352 |   0.211 |         0 | no     |
