"""Results analysis: figures, fitted slopes, doubling ratios, Markdown tables (M5, owner: Gaurav).

Reads ``results/results.csv`` (written by ``benchmark.py``) and writes
* ``results/figures/figNN_*.png`` + ``figNN_*.txt`` (numbered caption) and ``captions.md``
* ``results/tables/*.md`` (drop straight into the report; ``summary.md`` is the one-page summary table)

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
* Expected-growth lines on the log-log figures: pure c·n², c·n lg n and c·n curves,
  placed a constant factor above/below the measured curves of that class so they can
  be compared by eye (parallel = same growth rate).
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import pandas as pd

from sortscope.inputs import generate, input_kinds, inversion_count
from sortscope.registry import QUADRATIC, QUICK_VARIANTS, get_info, names
from sortscope.validation import ALLOW_OUTSIDE_FLAG, BENCH_N, RESULTS_DIR, SEED, check_output_path, safe_console

SLOPE_MIN_N = 500
# The runtime-vs-n figures get a second panel when sizes go beyond this, because the Θ(n²)
# sorts stop here (the proposal's size cap): on one linear axis up to 100,000 every
# small-n point would sit in the bottom-left corner.
LINEAR_ZOOM_N = 5000

# Categorical palette (dataviz reference, light mode), assigned to algorithms in a
# fixed order so an algorithm has the same color in every figure.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
ALGO_COLOR = {name: SERIES[i] for i, name in enumerate(names())}
MARKERS = {"bubble": "o", "selection": "s", "insertion": "^", "merge": "D",
           "quick_first": "v", "quick_random": "P", "quick_median3": "X", "heap": "*"}
# Input types get their own marker shapes too (Figure 10), so they never rely on color alone.
KIND_MARKERS = {"random": "o", "sorted": "s", "reverse": "^", "nearly_sorted": "D", "many_duplicates": "v"}
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


# Each expected growth class: its shape g(n), legend text and line style on the log-log figures
# (the constant in front of g(n) is set from the data, see fig_loglog).
GROWTH = {
    "n²": (lambda n: n**2, "∝ n²", "--"),
    "n log n": (theory_n_lg_n, "∝ n lg n", ":"),
    "n": (lambda n: n, "∝ n", "-."),
}


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
WHOLE_COLUMNS = ["n", "comparisons", "swaps", "writes", "max_depth", "trials", "seed"]   # the rest are measurements


def load(csv_path: Path, warn=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (measured rows, skipped rows), validating the file first.

    * empty file / wrong columns / no measured rows -> ResultsError with a readable message
    * individual malformed rows (non-numeric, missing, negative, infinite or out-of-range values
      in a measured row, unknown algorithm or input name) are dropped, and ``warn`` is called
      with their CSV line numbers, so one bad line doesn't throw away a 10-minute benchmark.
    * a configuration measured more than once keeps its last row (also reported through ``warn``).
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
    except OSError as e:  # --csv names a folder, or a file we are not allowed to open
        raise ResultsError(f"cannot read {csv_path}: {e.strerror or e}") from None
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
    # A measured row is usable only if every number in it is one the benchmark could have written:
    # finite and not negative; the counts whole; n within the benchmark's size range (the analysis
    # rebuilds inputs of size n, so n = 100000000000 would exhaust memory); seed within its range.
    numbers = ok[NUMERIC_COLUMNS]
    sane = np.isfinite(numbers).all(axis=1) & (numbers >= 0).all(axis=1) & (numbers[WHOLE_COLUMNS] % 1 == 0).all(axis=1)
    sane &= ok["n"].between(*BENCH_N) & (ok["seed"] <= SEED[1])
    bad = ~sane | ~ok["algorithm"].isin(names()) | ~ok["input_type"].isin(input_kinds())
    if bad.any():
        lines = [int(i) + 2 for i in ok.index[bad]]  # +1 for the header, +1 for 1-based line numbers
        warn(f"skipped {len(lines)} malformed row(s) in {csv_path} at line(s) {lines[:10]}"
             f"{' …' if len(lines) > 10 else ''}")
        ok = ok[~bad]
    if ok.empty:
        raise ResultsError(f"{csv_path} has no usable measured rows (status=ok) — nothing to plot")
    ok["n"] = ok["n"].astype(int)
    # Every table and figure assumes one measurement per (algorithm, input, n). A CSV can hold
    # the same configuration twice (two result files joined together, or a run started with a
    # repeated name); the row furthest down the file is the newer one, so that one is kept.
    repeated = ok.duplicated(["algorithm", "input_type", "n"], keep="last")
    if repeated.any():
        lines = [int(i) + 2 for i in ok.index[repeated]]
        warn(f"{csv_path} measures {len(lines)} configuration(s) more than once; using the last row of each "
             f"and ignoring line(s) {lines[:10]}{' …' if len(lines) > 10 else ''}")
        ok = ok[~repeated]
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
            # sub[a] > 0: a run faster than the CSV's 4 decimals is recorded as 0.0 ms -> no ratio
            row[f"{a}→{b}"] = round(sub[b] / sub[a], 2) if a in sub and b in sub and sub[a] > 0 else None
        rows.append(row)
    return pd.DataFrame(rows)


def summary_table(ok: pd.DataFrame, slopes: pd.DataFrame, kind: str = "random") -> tuple[pd.DataFrame, int | None]:
    """One row per algorithm on ``kind`` input: expected class, fitted slope, doubling ratio and the
    measurements at the largest n where every algorithm in the CSV ran. Returns (table, that n)."""
    data = ok[ok.input_type == kind]
    algos = [a for a in names() if (data.algorithm == a).any()]
    common = [int(n) for n in sorted(data.n.unique())
              if all(((data.algorithm == a) & (data.n == n)).any() for a in algos)]
    if not common:
        return pd.DataFrame(), None
    n = common[-1]
    # Largest doubling step (m -> 2m) that every algorithm has, so the ratios are comparable.
    pair = next(((m, 2 * m) for m in reversed(common) if 2 * m in common), None)
    slope = slopes.set_index("algorithm")[kind]
    rows = []
    for algo in algos:
        info, sub = get_info(algo), data[data.algorithm == algo].set_index("n")
        r = sub.loc[n]
        row = {"algorithm": info.label, "expected": expected_class(algo, kind),
               "slope": "—" if slope[algo] is None or pd.isna(slope[algo]) else f"{slope[algo]:.2f}"}
        if pair:
            small, big = sub.ms[pair[0]], sub.ms[pair[1]]
            row[f"T({pair[1]})/T({pair[0]})"] = f"{big / small:.2f}" if small > 0 else "—"   # 0.0 ms: no ratio
        row.update({"median ms": round(float(r.ms), 3), "comparisons": int(r.comparisons), "swaps": int(r.swaps),
                    "writes": int(r.writes), "peak KB": round(float(r.peak_kb), 3), "max depth": int(r.max_depth),
                    "stable": "yes" if info.stable else "no"})
        rows.append(row)
    return pd.DataFrame(rows), n


def _md_cell(text: str) -> str:
    """Make ``text`` safe to put in one Markdown table cell.

    Cell text can come straight from the results CSV (e.g. the ``reason`` column), so it is
    not trusted: a "|" would start a new column and a line break would end the table row.
    Backslashes are doubled first so an existing "\\|" can't cancel the escape added here.
    """
    text = text.replace("\\", "\\\\").replace("|", "\\|")
    return " ".join(text.splitlines())  # line breaks -> spaces; text without any is unchanged


def _is_number(text: str) -> bool:
    """True for cells like "1,234", "0.23", "-5" (used to right-align numeric columns)."""
    try:
        float(text.replace(",", ""))
        return True
    except ValueError:
        return False


def to_markdown(df: pd.DataFrame, title: str, note: str = "") -> str:
    """Render a DataFrame as a Markdown table with a heading and an optional note.

    Columns are padded to a common width so the raw .md file lines up like the rendered table;
    numeric columns are right-aligned (both in the raw text and via ``---:`` when rendered).
    """
    cols = list(df.columns)
    lines = [f"### {title}", ""]
    if note:
        lines += [note, ""]
    header = [_md_cell(str(c)) for c in cols]
    rows = []
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            cells.append("—" if v is None or (isinstance(v, float) and math.isnan(v)) else
                         (f"{v:,}" if isinstance(v, (int, np.integer)) else _md_cell(str(v))))
        rows.append(cells)
    numeric = [bool(rows) and all(row[i] == "—" or _is_number(row[i]) for row in rows)
               and any(row[i] != "—" for row in rows) for i in range(len(cols))]
    widths = [max([len(header[i]), 3] + [len(row[i]) for row in rows]) for i in range(len(cols))]

    def line(cells: list[str]) -> str:
        return "| " + " | ".join(cell.rjust(w) if num else cell.ljust(w)
                                 for cell, w, num in zip(cells, widths, numeric)) + " |"

    lines.append(line(header))
    lines.append("|" + "|".join("-" * (w + 1) + ":" if num else "-" * (w + 2)
                                for w, num in zip(widths, numeric)) + "|")
    lines += [line(row) for row in rows]
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
        data = ok[ok.input_type == kind]
        # Two panels when the data goes past LINEAR_ZOOM_N: (a) every algorithm up to that size,
        # (b) the full range for the algorithms that were measured beyond it. Both linear.
        # A CSV whose sizes are all above LINEAR_ZOOM_N has nothing to zoom in on: one panel.
        small = data[data.n <= LINEAR_ZOOM_N]
        large = [a for a in names() if (data[data.algorithm == a].n > LINEAR_ZOOM_N).any()] if len(small) else []
        fig, axes = _new_fig(2 if large else 1, width=5.8 if large else 7.2)
        ax = axes[0]
        shown = small if large else data
        for algo in names():
            sub = shown[shown.algorithm == algo].sort_values("n")
            if len(sub):
                _series(ax, sub.n, sub.ms, algo)
        title = f"Runtime vs n — {KIND_LABEL[kind]} input"
        _style(ax, f"(a) {title}, n ≤ {LINEAR_ZOOM_N:,}" if large else title,
               "n (number of elements)", "median runtime (ms)")
        _legend(ax, loc="upper left")
        if large:
            ax = axes[1]
            for algo in large:
                sub = data[data.algorithm == algo].sort_values("n")
                _series(ax, sub.n, sub.ms, algo)
            _style(ax, "(b) all sizes — sorts measured beyond that", "n (number of elements)", "median runtime (ms)")
            _legend(ax, loc="upper left")
        fig.tight_layout()
        fw.save(fig, f"runtime_{kind}",
                f"Median runtime (ms, {_trials(ok)} trials, NullCounter) vs n on {KIND_LABEL[kind]} input, "
                f"linear axes." + (f" (a) every algorithm up to n = {LINEAR_ZOOM_N:,}; (b) the full size range for "
                                   f"the sorts measured beyond it. Configurations above the benchmark caps were "
                                   f"skipped (see the CSV and skipped.md)." if large else ""))


def _trials(ok: pd.DataFrame) -> int:
    return int(ok.trials.iloc[0]) if len(ok) else 0


def fig_comparisons_vs_theory(ok: pd.DataFrame, fw: FigureWriter) -> None:
    """Figure 6: measured comparisons vs the theoretical curves (3 panels)."""
    rnd = ok[ok.input_type == "random"]
    fig, axes = _new_fig(3, width=5.0)

    def measured(ax, algo, ring: bool = False):
        """Plot the measured comparisons of one algorithm as markers; return the n values used.

        ``ring=True`` draws a larger hollow marker, for a series whose points coincide with
        another's (Bubble and Selection on random input), so both stay visible.
        """
        sub = rnd[rnd.algorithm == algo].sort_values("n")
        if len(sub):
            shape = dict(markersize=12, markerfacecolor="none", markeredgewidth=1.8) if ring else dict(markersize=6)
            ax.plot(sub.n, sub.comparisons, color=ALGO_COLOR[algo], marker=MARKERS[algo],
                    linestyle="none", label=f"{get_info(algo).label} (measured)", **shape)
        return sub.n.to_numpy(float)

    # (a) quadratic sorts
    ax = axes[0]
    ns = np.concatenate([measured(ax, a, ring=(a == "bubble")) for a in QUADRATIC] + [np.array([2.0])])
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
            "(a) Selection equals n(n−1)/2 exactly; Bubble's points (rings) coincide with Selection's (on random "
            "input the early exit almost never fires, so it also makes ≈ n(n−1)/2 comparisons); Insertion tracks the "
            "inversion count ≈ n(n−1)/4. (b) Merge stays below its exact worst-case bound and close to n lg n. "
            "(c) Random-pivot Quick: the exact expectation for our partition (m+2 comparisons per partition, "
            "m+1 when the pivot is the minimum) vs the leading term 2n ln n; the gap is the +Θ(n) term. "
            "Random-pivot comparisons are for one seed per n.")


def fig_loglog(ok: pd.DataFrame, slopes: pd.DataFrame, fw: FigureWriter, kind: str = "random") -> None:
    """Log-log runtime with fitted slopes in the legend and expected-growth lines (Figures 7 and 11)."""
    fig, (ax,) = _new_fig(width=8.6, height=5.0)
    data = ok[ok.input_type == kind]
    for algo in names():
        sub = data[data.algorithm == algo].sort_values("n")
        if len(sub) == 0:
            continue
        b = slopes.set_index("algorithm").loc[algo, kind]
        label = f"{get_info(algo).label}  (slope {b:.2f})" if b is not None and not pd.isna(b) else get_info(algo).label
        _series(ax, sub.n, sub.ms, algo, label=label)
    # Expected-growth lines: one pure c·g(n) curve per growth class present. The constant c puts
    # the n² line a fixed factor above the slowest curve of its class (and the other lines the same
    # factor below the fastest curve of theirs) at the largest measured n, so a line never hides
    # data and "measured curve parallel to the line" can be judged by eye.
    gap = 2.2
    lines_drawn = False
    for cls, (shape, text, style) in GROWTH.items():
        # isin (a boolean Series), not a plain list of booleans: for a CSV with no rows of this
        # input type the list would be [], and data[[]] selects zero *columns* instead of zero rows.
        members = data[data.algorithm.isin([a for a in names() if expected_class(a, kind) == cls])]
        if members.n.nunique() < 2:
            continue
        n_hi = members.n.max()
        at_hi = members[members.n == n_hi].ms
        anchor = at_hi.max() * gap if cls == "n²" else at_hi.min() / gap
        grid = np.geomspace(max(members.n.min(), 2), n_hi, 50)
        ax.plot(grid, anchor * shape(grid) / shape(float(n_hi)), color=INK2, linestyle=style,
                linewidth=1.2, label=f"{text}  (expected growth)")
        lines_drawn = True
    ax.set_xscale("log")
    ax.set_yscale("log")
    _style(ax, f"Runtime vs n, log–log — {KIND_LABEL[kind]} input", "n (log scale)", "median runtime (ms, log scale)")
    ax.grid(True, which="minor", color=GRID, linewidth=0.3)
    _legend(ax, loc="center left", bbox_to_anchor=(1.01, 0.5))   # outside the plot: never covers a curve
    fig.tight_layout()
    fw.save(fig, f"loglog_{kind}",
            f"Log–log runtime on {KIND_LABEL[kind]} input. Slopes are numpy.polyfit fits of log t vs log n over "
            f"n ≥ {SLOPE_MIN_N}: ≈2 indicates Θ(n²), ≈1–1.15 indicates Θ(n log n) over this range, ≈1 indicates "
            f"Θ(n)." + (" Gray lines show the expected growth of each class present (c·n², c·n lg n, c·n), offset "
                        "from the data by a constant factor; a measured curve of that class should run parallel "
                        "to its line." if lines_drawn else ""))


def fig_normalized(ok: pd.DataFrame, fw: FigureWriter, kind: str = "random") -> None:
    """Figure 8: t/n² for quadratic sorts and t/(n lg n) for n log n sorts."""
    fig, axes = _new_fig(2, width=5.6)
    sub = ok[ok.input_type == kind]
    ax = axes[0]
    # How far each quadratic curve is from flat: (t/n² at the largest n) / (t/n² at the smallest n).
    drift = []
    for algo in QUADRATIC:
        s = sub[sub.algorithm == algo].sort_values("n")
        _series(ax, s.n, s.ms * 1e6 / s.n.astype(float) ** 2, algo)
        c = (s.ms / s.n.astype(float) ** 2).to_numpy()
        if len(c) >= 2 and c[0] > 0:
            drift.append(c[-1] / c[0])
    _style(ax, "(a) t / n² — quadratic sorts", "n (log scale)", "ns per n²")
    ax.set_xscale("log")
    ax.set_ylim(bottom=0)
    _legend(ax)
    ax = axes[1]
    for algo in [a for a in names() if a not in QUADRATIC]:
        s = sub[sub.algorithm == algo].sort_values("n")
        n = s.n.astype(float)
        _series(ax, s.n, s.ms * 1e6 / (n * np.log2(n)), algo)
    _style(ax, "(b) t / (n lg n) — n log n sorts", "n (log scale)", "ns per n·lg n")
    ax.set_xscale("log")
    ax.set_ylim(bottom=0)
    _legend(ax)
    fig.tight_layout()
    if not drift:
        part_a = ""
    elif max(drift) <= 1.25 and min(drift) >= 0.8:
        # Only the two ends of each curve are compared, so the caption claims no more than that.
        part_a = " (a) flattens: the cost per n² at the largest n is within 25% of its value at the smallest n."
    else:
        part_a = (f" (a) is not perfectly flat: the cost per n² changes by {min(drift):.2f}×–{max(drift):.2f}× from "
                  f"the smallest to the largest n although the comparison counts are exactly quadratic (see the "
                  f"slopes of comparisons) — a change in cost per operation on this machine, not extra work.")
    fw.save(fig, f"normalized_{kind}",
            f"Normalized runtime on {KIND_LABEL[kind]} input. A curve that flattens means the growth model is right; "
            f"its height is the hidden constant (ns per basic step).{part_a} (b) A curve that falls at small n is "
            f"fixed per-call overhead shrinking relative to n lg n (for random-pivot Quick: one random-number call "
            f"per partition, Θ(n) in total).")


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
    """Figure 9: Quick Sort comparisons per pivot rule and input type (dots on a log scale).

    Dots, not bars: a log axis has no zero, so the length of a bar on it would mean nothing.
    """
    if n is None or (table.comparisons <= 0).any():   # 0 comparisons (n = 1) has no place on a log axis
        return
    kinds = list(dict.fromkeys(table.input))
    fig, (ax,) = _new_fig(width=7.6)
    step = 0.24
    x = np.arange(len(kinds))
    for i, algo in enumerate(QUICK_VARIANTS):
        vals = [table[(table.algorithm == algo) & (table.input == k)].comparisons.iloc[0] for k in kinds]
        xs = x + (i - 1) * step
        ax.plot(xs, vals, linestyle="none", marker=MARKERS[algo], markersize=9, color=ALGO_COLOR[algo],
                label=get_info(algo).label)
        for xi, v in zip(xs, vals):
            ax.annotate(_short(v), (xi, v), textcoords="offset points", xytext=(0, 8), ha="center",
                        fontsize=7.5, color=INK2)
    ax.set_yscale("log")
    ax.set_xticks(x, [KIND_LABEL[k] for k in kinds])
    ax.set_xlim(-0.6, len(kinds) - 0.4)
    ax.set_ylim(table.comparisons.min() / 2, table.comparisons.max() * 3)   # room for the labels on top
    _style(ax, f"Quick Sort pivot rules — comparisons at n = {n:,}", "input type", "key comparisons (log scale)")
    ax.grid(False, axis="x")                         # categories need no vertical grid lines
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
            # Hollow markers with a different shape per input type: points that land on the
            # same spot (random and many-duplicates inputs of equal n) stay visible, and the
            # input type is readable without relying on color.
            ax.plot(s.inversions, s.shifts, linestyle="none", marker=KIND_MARKERS[kind], markersize=9,
                    markerfacecolor="none", markeredgewidth=1.8, color=kind_colors[kind], label=KIND_LABEL[kind])
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
            "Fenwick tree) for every measured configuration (marker shape = input type). All points lie on y = x: "
            "each shift removes exactly "
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
    # Sorted input shows three growth classes at once: Θ(n) (Bubble, Insertion), Θ(n log n), Θ(n²).
    fig_loglog(ok, slopes, fw, "sorted")
    fw.write_index()
    summary, sn = summary_table(ok, slopes)

    tables = {
        "summary.md": to_markdown(
            summary, f"Summary — random input, measurements at n = {sn:,}",
            f"One row per algorithm. n = {sn:,} is the largest size every algorithm ran.\n\n"
            f"- **expected**: growth class on random input\n"
            f"- **slope**: log–log fit of runtime over n ≥ {SLOPE_MIN_N} (≈2 for n², ≈1.0–1.15 for n log n)\n"
            f"- **T(2m)/T(m)**: doubling ratio (≈4 for n², slightly above 2 for n log n)\n"
            f"- **median ms**: median runtime at n = {sn:,}\n"
            f"- **comparisons / swaps / writes**: exact operation counts at n = {sn:,}\n"
            f"- **peak KB / max depth**: tracemalloc peak memory and recursion depth at n = {sn:,}") if sn else "",
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
    """`sortscope plot`: validate paths, build every figure and table, print the summary and slope tables."""
    try:
        out = check_output_path(args.out, allow_outside=args.allow_outside_results)
        paths = analyze(args.csv, out)
    except ValueError as e:  # ResultsError is a ValueError too
        raise SystemExit(f"error: {e}") from None
    except OSError as e:  # e.g. read-only output folder
        raise SystemExit(f"error: cannot write figures/tables under {args.out}: {e.strerror or e}") from None
    print(f"figures -> {paths['figures']}\ntables  -> {paths['tables']}")
    for name in ("summary.md", "slopes.md"):
        print((paths["tables"] / name).read_text(encoding="utf-8"))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Standalone entry point: ``python -m sortscope.analysis``."""
    safe_console()
    parser = argparse.ArgumentParser(prog="sortscope.analysis", description="Plot SortScope benchmark results.")
    add_arguments(parser)
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
