### Doubling ratio T(2n)/T(n) — random input

≈4 → Θ(n²); slightly above 2 → Θ(n log n); ≈2 → Θ(n).

| algorithm | 500→1000 | 1000→2000 | 5000→10000 | 50000→100000 |
|---|---|---|---|---|
| bubble | 4.53 | 4.24 | — | — |
| selection | 4.28 | 3.65 | — | — |
| insertion | 4.28 | 4.3 | — | — |
| merge | 2.24 | 2.2 | 2.18 | 2.07 |
| quick_first | 2.07 | 2.38 | 2.14 | 2.03 |
| quick_random | 2.28 | 2.12 | 2.29 | 2.26 |
| quick_median3 | 2.21 | 2.19 | 2.13 | 2.11 |

### Doubling ratio T(2n)/T(n) — sorted input

≈4 → Θ(n²); slightly above 2 → Θ(n log n); ≈2 → Θ(n).

| algorithm | 500→1000 | 1000→2000 | 5000→10000 | 50000→100000 |
|---|---|---|---|---|
| bubble | 1.33 | 2.06 | — | — |
| selection | 3.45 | 2.15 | — | — |
| insertion | 2.06 | 2.08 | — | — |
| merge | 2.22 | 2.24 | 2.83 | 2.16 |
| quick_first | 4.34 | 4.06 | — | — |
| quick_random | 2.14 | 2.14 | 2.21 | 2.04 |
| quick_median3 | 2.18 | 2.14 | 2.12 | 2.12 |

### Doubling ratio T(2n)/T(n) — reverse input

≈4 → Θ(n²); slightly above 2 → Θ(n log n); ≈2 → Θ(n).

| algorithm | 500→1000 | 1000→2000 | 5000→10000 | 50000→100000 |
|---|---|---|---|---|
| bubble | 4.59 | 4.95 | — | — |
| selection | 4.1 | 3.98 | — | — |
| insertion | 4.5 | 4.01 | — | — |
| merge | 2.28 | 2.21 | 2.17 | 2.12 |
| quick_first | 4.27 | 4.08 | — | — |
| quick_random | 2.14 | 2.18 | 2.15 | 2.05 |
| quick_median3 | 2.18 | 2.13 | 2.13 | 2.17 |

### Doubling ratio T(2n)/T(n) — nearly sorted input

≈4 → Θ(n²); slightly above 2 → Θ(n log n); ≈2 → Θ(n).

| algorithm | 500→1000 | 1000→2000 | 5000→10000 | 50000→100000 |
|---|---|---|---|---|
| bubble | 4.7 | 4.7 | — | — |
| selection | 3.25 | 3.73 | — | — |
| insertion | 4.2 | 3.98 | — | — |
| merge | 2.27 | 2.18 | 2.13 | 2.1 |
| quick_first | 3.1 | 1.03 | 2.23 | 1.75 |
| quick_random | 2.15 | 2.08 | 1.97 | 2.06 |
| quick_median3 | 2.17 | 2.21 | 2.11 | 2.24 |

### Doubling ratio T(2n)/T(n) — many duplicates input

≈4 → Θ(n²); slightly above 2 → Θ(n log n); ≈2 → Θ(n).

| algorithm | 500→1000 | 1000→2000 | 5000→10000 | 50000→100000 |
|---|---|---|---|---|
| bubble | 5.39 | 3.95 | — | — |
| selection | 4.81 | 3.87 | — | — |
| insertion | 4.66 | 4.2 | — | — |
| merge | 2.28 | 2.28 | 2.27 | 2.16 |
| quick_first | 2.39 | 2.13 | 1.86 | 2.14 |
| quick_random | 2.11 | 1.76 | 2.67 | 2.0 |
| quick_median3 | 2.3 | 2.02 | 1.15 | 2.08 |
