### Quick Sort pivot rules at n = 5,000

| algorithm | input | comparisons | swaps | median_ms | max_depth |
|---|---|---|---|---|---|
| quick_first | sorted | 12,507,498 | 0 | 888.149 | 1 |
| quick_first | reverse | 12,509,998 | 2,500 | 919.316 | 1 |
| quick_first | random | 95,533 | 14,434 | 9.6 | 9 |
| quick_first | many_duplicates | 81,693 | 21,185 | 8.76 | 9 |
| quick_random | sorted | 88,060 | 7,164 | 10.34 | 9 |
| quick_random | reverse | 88,311 | 9,644 | 10.636 | 9 |
| quick_random | random | 87,522 | 18,148 | 13.103 | 9 |
| quick_random | many_duplicates | 78,912 | 24,485 | 11.293 | 9 |
| quick_median3 | sorted | 77,485 | 6,664 | 7.974 | 11 |
| quick_median3 | reverse | 77,504 | 9,166 | 7.265 | 11 |
| quick_median3 | random | 90,023 | 17,968 | 12.095 | 10 |
| quick_median3 | many_duplicates | 88,845 | 23,928 | 9.848 | 10 |
