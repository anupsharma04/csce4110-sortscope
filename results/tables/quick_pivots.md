### Quick Sort pivot rules at n = 5,000

| algorithm | input | comparisons | swaps | median_ms | max_depth |
|---|---|---|---|---|---|
| quick_first | sorted | 12,507,498 | 0 | 763.156 | 1 |
| quick_first | reverse | 12,509,998 | 2,500 | 757.137 | 1 |
| quick_first | random | 95,533 | 14,434 | 8.62 | 9 |
| quick_first | many_duplicates | 81,693 | 21,185 | 9.194 | 9 |
| quick_random | sorted | 88,060 | 7,164 | 9.118 | 9 |
| quick_random | reverse | 88,311 | 9,644 | 9.306 | 9 |
| quick_random | random | 87,522 | 18,148 | 10.25 | 9 |
| quick_random | many_duplicates | 78,912 | 24,485 | 10.3 | 9 |
| quick_median3 | sorted | 77,485 | 6,664 | 6.737 | 11 |
| quick_median3 | reverse | 77,504 | 9,166 | 6.93 | 11 |
| quick_median3 | random | 90,023 | 17,968 | 9.124 | 10 |
| quick_median3 | many_duplicates | 88,845 | 23,928 | 16.764 | 10 |
