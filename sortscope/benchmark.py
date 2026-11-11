"""Benchmark runner (M4, owner: Gaurav).

For every (algorithm, input type, n) in the grid, three *separate* measurement
runs are made on the same seeded input, because each kind of measurement distorts
the others (counting slows the sort down; tracemalloc slows it down much more):

1. timing  — ``trials`` runs with :class:`NullCounter` (no counting work), each on a
             fresh copy of the input, ``time.perf_counter`` around the sort call
             only, garbage collector disabled inside the timed region. We report
             every trial and the median (robust to OS hiccups).
2. counts  — one run with :class:`OpCounter` (counts are deterministic for a seed).
3. memory  — one run under ``tracemalloc``; peak traced bytes allocated *during*
             the sort (the input copy is made before tracing starts). tracemalloc
             slows Python down a lot, which is why it never overlaps timing.
             Note: Python 3.11+ frames are not traced, so the O(log n) recursion
             stack of Merge/Quick shows up in ``max_depth``, not in ``peak_kb``.

Configurations that would take too long are written to the CSV with
``status=skipped`` and a reason instead of being silently dropped.

Output: ``results/results.csv`` plus ``results/results_meta.json`` (Python version,
CPU, date, grid). Rows are written as soon as they are measured, so an interrupted
run keeps everything finished so far.

    python -m sortscope benchmark                 # full grid from the proposal
    python -m sortscope benchmark --quick         # small grid, a few seconds
    python -m sortscope benchmark --algorithms merge quick_random --sizes 1000 2000
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import math
import os
import platform
import random
import statistics
import sys
import time
import tracemalloc
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sortscope.counter import NullCounter, OpCounter
from sortscope.inputs import generate, input_kinds
from sortscope.registry import QUADRATIC, get_sort, names
from sortscope.validation import (ALLOW_OUTSIDE_FLAG, BENCH_N, RESULTS_DIR, SEED, TRIALS, check_output_path,
                                  int_arg, safe_console)

BASE_SIZES = [100, 500, 1000, 2000, 5000]           # every algorithm
LARGE_SIZES = [10_000, 50_000, 100_000]             # Merge and Quick only
FULL_SIZES = BASE_SIZES + LARGE_SIZES
# Doubling chain with two sizes >= analysis.SLOPE_MIN_N, so the quick grid still
# yields log-log slopes and doubling ratios.
QUICK_SIZES = [125, 250, 500, 1000]
QUADRATIC_CAP = 5000
# Rough cost model for the up-front estimate: the full proposal grid (2.14e9 work units, see
# Config.work_units) took 475 s on the development laptop -> 2.2e-7 s per unit.
SECONDS_PER_WORK_UNIT = 2.2e-7
LONG_RUN_WARNING_S = 120
DEFAULT_TRIALS = 5
DEFAULT_SEED = 4110

# Inputs on which the first-element pivot degrades to Θ(n²): sorted and reverse
# (the pivot is always the segment's min/max -> 1 | m-1 splits every time).
# NOT nearly sorted: with ~5% of keys displaced, in-place runs are only ~20 long,
# so pivots peel off at most a short run before a displaced key splits the
# segment well. Measured: comparisons/(n lg n) stays ≈ 5-6.5 from n=5k to 100k,
# i.e. Θ(n log n) with a large constant (≈ 4x random input).
QUICK_FIRST_BAD_INPUTS = ("sorted", "reverse")

CSV_COLUMNS = [
    "algorithm", "input_type", "n", "status", "reason",
    "trial_median_ms", "trial_times_ms",
    "comparisons", "swaps", "writes", "max_depth", "peak_kb",
    "trials", "seed", "python_version", "machine",
]


def skip_reason(algo: str, kind: str, n: int) -> str | None:
    """Why a configuration is not run, or None if it should run."""
    if algo in QUADRATIC and n > QUADRATIC_CAP:
        return f"Θ(n²) algorithm capped at n <= {QUADRATIC_CAP}"
    if algo == "quick_first" and kind in QUICK_FIRST_BAD_INPUTS and n > QUADRATIC_CAP:
        return f"first-pivot worst case (Θ(n²)) on {kind} capped at n <= {QUADRATIC_CAP}"
    return None


@dataclass
class Config:
    """One benchmark configuration: (algorithm, input type, n)."""
    algo: str
    kind: str
    n: int

    @property
    def skip(self) -> str | None:
        """Reason this configuration is not run (too slow), or None."""
        return skip_reason(self.algo, self.kind, self.n)

    def work_units(self, trials: int) -> float:
        """Rough cost estimate used only for the ETA (trials + count run + memory run)."""
        quadratic = self.algo in QUADRATIC or (self.algo == "quick_first" and self.kind in QUICK_FIRST_BAD_INPUTS)
        per_run = self.n * self.n / 2 if quadratic else self.n * math.log2(max(self.n, 2))
        return per_run * (trials + 2)


def build_grid(algorithms: list[str], kinds: list[str], sizes: list[int] | None) -> list[Config]:
    """Full proposal grid by default: every algorithm at every size, so that capped
    configurations appear in the CSV as skipped rows."""
    sizes = sorted(set(sizes)) if sizes else FULL_SIZES
    return [Config(a, k, n) for a in algorithms for k in kinds for n in sizes]


def time_one(algo: str, arr: list[int], seed: int) -> float:
    """One timing trial in milliseconds: only the sort call is inside the timed region.

    Everything else happens *before* ``t0``: copying the input (so every trial sorts the same
    unsorted data), creating the NullCounter (no counting work while timing), and building
    the sort function (which gives quick_random a fresh RNG -> identical pivots every trial).
    The garbage collector is paused so a collection can't land inside the measurement.
    """
    data = list(arr)
    counter = NullCounter()
    sort_fn = get_sort(algo, seed=seed)
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        t0 = time.perf_counter()
        sort_fn(data, counter)
        t1 = time.perf_counter()
    finally:
        if gc_was_enabled:
            gc.enable()
    return (t1 - t0) * 1000.0


def warm_up(algo: str, arr: list[int], seed: int) -> None:
    """Run the algorithm once on a tiny slice so the first timed trial isn't paying start-up costs."""
    get_sort(algo, seed=seed)(list(arr[:64]), NullCounter())


def time_trials(algo: str, arr: list[int], trials: int, seed: int) -> list[float]:
    """``trials`` back-to-back timing trials of one configuration (ms each)."""
    warm_up(algo, arr, seed)
    return [time_one(algo, arr, seed) for _ in range(trials)]


def count_run(algo: str, arr: list[int], seed: int) -> OpCounter:
    """One run with OpCounter: exact comparisons/swaps/writes/max depth (deterministic for a seed)."""
    counter = OpCounter()
    get_sort(algo, seed=seed)(list(arr), counter)
    return counter


def memory_run(algo: str, arr: list[int], seed: int) -> float:
    """Peak extra memory (KB) of one sort, measured with tracemalloc in its own run.

    The input copy, counter and sort function are created *before* tracing starts, so only
    allocations made by the sort itself count (e.g. Merge Sort's scratch buffer). Kept apart
    from timing because tracing slows Python down a lot.
    """
    data = list(arr)                # allocated before tracing: not counted
    counter = NullCounter()
    sort_fn = get_sort(algo, seed=seed)
    tracemalloc.start()
    try:
        sort_fn(data, counter)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak / 1024.0


def measure(cfg: Config, trials: int, seed: int, times: list[float] | None = None) -> dict:
    """All three measurement runs for one configuration -> one CSV row (or a skipped row).

    ``times`` lets the interleaved mode pass in timing trials it already collected.
    """
    row = {"algorithm": cfg.algo, "input_type": cfg.kind, "n": cfg.n, "trials": trials, "seed": seed,
           # Reproducibility: the CSV itself records seed, Python version and machine.
           "python_version": _PYTHON_VERSION, "machine": _MACHINE}
    reason = cfg.skip
    if reason:
        return {**row, "status": "skipped", "reason": reason}
    arr = generate(cfg.kind, cfg.n, seed)
    if times is None:
        times = time_trials(cfg.algo, arr, trials, seed)
    c = count_run(cfg.algo, arr, seed)
    peak = memory_run(cfg.algo, arr, seed)
    return {
        **row,
        "status": "ok",
        "reason": "",
        "trial_median_ms": round(statistics.median(times), 4),
        "trial_times_ms": ";".join(f"{t:.4f}" for t in times),
        "comparisons": c.comparisons,
        "swaps": c.swaps,
        "writes": c.writes,
        "max_depth": c.max_depth,
        "peak_kb": round(peak, 3),
    }


_PYTHON_VERSION = sys.version.split()[0]
_MACHINE = f"{platform.platform()} | {platform.processor() or platform.machine()} | {os.cpu_count()} cpus"


def machine_info() -> dict:
    """Python/OS/CPU/date details recorded in the sidecar JSON for reproducibility."""
    return {
        "python_version": _PYTHON_VERSION,
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine(),
        "cpu_count": os.cpu_count(),
        "date_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _fmt_secs(s: float) -> str:
    s = int(round(s))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


def estimate_seconds(grid: list[Config], trials: int) -> float:
    """Rough wall-clock estimate for a grid (calibrated on the development laptop)."""
    return SECONDS_PER_WORK_UNIT * sum(c.work_units(trials) for c in grid if not c.skip)


def run_benchmark(grid: list[Config], trials: int, seed: int, out: Path, verbose: bool = True,
                  interleave: bool = False) -> list[dict]:
    """Measure every configuration in ``grid`` and write ``out`` (CSV) plus ``<out>_meta.json``.

    Back-to-back mode (default): each configuration's trials run consecutively and its row is
    written immediately, so an interrupted run keeps everything finished so far.

    Interleaved mode: timing trial t of *every* configuration runs before trial t+1 of any,
    in a freshly shuffled (seeded) order each round. Slow drift in machine speed (boost clock,
    background load) then spreads over all configurations instead of hitting whichever one was
    running at the time. Rows are written after timing finishes.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    if verbose:
        est = estimate_seconds(grid, trials)
        print(f"estimated time ≈ {_fmt_secs(est)} for {len(grid)} configurations "
              f"({sum(c.skip is None for c in grid)} measured)", flush=True)
        if est > LONG_RUN_WARNING_S:
            print(f"warning: this is a long run (about {est / 60:.0f} min). Keep the machine idle: other programs "
                  "skew the timings. Ctrl+C stops it" +
                  ("." if interleave else "; rows finished so far stay in the CSV."), flush=True)
    meta = {
        **machine_info(),
        "trials": trials,
        "seed": seed,
        "timing_order": "interleaved (shuffled each round)" if interleave else "back-to-back per configuration",
        "timer": "time.perf_counter, gc disabled, NullCounter",
        "memory": "tracemalloc peak during sort (separate run)",
        "algorithms": sorted({c.algo for c in grid}),
        "input_types": sorted({c.kind for c in grid}),
        "sizes": sorted({c.n for c in grid}),
        "csv": out.name,
    }
    meta_path = out.with_name(out.stem + "_meta.json")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    start = time.perf_counter()
    pre_timed = _interleaved_times(grid, trials, seed, verbose, start) if interleave else {}

    total_units = sum(c.work_units(trials) for c in grid if not c.skip)
    done_units = 0.0
    rows = []
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for idx, cfg in enumerate(grid, 1):
            row = measure(cfg, trials, seed, times=pre_timed.get(idx - 1))
            writer.writerow(row)
            f.flush()
            rows.append(row)
            if row["status"] == "ok":
                done_units += cfg.work_units(trials)
            if verbose:
                elapsed = time.perf_counter() - start
                # ETA: observed seconds per work unit × remaining work units.
                eta = elapsed / done_units * (total_units - done_units) if done_units else 0.0
                what = f"{row['trial_median_ms']:>10.3f} ms" if row["status"] == "ok" else "   skipped"
                print(f"[{idx:>4}/{len(grid)}] {cfg.algo:<14} {cfg.kind:<16} n={cfg.n:<7} {what}"
                      f"   elapsed {_fmt_secs(elapsed)}  ETA {_fmt_secs(eta)}", flush=True)
    if verbose:
        ok = sum(r["status"] == "ok" for r in rows)
        print(f"wrote {out} ({ok} measured, {len(rows) - ok} skipped) and {meta_path.name} "
              f"in {_fmt_secs(time.perf_counter() - start)}")
    return rows


def _interleaved_times(grid: list[Config], trials: int, seed: int, verbose: bool,
                       start: float) -> dict[int, list[float]]:
    """Timing trials for every measured configuration, one round per trial, shuffled each round.

    Returns {index in grid: [ms per trial]}. Inputs are generated once and reused, exactly as
    in back-to-back mode (same seed -> same input for every algorithm).
    """
    todo = [i for i, c in enumerate(grid) if c.skip is None]
    inputs = {i: generate(grid[i].kind, grid[i].n, seed) for i in todo}
    for i in todo:
        warm_up(grid[i].algo, inputs[i], seed)
    times: dict[int, list[float]] = {i: [] for i in todo}
    order = list(todo)
    shuffler = random.Random(seed)            # seeded: the trial order itself is reproducible
    for t in range(trials):
        shuffler.shuffle(order)
        for i in order:
            times[i].append(time_one(grid[i].algo, inputs[i], seed))
        if verbose:
            elapsed = time.perf_counter() - start
            eta = elapsed / (t + 1) * (trials - t - 1)
            print(f"timing round {t + 1}/{trials} done ({len(order)} configurations)   "
                  f"elapsed {_fmt_secs(elapsed)}  ETA (timing) {_fmt_secs(eta)}", flush=True)
    return times


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Register the `benchmark` command's flags on ``parser``."""
    parser.add_argument("--quick", action="store_true",
                        help=f"small grid for testing: sizes {QUICK_SIZES}, 3 trials, written to results/scratch/")
    # Numbers are validated at parse time (sortscope.validation). Sizes stop at 100,000, the
    # largest size in the proposal; Θ(n²) cases above 5,000 are still run as "skipped" rows.
    size_hint = (f"the proposal's grid goes up to {BENCH_N[1]:,}; Θ(n²) sorts above {QUADRATIC_CAP:,} "
                 "are recorded as skipped")
    parser.add_argument("--sizes", type=int_arg("--sizes value", *BENCH_N, hint=size_hint), nargs="+",
                        help=f"override sizes, each {BENCH_N[0]}-{BENCH_N[1]:,} (default {FULL_SIZES})")
    parser.add_argument("--algorithms", nargs="+", choices=names(), default=names(), metavar="ALGO",
                        help=f"subset of: {', '.join(names())}")
    parser.add_argument("--types", nargs="+", choices=input_kinds(), default=input_kinds(), metavar="KIND",
                        help=f"subset of: {', '.join(input_kinds())}")
    parser.add_argument("--trials", type=int_arg("--trials", *TRIALS),
                        help=f"timing trials per configuration, {TRIALS[0]}-{TRIALS[1]} (default {DEFAULT_TRIALS})")
    parser.add_argument("--seed", type=int_arg("--seed", *SEED), default=DEFAULT_SEED)
    parser.add_argument("--interleave", action="store_true",
                        help="run timing trial t of every configuration before trial t+1 (shuffled each round) "
                             "so machine-speed drift is spread out; recommended for final results")
    parser.add_argument("--out", type=Path, help="CSV path inside results/ (default results/results.csv)")
    parser.add_argument(ALLOW_OUTSIDE_FLAG, action="store_true", help="allow --out outside results/")


def run(args: argparse.Namespace) -> int:
    """`sortscope benchmark`: validate the output path, build the grid, run it."""
    sizes = args.sizes or (QUICK_SIZES if args.quick else None)
    trials = args.trials if args.trials is not None else (3 if args.quick else DEFAULT_TRIALS)
    out = args.out or (RESULTS_DIR / "scratch" / "results_quick.csv" if args.quick else RESULTS_DIR / "results.csv")
    try:
        out = check_output_path(out, suffixes=(".csv",), allow_outside=args.allow_outside_results)
    except ValueError as e:
        raise SystemExit(f"error: {e}") from None
    grid = build_grid(args.algorithms, args.types, sizes)
    try:
        run_benchmark(grid, trials, args.seed, out, interleave=args.interleave)
    except OSError as e:  # read-only file/folder, path is a directory, disk full, ...
        raise SystemExit(f"error: cannot write benchmark results to {out}: {e.strerror or e}") from None
    return 0


def main(argv: list[str] | None = None) -> int:
    """Standalone entry point: ``python -m sortscope.benchmark``."""
    safe_console()
    parser = argparse.ArgumentParser(prog="sortscope.benchmark", description="Run the SortScope benchmark grid.")
    add_arguments(parser)
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
