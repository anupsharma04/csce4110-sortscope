"""Benchmark runner: grid, skip rules, CSV contents and metadata."""

import csv
import json

from sortscope.benchmark import CSV_COLUMNS, build_grid, run_benchmark, skip_reason
from sortscope.counter import OpCounter
from sortscope.inputs import generate, input_kinds
from sortscope.registry import get_sort, names


def test_skip_rules() -> None:
    assert skip_reason("bubble", "random", 5000) is None
    assert "capped" in skip_reason("bubble", "random", 10_000)
    assert skip_reason("merge", "sorted", 100_000) is None
    assert skip_reason("quick_first", "sorted", 5000) is None
    assert "worst case" in skip_reason("quick_first", "reverse", 10_000)
    # nearly sorted is NOT a first-pivot worst case (measured Θ(n log n), large constant)
    assert skip_reason("quick_first", "nearly_sorted", 100_000) is None
    assert skip_reason("quick_first", "random", 100_000) is None
    assert skip_reason("quick_median3", "sorted", 100_000) is None


def test_full_grid_contains_skipped_rows() -> None:
    grid = build_grid(["bubble", "merge"], ["random"], None)
    at_100k = {c.algo: c.skip is None for c in grid if c.n == 100_000}
    assert at_100k == {"bubble": False, "merge": True}      # bubble skipped, merge runs
    assert sum(c.skip is not None for c in grid) == 3        # bubble at 10k, 50k, 100k
    assert len(grid) == 2 * 8


def test_run_writes_csv_and_meta(tmp_path) -> None:
    out = tmp_path / "r.csv"
    grid = build_grid(["insertion", "quick_random"], ["random", "sorted"], [50, 6000])
    run_benchmark(grid, trials=2, seed=7, out=out, verbose=False)

    with out.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0].keys()) == CSV_COLUMNS
    assert len(rows) == len(grid)

    skipped = [r for r in rows if r["status"] == "skipped"]
    assert {(r["algorithm"], r["n"]) for r in skipped} == {("insertion", "6000")}
    assert all(r["reason"] for r in skipped)

    for r in rows:
        if r["status"] != "ok":
            continue
        times = [float(t) for t in r["trial_times_ms"].split(";")]
        assert len(times) == 2 and float(r["trial_median_ms"]) > 0
        # counts in the CSV are exactly the OpCounter counts for that seeded input
        c = OpCounter()
        get_sort(r["algorithm"], seed=7)(generate(r["input_type"], int(r["n"]), 7), c)
        assert (int(r["comparisons"]), int(r["swaps"]), int(r["writes"])) == (c.comparisons, c.swaps, c.writes)
        assert float(r["peak_kb"]) >= 0

    meta = json.loads((tmp_path / "r_meta.json").read_text(encoding="utf-8"))
    assert {"python_version", "processor", "date_utc", "trials", "seed"} <= meta.keys()
    assert meta["seed"] == 7 and meta["trials"] == 2


def test_interleaved_mode_same_counts_and_complete_rows(tmp_path) -> None:
    # Review finding #3: interleaved timing must change only *when* trials run, never what is measured.
    grid = build_grid(["insertion", "merge", "quick_random"], ["random", "sorted"], [60, 120, 6000])
    a = run_benchmark(grid, trials=3, seed=11, out=tmp_path / "a.csv", verbose=False)
    b = run_benchmark(grid, trials=3, seed=11, out=tmp_path / "b.csv", verbose=False, interleave=True)
    assert [r["status"] for r in a] == [r["status"] for r in b]          # same skipped rows
    keys = ("algorithm", "input_type", "n", "comparisons", "swaps", "writes", "max_depth")
    assert [tuple(r.get(k) for k in keys) for r in a] == [tuple(r.get(k) for k in keys) for r in b]
    for r in b:
        if r["status"] == "ok":
            assert len(r["trial_times_ms"].split(";")) == 3 and r["trial_median_ms"] > 0
    meta = json.loads((tmp_path / "b_meta.json").read_text(encoding="utf-8"))
    assert meta["timing_order"].startswith("interleaved")


def test_long_run_prints_estimate_and_warning(tmp_path, capsys, monkeypatch) -> None:
    # Review finding #5: a long benchmark must say so up front.
    import sortscope.benchmark as bm

    monkeypatch.setattr(bm, "LONG_RUN_WARNING_S", 0)          # treat this tiny run as "long"
    run_benchmark(build_grid(["merge"], ["random"], [50]), trials=1, seed=0, out=tmp_path / "r.csv")
    out = capsys.readouterr().out
    assert "estimated time" in out and "warning: this is a long run" in out
    full = bm.estimate_seconds(build_grid(names(), input_kinds(), None), 5)
    assert 6 * 60 < full < 10 * 60                             # calibrated on the real 7m55s full run


def test_unwritable_output_gives_clear_error(tmp_path) -> None:
    # Regression (attack #44/#45): a read-only target used to end in a PermissionError traceback.
    import os
    import stat

    import pytest

    from sortscope.benchmark import main

    ro = tmp_path / "readonly.csv"
    ro.write_text("old\n")
    os.chmod(ro, stat.S_IREAD)
    try:
        with pytest.raises(SystemExit) as e:
            main(["--algorithms", "merge", "--types", "random", "--sizes", "50", "--trials", "1", "--out", str(ro),
                  "--allow-outside-results"])
        assert "cannot write benchmark results" in str(e.value)
    finally:
        os.chmod(ro, stat.S_IWRITE | stat.S_IREAD)
    # a directory where the CSV should be is also an OSError, not a traceback
    folder = tmp_path / "looks_like.csv"
    folder.mkdir()
    with pytest.raises(SystemExit, match="cannot write"):
        main(["--algorithms", "merge", "--types", "random", "--sizes", "50", "--trials", "1", "--out", str(folder),
              "--allow-outside-results"])


def test_output_must_stay_inside_results(tmp_path) -> None:
    # Review finding #1: `--out README.md` used to overwrite the README.
    import pytest

    from sortscope.benchmark import main
    from sortscope.validation import PROJECT_ROOT, RESULTS_DIR

    base = ["--algorithms", "merge", "--types", "random", "--sizes", "50", "--trials", "1"]
    readme = PROJECT_ROOT / "README.md"
    before = readme.read_bytes()
    with pytest.raises(SystemExit, match="must end in .csv"):
        main(base + ["--out", str(readme)])
    with pytest.raises(SystemExit, match="refusing to write outside"):
        main(base + ["--out", str(PROJECT_ROOT / "sneaky.csv")])
    with pytest.raises(SystemExit, match="refusing to write outside"):
        main(base + ["--out", str(RESULTS_DIR / ".." / "escape.csv")])     # .. can't climb out
    with pytest.raises(SystemExit, match="refusing to write outside"):
        main(base + ["--out", str(tmp_path / "r.csv")])                    # needs the explicit flag
    assert readme.read_bytes() == before and not (PROJECT_ROOT / "sneaky.csv").exists()
    # inside results/ is fine, and the flag allows a deliberate outside path
    inside = RESULTS_DIR / "scratch" / "pytest_inside.csv"
    try:
        assert main(base + ["--out", str(inside)]) == 0 and inside.exists()
    finally:
        inside.unlink(missing_ok=True)
        (inside.parent / "pytest_inside_meta.json").unlink(missing_ok=True)
    assert main(base + ["--out", str(tmp_path / "r.csv"), "--allow-outside-results"]) == 0


def test_merge_peak_memory_is_linear_insertion_constant(tmp_path) -> None:
    out = tmp_path / "m.csv"
    run_benchmark(build_grid(["merge", "insertion"], ["random"], [2000, 4000]), 1, 0, out, verbose=False)
    with out.open(newline="", encoding="utf-8") as f:
        peak = {(r["algorithm"], int(r["n"])): float(r["peak_kb"]) for r in csv.DictReader(f)}
    # aux buffer of n pointers ≈ 8n bytes: doubling n roughly doubles the peak
    assert 1.7 < peak[("merge", 4000)] / peak[("merge", 2000)] < 2.3
    assert peak[("insertion", 4000)] < 2.0   # in place: no buffer (only tiny bookkeeping)
