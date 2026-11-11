# SortScope

Sorting-algorithm visualizer and benchmark tool — CSCE 4110 (Algorithms), University of North Texas, Fall 2026.
Team **Big O Squad**: Ingeet Adhikari, Anup Sharma, Gaurav Bhandari.

SortScope implements Bubble (early exit), Selection, Insertion, Merge and Quick Sort (first / random / median-of-three
pivot). Every sort counts its key comparisons, swaps and array writes through one shared counter. A matplotlib
animation shows each sort step by step. A benchmark runner measures runtime, operation counts and peak memory over
five input types and sizes from 100 to 100,000. The analysis module checks the measurements against theory: closed-form
counts, log–log slopes, doubling ratios and normalized runtime.

## Dependencies

Python 3.11 or newer (developed on 3.13). `requirements.txt` pins exact versions of matplotlib, pillow, numpy,
pandas, pytest and hypothesis, the versions the committed results were made with. hypothesis is used only by the
property-based tests (`tests/test_properties.py`); if it isn't installed, that file is skipped and the rest of the
suite still runs.
Saving `.mp4` animations also needs `ffmpeg` on your PATH; `.gif` needs nothing extra.

## Setup

```bash
python -m venv .venv
# Windows (PowerShell):  .venv\Scripts\Activate.ps1      macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q          # all tests should pass
```

## How to run every mode

| What | Command |
|---|---|
| Interactive menu (every demo part, with size and speed prompts) | `python -m sortscope` |
| Animate one sort | `python -m sortscope visualize --algo insertion --input nearly_sorted --n 40` |
| Animate your own list | `python -m sortscope visualize --algo merge --list "5 3 9 1 7" --interval 300` |
| Demo part 2: all 7 algorithms racing on one 40-item input | `python -m sortscope visualize --demo all --n 40` |
| Demo part 3: Insertion, nearly sorted vs reverse | `python -m sortscope visualize --demo insertion --n 40` |
| Demo part 3 (extended): Insertion on all 5 input types | `python -m sortscope visualize --demo inputs --n 40` |
| Demo part 4: Quick first vs median-of-3 on sorted | `python -m sortscope visualize --demo quick --n 40` |
| Several panels of your choice (up to 8) | `python -m sortscope visualize --algo quick_first quick_random --input sorted` |
| Faster / slower animation | add `--steps-per-frame 5` and/or `--interval 20` (ms per frame) |
| Save an animation | add `--save results/figures/demo.gif` (or `.mp4`) |
| Sort your own list, all algorithms | `python -m sortscope sort "5, 3, 9, 1, 7, 3"` |
| Sort a long list (file or stdin) | `python -m sortscope sort --file numbers.txt --algo merge quick_median3`, or `... sort -` to read stdin |
| Quick benchmark (seconds) | `python -m sortscope benchmark --quick` → `results/scratch/results_quick.csv` |
| Full benchmark (≈10–20 min) | `python -m sortscope benchmark` → `results/results.csv` + `results_meta.json` |
| Custom benchmark | `python -m sortscope benchmark --algorithms merge quick_random --types random --sizes 1000 2000 4000 --out results/scratch/custom.csv` (without `--out` it **overwrites** `results/results.csv`) |
| Plot a scratch run | `python -m sortscope plot --csv results/scratch/custom.csv --out results/scratch` |
| Figures + tables | `python -m sortscope plot` → `results/figures/`, `results/tables/` |
| Tests | `python -m sortscope test` (same as `python -m pytest -q`) |

**Input rules** (one place: `sortscope/validation.py`, shared by the CLI and the menu). Bad input gets a message
saying what is allowed; the menu asks again instead of stopping; Ctrl+C exits cleanly.

| Input | Allowed |
|---|---|
| `visualize --n` | whole number 0–200 |
| `benchmark --sizes` | whole numbers 1–100,000 (Θ(n²) sorts above 5,000 are recorded as skipped) |
| `--trials` / `--seed` | 1–100 / 0–4,294,967,295 |
| `--interval` / `--steps-per-frame` | 1–10,000 |
| typed lists | integers separated by commas and/or spaces; ≤ 200 items for `visualize --list` and the menu, ≤ 10,000 for `sort` |
| algorithm / input names | exactly the names below (the error lists them) |
| output paths (`--out`, `--save`) | must be inside `results/` with the right extension (`.csv`, `.gif`/`.mp4`); add `--allow-outside-results` to write elsewhere on purpose |

Algorithm names: `bubble selection insertion merge quick_first quick_random quick_median3`.
Input types: `random sorted reverse nearly_sorted many_duplicates`.

## Example output

```
$ python -m sortscope sort "5, 3, 9, 1, 7, 3"
input:  [5, 3, 9, 1, 7, 3]
sorted: [1, 3, 3, 5, 7, 9]

algorithm              comparisons   swaps  writes   time ms  stable
Bubble (early exit)             14       8      16    0.0025  yes
Selection                       15       2       4    0.0021  no
Insertion                       11       0      13    0.0020  yes
Merge                           11       0      16    0.0055  yes
Quick (first pivot)             23       4       8    0.0048  no
Quick (random pivot)            27       9      18    0.0081  no
Quick (median-of-3)             33       7      14    0.0056  no

time ms: median of 5 runs without counting (NullCounter); counts are exact, times vary by machine
```

The counts are the same on every machine. The time column is measured in a separate run with `NullCounter`
(median of 5 runs; a single run for lists over 2,000 items), so it will differ from the numbers above.

Bar colors in the visualizer: yellow = compared, red with an outline = swapped/written, violet = pivot,
green = in its final position, gray = untouched. Live counters under the bars show the step number,
comparisons, swaps and writes.

Controls in the visualizer window (plain matplotlib widgets, no extra dependency):

- **Start / Pause / Restart** buttons; the keys still work too: **space** pauses/resumes, **r** restarts from
  the original unsorted input (hints are shown in the top-right corner).
- **n** slider (5–200) and **speed** slider (events applied per frame).
- **algorithm** and **input** radio buttons, when the window shows a single panel (the side-by-side demos keep
  their fixed pairing).

Changing n, the algorithm or the input loads the new unsorted list and waits for Start (or space). Saved
GIF/MP4 files contain no controls.

## How operations are counted

Every sort goes through one counter object, `sortscope/counter.py`: `less(a, b)`, `swap(arr, i, j)`, `write(arr, i, v)`.

- **comparison**: one key-vs-key comparison between two elements, including the 2–3 comparisons that
  median-of-three uses to pick a pivot. Loop-index and bounds checks are not counted.
- **swap**: an exchange of two array positions that actually happens. Selection Sort skips swapping an element with itself.
- **write**: an assignment of an element into the input array. A swap counts as 2 writes, an Insertion Sort shift
  as 1, placing the insertion key as 1 (always written back, even if it didn't move), and a merge copy-back as 1.
  Copies into Merge Sort's scratch buffer are not writes.

These rules give exact formulas, which `tests/test_counts.py` asserts. The derivations are in comments there.

| Algorithm | Exact result asserted |
|---|---|
| Selection | comparisons = n(n−1)/2 for every input; reverse → ⌊n/2⌋ swaps |
| Bubble (early exit) | sorted → n−1 comparisons, 0 swaps; reverse → n(n−1)/2 comparisons and swaps; swaps = inversions |
| Insertion | shifts = inversions; writes = inversions + n − 1; comparisons = inversions + n − 1 − (# strict prefix minima) |
| Merge | writes = n⌈lg n⌉ − 2^⌈lg n⌉ + n; comparisons ≤ n⌈lg n⌉ − 2^⌈lg n⌉ + 1, and an input reaching the bound exists |
| Quick, first pivot, sorted | comparisons = (n² + 3n − 4)/2, 0 swaps |
| Quick, first pivot, all equal | balanced splits: C(m) = C(⌈m/2⌉) + C(⌊m/2⌋) + m + 1 + [m even] |
| Quick, random pivot | mean over 200 seeds within 4 standard errors of the exact expectation, and within 10% of 2n ln n |

**Design notes.**
- Quick Sort uses Hoare partitioning. Lomuto becomes Θ(n²) when there are many duplicates; Hoare doesn't.
- Quick Sort recurses on the smaller part and loops on the larger, so the recursion depth is ≤ ⌊lg n⌋ + 1 for every
  pivot rule.
- Merge Sort allocates one scratch buffer of size n, once.
- Timing runs use `NullCounter`, which keeps the same method calls but does no counting. That adds the same constant
  factor to every algorithm, so slopes and doubling ratios are unaffected.

**Input definitions** (`sortscope/inputs.py`, each takes `(n, seed)`):
- random: a random ordering of 0..n−1 (no repeated values)
- sorted / reverse: 0..n−1 in order / in reverse
- nearly sorted: exactly round(0.05·n) positions (at least 2) rotated along a random cycle, so ≈5% are out of place
- many duplicates: values drawn from `range(max(1, n // 50))`

## Measurement method

For each configuration, three separate runs use the same seeded input:
1. timing: 5 trials with `NullCounter`, a fresh copy of the input for each trial, `time.perf_counter`, garbage
   collector off; the median is reported;
2. counts: one run with `OpCounter`;
3. memory: one run under `tracemalloc`, recording the peak allocated during the sort.

> **Run the full benchmark on a quiet machine.** Close other programs, plug in the laptop, and don't run tests,
> plots or a second benchmark at the same time. Competing CPU load makes doubling ratios jump around (we saw
> ratios of 7.6 for a quadratic sort when tests were running alongside). Operation counts are unaffected:
> they're deterministic.

The benchmark prints an estimated duration first and warns when a run will take more than about 2 minutes.
With `--interleave`, timing trial t of *every* configuration runs before trial t+1 of any, in a shuffled order,
so slow drift in machine speed is spread across all configurations instead of landing on one. Use it for final
results. The committed `results/results.csv` was produced in the default back-to-back mode.

Θ(n²) sorts, and Quick with first pivot on sorted or reverse input, are capped at n ≤ 5000. Larger
configurations appear in the CSV as `status=skipped` with a reason. Two limits of tracemalloc to keep in mind:
- In-place sorts show about 0.1–1.1 KB rather than exactly 0, from small Python bookkeeping objects (the RNG
  state for random pivots, for example).
- Python 3.11+ doesn't trace call frames, so the O(log n) recursion stack is reported in the `max_depth` column
  instead of in `peak_kb`.

## Repository layout

```
sortscope/
  __main__.py      menu + CLI (visualize | benchmark | plot | sort | test)
  counter.py       OpCounter, NullCounter (the counting rules live here)
  registry.py      algorithm name -> sort function + complexity/stability metadata
  inputs.py        input generators (n, seed), inversion_count, parse_user_list
  algorithms/      counted sorts used by the benchmark (one file per sort)
  steps/           the same sorts as event generators for the visualizer
  visualizer.py    matplotlib FuncAnimation bars, side-by-side mode, GIF/MP4 export
  benchmark.py     timing / counting / memory runs -> results/results.csv
  analysis.py      figures, slopes, doubling ratios, Markdown tables
tests/             correctness, stability, exact counts, step equivalence, inputs, benchmark, CLI
results/           results.csv, results_meta.json, figures/, tables/   (scratch/ is git-ignored)
scripts/           reproduce_all.sh, reproduce_all.ps1
```

## Reproducing every figure

```bash
bash scripts/reproduce_all.sh        # macOS / Linux / Git Bash: tests -> benchmark -> plots -> demo GIFs
```
```powershell
powershell -ExecutionPolicy Bypass -File scripts\reproduce_all.ps1   # Windows PowerShell (same steps)
```
On Windows, plain PowerShell's `bash` is the WSL launcher and fails unless a Linux distro is installed. Use the
`.ps1` script, or run the `.sh` script from Git Bash.

or step by step: `python -m pytest -q`, `python -m sortscope benchmark`, `python -m sortscope plot`.
Every random choice is seeded (default seed 4110, recorded in the CSV and `results_meta.json`), so all operation
counts reproduce exactly. Runtimes depend on the machine; `results_meta.json` records the Python version, CPU and date.

`results/figures/captions.md` lists every figure with its numbered caption. `results/tables/` has the slopes,
doubling ratios, pivot comparison, inversion table, runtime table and skipped configurations, all as Markdown.

## Contributions

| Module | Owner |
|---|---|
| M1 Sorting Engine, M2 Input Generator | Ingeet Adhikari |
| M3 Visualizer (step generators), Tests | Anup Sharma |
| M4 Benchmark Runner, M5 Results & Plots, Menu | Gaurav Bhandari |
