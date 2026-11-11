"""Results analysis: figures, fitted slopes, doubling ratios, Markdown tables (M5, owner: Gaurav).

Reads ``results/results.csv`` (written by ``benchmark.py``) and writes
* ``results/figures/figNN_*.png`` + ``figNN_*.txt`` (numbered caption) and ``captions.md``
* ``results/tables/*.md`` (drop straight into the report)

    python -m sortscope plot                       # uses results/results.csv
    python -m sortscope plot --csv results/scratch/results_quick.csv --out results/scratch

Method notes (also in the captions):
* Log-log slope: least-squares fit of log t = b·log n + c with numpy.polyfit over
  every measured size >= SLOPE_MIN_N (very small n is dominated by fixed Python
  call overhead, not by the algorithm's growth). Expect b ≈ 2 for Θ(n²) and
  b ≈ 1.0–1.15 for Θ(n log n) over this size range.
* Doubling ratio T(2n)/T(n): ≈ 4 for Θ(n²); ≈ 2·(1 + 1/lg n) (slightly above 2)
  for Θ(n log n); ≈ 2 for Θ(n).
* Normalized time t/n² or t/(n lg n) flattens to the hidden constant when the
  model is right.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd

from sortscope.inputs import generate, input_kinds, inversion_count
from sortscope.registry import QUADRATIC, QUICK_VARIANTS, get_info, names
from sortscope.validation import ALLOW_OUTSIDE_FLAG, RESULTS_DIR, check_output_path, safe_console

SLOPE_MIN_N = 500

# Categorical palette (dataviz reference, light mode), assigned to algorithms in a
# fixed order so an algorithm has the same color in every figure.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
ALGO_COLOR = {name: SERIES[i] for i, name in enumerate(names())}
MARKERS = {"bubble": "o", "selection": "s", "insertion": "^", "merge": "D",
           "quick_first": "v", "quick_random": "P", "quick_median3": "X"}
SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
KIND_LABEL = {"random": "random", "sorted": "sorted", "reverse": "reverse",
              "nearly_sorted": "nearly sorted", "many_duplicates": "many duplicates"}


# --------------------------------------------------------------------------- theory
def theory_n_choose_2(n: np.ndarray) -> np.ndarray:
    """n(n-1)/2: Selection's exact comparisons; Bubble/Insertion worst case."""
    return n * (n - 1) / 2


def theory_n_lg_n(n: np.ndarray) -> np.ndarray:
    """n lg n reference curve."""
    return n * np.log2(n)


def theory_merge_worst(n: np.ndarray) -> np.ndarray:
    """Merge Sort's exact worst-case comparisons: n⌈lg n⌉ - 2^⌈lg n⌉ + 1."""
    k = np.ceil(np.log2(n))
    return n * k - 2**k + 1


def theory_2n_ln_n(n: np.ndarray) -> np.ndarray:
    """Leading term of random-pivot Quick Sort's expected comparisons."""
    return 2 * n * np.log(n)


def hoare_random_expected(n_max: int) -> np.ndarray:
    """E(m) for m = 0..n_max: exact expected comparisons of our Hoare Quick Sort with a
    uniform random pivot (derivation in tests/test_counts.py)."""
    e = np.zeros(n_max + 1)
    s = 0.0
    for m in range(2, n_max + 1):
        e[m] = m + 2 - 1 / m + (e[m - 1] + 2 * s) / m
        s += e[m]
    return e


# --------------------------------------------------------------------------- data
class ResultsError(ValueError):
    """The results CSV is missing, empty, or not a SortScope results file."""


REQUIRED_COLUMNS = ["algorithm", "input_type", "n", "status", "trial_median_ms",
                    "comparisons", "swaps", "writes", "max_depth", "peak_kb", "trials", "seed"]
NUMERIC_COLUMNS = ["n", "trial_median_ms", "comparisons", "swaps", "writes", "max_depth", "peak_kb", "trials", "seed"]


def load(csv_path: Path, warn=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (measured rows, skipped rows), validating the file first.

    * empty file / wrong columns / no measured rows -> ResultsError with a readable message
    * individual malformed rows (non-numeric or missing values in a measured row, unknown
      algorithm or input name) are dropped, and ``warn`` is called with their CSV line numbers,
      so one bad line doesn't throw away a 10-minute benchmark.
    """
    import sys

    warn = warn or (lambda msg: print(f"warning: {msg}", file=sys.stderr))
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        raise ResultsError(f"{csv_path} not found — run `python -m sortscope benchmark` first") from None
    except pd.errors.EmptyDataError:
        raise ResultsError(f"{csv_path} is empty — run `python -m sortscope benchmark` first") from None
    except (pd.errors.ParserError, UnicodeDecodeError) as e:
        raise ResultsError(f"{csv_path} is not a readable CSV file: {e}") from None
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ResultsError(f"{csv_path} is not a SortScope results file (missing columns: {', '.join(missing)})")

    odd_status = ~df["status"].isin(["ok", "skipped"])
    if odd_status.any():
        lines = [int(i) + 2 for i in df.index[odd_status]]
        warn(f"ignored {len(lines)} row(s) with an unknown status in {csv_path} at line(s) {lines[:10]}"
             f"{' …' if len(lines) > 10 else ''}")
    ok = df[df["status"] == "ok"].copy()
    for col in NUMERIC_COLUMNS:
        ok[col] = pd.to_numeric(ok[col], errors="coerce")
    bad = ok[NUMERIC_COLUMNS].isna().any(axis=1) | ~ok["algorithm"].isin(names()) | ~ok["input_type"].isin(input_kinds())
    if bad.any():
        lines = [int(i) + 2 for i in ok.index[bad]]  # +1 for the header, +1 for 1-based line numbers
        warn(f"skipped {len(lines)} malformed row(s) in {csv_path} at line(s) {lines[:10]}"
             f"{' …' if len(lines) > 10 else ''}")
        ok = ok[~bad]
    if ok.empty:
        raise ResultsError(f"{csv_path} has no usable measured rows (status=ok) — nothing to plot")
    ok["n"] = ok["n"].astype(int)
    ok["ms"] = ok["trial_median_ms"].astype(float)
    return ok, df[df["status"] == "skipped"].copy()


def fit_slope(n: np.ndarray, t: np.ndarray) -> float:
    """Least-squares slope b of log t = b·log n + c (numpy.polyfit, degree 1)."""
    return float(np.polyfit(np.log(n), np.log(t), 1)[0])


def expected_class(algo: str, kind: str) -> str:
    """Growth class we expect for this (algorithm, input) pair — not just the average case."""
    if algo in ("bubble", "insertion") and kind == "sorted":
        return "n"                      # early exit / no shifts: one linear pass
    if algo in QUADRATIC:
        return "n²"
    if algo == "quick_first" and kind in ("sorted", "reverse"):
        return "n²"                     # pivot is always the segment min/max
    return "n log n"


def slopes_table(ok: pd.DataFrame, column: str = "ms") -> pd.DataFrame:
    """Numeric log-log slopes (algorithm × input type) of ``column`` vs n.

    ``column="ms"`` fits runtime; ``column="comparisons"`` fits the deterministic
    comparison counts, which are free of timing noise.
    """
    rows = []
    for algo in names():
        row = {"algorithm": algo}
        for kind in input_kinds():
            sub = ok[(ok.algorithm == algo) & (ok.input_type == kind) & (ok.n >= SLOPE_MIN_N)].sort_values("n")
            y = sub[column].to_numpy(float)
            row[kind] = round(fit_slope(sub.n.to_numpy(float), y), 2) if len(sub) >= 2 and (y > 0).all() else None
        rows.append(row)
    return pd.DataFrame(rows)


def slopes_report_table(slopes: pd.DataFrame) -> pd.DataFrame:
    """Slopes formatted as 'slope (expected class)' for the report."""
    out = slopes.copy()
    for kind in input_kinds():
        out[kind] = [
            "—" if v is None or pd.isna(v) else f"{v:.2f} ({expected_class(a, kind)})"
            for a, v in zip(out.algorithm, out[kind])
        ]
    return out


def doubling_table(ok: pd.DataFrame, kind: str) -> pd.DataFrame:
    """T(2n)/T(n) for every (n, 2n) pair of sizes present in the data, one row per algorithm."""
    sizes = sorted(ok.n.unique())
    pairs = [(n, 2 * n) for n in sizes if 2 * n in sizes]
    rows = []
    for algo in names():
        sub = ok[(ok.algorithm == algo) & (ok.input_type == kind)].set_index("n").ms
        row = {"algorithm": algo}
        for a, b in pairs:
            row[f"{a}→{b}"] = round(sub[b] / sub[a], 2) if a in sub and b in sub else None
        rows.append(row)
    return pd.DataFrame(rows)


def to_markdown(df: pd.DataFrame, title: str, note: str = "") -> str:
    """Render a DataFrame as a Markdown table with a heading and an optional note."""
    cols = list(df.columns)
    lines = [f"### {title}", ""]
    if note:
        lines += [note, ""]
    lines.append("| " + " | ".join(str(c) for c in cols) + " |")
    lines.append("|" + "|".join("---" for _ in cols) + "|")
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            cells.append("—" if v is None or (isinstance(v, float) and math.isnan(v)) else
                         (f"{v:,}" if isinstance(v, (int, np.integer)) else str(v)))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- figures
class FigureWriter:
    """Saves numbered figures with a caption file next to each, and a captions index."""

    def __init__(self, out_dir: Path) -> None:
        self.dir = out_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.number = 0
        self.captions: list[tuple[str, str]] = []

    def save(self, fig, slug: str, caption: str) -> Path:
        """Save the next numbered figure as PNG plus a caption .txt; close the figure."""
        import matplotlib.pyplot as plt

        self.number += 1
        name = f"fig{self.number:02d}_{slug}"
        path = self.dir / f"{name}.png"
        fig.savefig(path, dpi=150, facecolor=SURFACE)
        plt.close(fig)
        text = f"Figure {self.number}: {caption}"
        (self.dir / f"{name}.txt").write_text(text + "\n", encoding="utf-8")
        self.captions.append((f"{name}.png", text))
        return path

    def write_index(self) -> None:
        """Write captions.md listing every figure with its numbered caption."""
        body = ["# Figure captions", ""] + [f"- **{f}** — {c}" for f, c in self.captions]
        (self.dir / "captions.md").write_text("\n".join(body) + "\n", encoding="utf-8")


def _style(ax, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", color=INK, fontsize=11)
    ax.set_xlabel(xlabel, color=INK2)
    ax.set_ylabel(ylabel, color=INK2)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.grid(True, color=GRID, linewidth=0.6, which="major")
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c3c2b7")


def _new_fig(ncols: int = 1, width: float = 6.4, height: float = 4.4):
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, ncols, figsize=(width * ncols, height), squeeze=False)
    fig.patch.set_facecolor(SURFACE)
    return fig, axes[0]


def _series(ax, x, y, algo: str, label: str | None = None, **kw) -> None:
    ax.plot(x, y, color=ALGO_COLOR[algo], marker=MARKERS[algo], markersize=5, linewidth=1.8,
            label=label or get_info(algo).label, **kw)


def _legend(ax, **kw) -> None:
    if not ax.get_legend_handles_labels()[0]:   # panel has no data (e.g. a partial CSV)
        ax.text(0.5, 0.5, "no data in this CSV", transform=ax.transAxes, ha="center", color=MUTED)
        return
    ax.legend(frameon=False, fontsize=8, labelcolor=INK2, **kw)


def fig_runtime_per_kind(ok: pd.DataFrame, fw: FigureWriter) -> None:
    """Figures 1-5: median runtime vs n (linear axes), one figure per input type."""
    for kind in input_kinds():
        fig, (ax,) = _new_fig(width=7.2)
        for algo in names():
            sub = ok[(ok.algorithm == algo) & (ok.input_type == kind)].sort_values("n")
            if len(sub):
                _series(ax, sub.n, sub.ms, algo)
        _style(ax, f"Runtime vs n — {KIND_LABEL[kind]} input", "n (number of elements)", "median runtime (ms)")
        _legend(ax, loc="upper left")
        fig.tight_layout()
        fw.save(fig, f"runtime_{kind}",
                f"Median runtime (ms, {_trials(ok)} trials, NullCounter) vs n on {KIND_LABEL[kind]} input, "
                f"linear axes. Missing points are configurations skipped by the benchmark caps (see CSV).")


def _trials(ok: pd.DataFrame) -> int:
    return int(ok.trials.iloc[0]) if len(ok) else 0


def fig_comparisons_vs_theory(ok: pd.DataFrame, fw: FigureWriter) -> None:
    """Figure 6: measured comparisons vs the theoretical curves (3 panels)."""
    rnd = ok[ok.input_type == "random"]
    fig, axes = _new_fig(3, width=5.0)

    def measured(ax, algo):
        """Plot the measured comparisons of one algorithm as markers; return the n values used."""
        sub = rnd[rnd.algorithm == algo].sort_values("n")
        if len(sub):
            ax.plot(sub.n, sub.comparisons, color=ALGO_COLOR[algo], marker=MARKERS[algo], markersize=6,
                    linestyle="none", label=f"{get_info(algo).label} (measured)")
        return sub.n.to_numpy(float)

    # (a) quadratic sorts
    ax = axes[0]
    ns = np.concatenate([measured(ax, a) for a in QUADRATIC] + [np.array([2.0])])
    grid = np.linspace(max(ns.min(), 2), ns.max(), 200)
    ax.plot(grid, theory_n_choose_2(grid), color=INK2, linestyle="--", linewidth=1.2, label="n(n−1)/2")
    ax.plot(grid, theory_n_choose_2(grid) / 2, color=MUTED, linestyle=":", linewidth=1.2,
            label="n(n−1)/4 (≈ E[inversions])")
    _style(ax, "(a) Quadratic sorts", "n", "key comparisons")
    _legend(ax, loc="upper left")

    # (b) merge
    ax = axes[1]
    ns = measured(ax, "merge")
    if len(ns):
        grid = np.linspace(max(ns.min(), 2), ns.max(), 400)
        ax.plot(grid, theory_merge_worst(grid), color=INK2, linestyle="--", linewidth=1.2,
                label="n⌈lg n⌉ − 2^⌈lg n⌉ + 1 (worst-case bound)")
        ax.plot(grid, theory_n_lg_n(grid), color=MUTED, linestyle=":", linewidth=1.2, label="n lg n")
    _style(ax, "(b) Merge Sort", "n", "key comparisons")
    _legend(ax, loc="upper left")

    # (c) quick random
    ax = axes[2]
    ns = measured(ax, "quick_random")
    if len(ns) and ns.max() >= 2:   # E(n) is only defined (and indexed) from n = 2
        grid = np.linspace(max(ns.min(), 2), ns.max(), 400)
        exact = hoare_random_expected(int(ns.max()))
        gi = np.unique(np.linspace(2, int(ns.max()), 400).astype(int))
        ax.plot(gi, exact[gi], color=INK2, linestyle="--", linewidth=1.2, label="exact E(n) for our Hoare scheme")
        ax.plot(grid, theory_2n_ln_n(grid), color=MUTED, linestyle=":", linewidth=1.2, label="2n ln n")
    _style(ax, "(c) Quick Sort, random pivot", "n", "key comparisons")
    _legend(ax, loc="upper left")
    for a in axes:
        a.ticklabel_format(style="sci", axis="y", scilimits=(0, 0))
    fig.tight_layout()
    fw.save(fig, "comparisons_vs_theory",
            "Measured key comparisons on random input (markers) against theory (lines). "
            "(a) Selection equals n(n−1)/2 exactly; Bubble's points sit under Selection's (on random input the "
            "early exit almost never fires, so it also makes ≈ n(n−1)/2 comparisons); Insertion tracks the "
            "inversion count ≈ n(n−1)/4. (b) Merge stays below its exact worst-case bound and close to n lg n. "
            "(c) Random-pivot Quick: the exact expectation for our partition (m+2 comparisons per partition, "
            "m+1 when the pivot is the minimum) vs the leading term 2n ln n; the gap is the +Θ(n) term. "
            "Random-pivot comparisons are for one seed per n.")


def fig_loglog(ok: pd.DataFrame, slopes: pd.DataFrame, fw: FigureWriter, kind: str = "random") -> None:
    """Figure 7: log-log runtime with fitted slopes in the legend."""
    fig, (ax,) = _new_fig(width=7.2)
    for algo in names():
        sub = ok[(ok.algorithm == algo) & (ok.input_type == kind)].sort_values("n")
        if len(sub) == 0:
            continue
        b = slopes.set_index("algorithm").loc[algo, kind]
        label = f"{get_info(algo).label}  (slope {b:.2f})" if b is not None and not pd.isna(b) else get_info(algo).label
        _series(ax, sub.n, sub.ms, algo, label=label)
    ax.set_xscale("log")
    ax.set_yscale("log")
    _style(ax, f"Runtime vs n, log–log — {KIND_LABEL[kind]} input", "n (log scale)", "median runtime (ms, log scale)")
    ax.grid(True, which="minor", color=GRID, linewidth=0.3)
    _legend(ax, loc="upper left")
    fig.tight_layout()
    fw.save(fig, f"loglog_{kind}",
            f"Log–log runtime on {KIND_LABEL[kind]} input. Slopes are numpy.polyfit fits of log t vs log n over "
            f"n ≥ {SLOPE_MIN_N}: ≈2 indicates Θ(n²), ≈1–1.15 indicates Θ(n log n) over this range.")


def fig_normalized(ok: pd.DataFrame, fw: FigureWriter, kind: str = "random") -> None:
    """Figure 8: t/n² for quadratic sorts and t/(n lg n) for n log n sorts."""
    fig, axes = _new_fig(2, width=5.6)
    sub = ok[ok.input_type == kind]
    ax = axes[0]
    for algo in QUADRATIC:
        s = sub[sub.algorithm == algo].sort_values("n")
        _series(ax, s.n, s.ms * 1e6 / s.n.astype(float) ** 2, algo)
    _style(ax, "(a) t / n² — quadratic sorts", "n (log scale)", "ns per n²")
    ax.set_xscale("log")
    ax.set_ylim(bottom=0)
    _legend(ax)
    ax = axes[1]
    for algo in ("merge", *QUICK_VARIANTS):
        s = sub[sub.algorithm == algo].sort_values("n")
        n = s.n.astype(float)
        _series(ax, s.n, s.ms * 1e6 / (n * np.log2(n)), algo)
    _style(ax, "(b) t / (n lg n) — n log n sorts", "n (log scale)", "ns per n·lg n")
    ax.set_xscale("log")
    ax.set_ylim(bottom=0)
    _legend(ax)
    fig.tight_layout()
    fw.save(fig, f"normalized_{kind}",
            f"Normalized runtime on {KIND_LABEL[kind]} input. A curve that flattens means the growth model is right; "
            f"its height is the hidden constant (ns per basic step). (a) does NOT flatten: cost per comparison grows "
            f"≈1.7× from n=100 to 5000 although the operation counts are exactly quadratic (see slopes of "
            f"comparisons) — a per-operation cost effect of the machine, not extra work. (b) random-pivot Quick "
            f"falls with n because its Θ(n) random-number calls (one per partition) shrink relative to n lg n.")


def quick_pivot_table(ok: pd.DataFrame) -> tuple[pd.DataFrame, int | None]:
    """Counts and time of the 3 pivot rules on 4 inputs at the largest size where all ran."""
    kinds = ["sorted", "reverse", "random", "many_duplicates"]
    q = ok[ok.algorithm.isin(QUICK_VARIANTS) & ok.input_type.isin(kinds)]
    # largest n at which every quick variant was measured on every one of these inputs
    common = [n for n in sorted(q.n.unique()) if len(q[q.n == n]) == len(QUICK_VARIANTS) * len(kinds)]
    if not common:
        return pd.DataFrame(), None
    n = common[-1]
    rows = []
    for algo in QUICK_VARIANTS:
        for kind in kinds:
            r = q[(q.algorithm == algo) & (q.input_type == kind) & (q.n == n)].iloc[0]
            rows.append({"algorithm": algo, "input": kind, "comparisons": int(r.comparisons),
                         "swaps": int(r.swaps), "median_ms": round(float(r.ms), 3), "max_depth": int(r.max_depth)})
    return pd.DataFrame(rows), n


def _short(v: float) -> str:
    """Compact count label: 950, 88k, 12.5M."""
    if v >= 1e6:
        return f"{v / 1e6:.1f}M"
    if v >= 1e3:
        return f"{v / 1e3:.0f}k"
    return f"{v:.0f}"


def fig_quick_pivots(table: pd.DataFrame, n: int | None, fw: FigureWriter) -> None:
    """Figure 9: grouped bars of Quick Sort comparisons per pivot rule (log scale)."""
    if n is None:
        return
    kinds = list(dict.fromkeys(table.input))
    fig, (ax,) = _new_fig(width=7.6)
    width = 0.26
    x = np.arange(len(kinds))
    for i, algo in enumerate(QUICK_VARIANTS):
        vals = [table[(table.algorithm == algo) & (table.input == k)].comparisons.iloc[0] for k in kinds]
        bars = ax.bar(x + (i - 1) * width, vals, width=width * 0.92, color=ALGO_COLOR[algo],
                      label=get_info(algo).label)
        ax.bar_label(bars, labels=[_short(v) for v in vals], fontsize=7, color=INK2, padding=2)
    ax.set_yscale("log")
    ax.set_xticks(x, [KIND_LABEL[k] for k in kinds])
    _style(ax, f"Quick Sort pivot rules — comparisons at n = {n:,}", "input type", "key comparisons (log scale)")
    _legend(ax, loc="upper right")
    fig.tight_layout()
    fw.save(fig, "quick_pivots",
            f"Key comparisons of the three Quick Sort pivot rules at n = {n:,} (largest size where all were run). "
            "First-element pivot is Θ(n²) on sorted and reverse input; random and median-of-three stay near "
            "n log n everywhere. Hoare partitioning keeps all three efficient on many duplicates. Log scale.")


def insertion_inversions(ok: pd.DataFrame) -> pd.DataFrame:
    """Recreate each insertion-sort input from (kind, n, seed) and count its inversions."""
    ins = ok[ok.algorithm == "insertion"]
    rows = []
    for _, r in ins.iterrows():
        n = int(r.n)
        inv = inversion_count(generate(r.input_type, n, int(r.seed)))
        rows.append({"input": r.input_type, "n": n, "inversions": inv,
                     "shifts": int(r.writes) - max(n - 1, 0), "comparisons": int(r.comparisons)})
    return pd.DataFrame(rows)


def fig_insertion_inversions(inv: pd.DataFrame, fw: FigureWriter) -> None:
    """Figure 10: Insertion Sort shifts vs inversions; points should lie on y = x."""
    if inv.empty:
        return
    fig, (ax,) = _new_fig(width=6.4)
    pos = inv[inv.inversions > 0]
    kind_colors = dict(zip(input_kinds(), SERIES))
    for kind in input_kinds():
        s = pos[pos.input == kind]
        if len(s):
            ax.plot(s.inversions, s.shifts, linestyle="none", marker="o", markersize=6,
                    color=kind_colors[kind], label=KIND_LABEL[kind])
    lim = [max(1, pos.inversions.min()) / 1.5, pos.inversions.max() * 1.5]
    ax.plot(lim, lim, color=INK2, linestyle="--", linewidth=1.2, label="y = x")
    ax.set_xscale("log")
    ax.set_yscale("log")
    _style(ax, "Insertion Sort: shifts vs inversions", "inversions in the input (log scale)",
           "element shifts = writes − (n−1) (log scale)")
    _legend(ax, loc="upper left")
    fig.tight_layout()
    fw.save(fig, "insertion_inversions",
            "Insertion Sort element shifts vs the input's inversion count (computed independently with a "
            "Fenwick tree) for every measured configuration. All points lie on y = x: each shift removes exactly "
            "one inversion. Our Insertion Sort shifts rather than swaps, so swaps are 0 and shifts are the "
            "writes minus the n−1 key placements. Sorted inputs (0 inversions, 0 shifts) cannot appear on log axes.")


# --------------------------------------------------------------------------- driver
def analyze(csv_path: Path, out_root: Path) -> dict[str, Path]:
    """Load the CSV, write every figure (+ caption files) and every Markdown table; return output dirs."""
    import matplotlib

    # Figures are written to files, so draw them with the windowless Agg backend, then put the
    # previous backend back. Without that, "Plot results" in the menu would leave Agg selected
    # and a later "Visualize" in the same session could not open its window.
    previous = matplotlib.get_backend()
    matplotlib.use("Agg")
    try:
        return _analyze(csv_path, out_root)
    finally:
        try:
            matplotlib.use(previous)
        except ImportError:  # the previous (window) backend can't be loaded: stay on Agg
            pass


def _analyze(csv_path: Path, out_root: Path) -> dict[str, Path]:
    ok, skipped = load(csv_path)
    fig_dir, tab_dir = out_root / "figures", out_root / "tables"
    tab_dir.mkdir(parents=True, exist_ok=True)
    fw = FigureWriter(fig_dir)

    slopes = slopes_table(ok)
    fig_runtime_per_kind(ok, fw)
    fig_comparisons_vs_theory(ok, fw)
    fig_loglog(ok, slopes, fw, "random")
    fig_normalized(ok, fw, "random")
    qtable, qn = quick_pivot_table(ok)
    fig_quick_pivots(qtable, qn, fw)
    inv = insertion_inversions(ok)
    fig_insertion_inversions(inv, fw)
    fw.write_index()

    tables = {
        "slopes.md": to_markdown(slopes_report_table(slopes), "Log–log slopes of runtime",
                                 f"numpy.polyfit(log n, log t, 1) over measured sizes n ≥ {SLOPE_MIN_N}. "
                                 "In parentheses: the growth class expected for that algorithm on that input "
                                 "(slope ≈ 2 for n², ≈ 1 for n, ≈ 1.0–1.15 for n log n)."),
        "slopes_comparisons.md": to_markdown(
            slopes_report_table(slopes_table(ok, "comparisons")), "Log–log slopes of key comparisons",
            f"Same fit as the runtime slopes, but on the deterministic comparison counts (n ≥ {SLOPE_MIN_N}), "
            "so timing noise cannot affect it. Bubble/Insertion on sorted input make n−1 comparisons → slope 1."),
        "doubling.md": "\n".join(
            to_markdown(doubling_table(ok, k), f"Doubling ratio T(2n)/T(n) — {KIND_LABEL[k]} input",
                        "≈4 → Θ(n²); slightly above 2 → Θ(n log n); ≈2 → Θ(n).")
            for k in input_kinds()),
        "quick_pivots.md": to_markdown(qtable, f"Quick Sort pivot rules at n = {qn:,}") if qn else "",
        "insertion_inversions.md": to_markdown(inv.sort_values(["input", "n"]),
                                               "Insertion Sort shifts vs inversions") if not inv.empty else "",
        "runtime_random.md": to_markdown(
            ok[ok.input_type == "random"].pivot(index="algorithm", columns="n", values="ms")
              .reindex(names()).reset_index().rename_axis(None, axis=1),
            "Median runtime (ms) on random input"),
        "skipped.md": to_markdown(skipped.reindex(columns=["algorithm", "input_type", "n", "reason"]),
                                  "Skipped configurations") if len(skipped) else "No configurations skipped.\n",
    }
    for name, text in tables.items():
        (tab_dir / name).write_text(text, encoding="utf-8")
    return {"figures": fig_dir, "tables": tab_dir}


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Register the `plot` command's flags on ``parser``."""
    parser.add_argument("--csv", type=Path, default=RESULTS_DIR / "results.csv",
                        help="results CSV to read (default results/results.csv)")
    parser.add_argument("--out", type=Path, default=RESULTS_DIR,
                        help="output folder inside results/; figures/ and tables/ are created in it")
    parser.add_argument(ALLOW_OUTSIDE_FLAG, action="store_true", help="allow --out outside results/")


def run(args: argparse.Namespace) -> int:
    """`sortscope plot`: validate paths, build every figure and table, print the slope table."""
    try:
        out = check_output_path(args.out, allow_outside=args.allow_outside_results)
        paths = analyze(args.csv, out)
    except ValueError as e:  # ResultsError is a ValueError too
        raise SystemExit(f"error: {e}") from None
    except OSError as e:  # e.g. read-only output folder
        raise SystemExit(f"error: cannot write figures/tables under {args.out}: {e.strerror or e}") from None
    print(f"figures -> {paths['figures']}\ntables  -> {paths['tables']}")
    print((paths["tables"] / "slopes.md").read_text(encoding="utf-8"))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Standalone entry point: ``python -m sortscope.analysis``."""
    safe_console()
    parser = argparse.ArgumentParser(prog="sortscope.analysis", description="Plot SortScope benchmark results.")
    add_arguments(parser)
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
