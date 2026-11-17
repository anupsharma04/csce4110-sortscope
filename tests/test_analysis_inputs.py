"""Regression tests for broken results files given to `plot` (attack cases #47-#51)."""

import matplotlib

matplotlib.use("Agg")

import pytest

from sortscope.analysis import ResultsError, analyze, load, main
from sortscope.benchmark import build_grid, run_benchmark

OUTSIDE = "--allow-outside-results"   # these tests write to pytest's tmp folders on purpose


@pytest.fixture(scope="module")
def good_csv(tmp_path_factory):
    path = tmp_path_factory.mktemp("res") / "results.csv"
    grid = build_grid(["insertion", "merge", "quick_first", "quick_random", "quick_median3"],
                      ["random", "sorted", "reverse", "nearly_sorted", "many_duplicates"], [250, 500, 1000])
    run_benchmark(grid, trials=1, seed=1, out=path, verbose=False)
    return path


def write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_missing_file(tmp_path) -> None:
    with pytest.raises(ResultsError, match="not found"):
        load(tmp_path / "nope.csv")
    with pytest.raises(SystemExit, match="not found"):
        main(["--csv", str(tmp_path / "nope.csv"), "--out", str(tmp_path), OUTSIDE])


def test_empty_file(tmp_path) -> None:                        # attack #47
    p = write(tmp_path, "empty.csv", "")
    with pytest.raises(SystemExit, match="is empty"):
        main(["--csv", str(p), "--out", str(tmp_path), OUTSIDE])


def test_header_only(tmp_path, good_csv) -> None:             # attack #48: used to "succeed" with empty tables
    header = good_csv.read_text(encoding="utf-8").splitlines()[0]
    p = write(tmp_path, "header.csv", header + "\n")
    with pytest.raises(SystemExit, match="no usable measured rows"):
        main(["--csv", str(p), "--out", str(tmp_path), OUTSIDE])


def test_not_a_sortscope_csv(tmp_path) -> None:               # attack #51: used to be KeyError: 'status'
    p = write(tmp_path, "garbage.csv", "hello,world\n1,2\n")
    with pytest.raises(SystemExit, match="missing columns: algorithm"):
        main(["--csv", str(p), "--out", str(tmp_path), OUTSIDE])


def _corrupt(good_csv, tmp_path, name, line_no, mutate):
    lines = good_csv.read_text(encoding="utf-8").splitlines()
    lines[line_no - 1] = mutate(lines[line_no - 1])
    return write(tmp_path, name, "\n".join(lines) + "\n")


def test_corrupted_value_is_skipped_with_warning(tmp_path, good_csv) -> None:   # attack #49
    def bad_median(line):
        f = line.split(",")
        f[5] = "abc"                                  # trial_median_ms
        return ",".join(f)

    p = _corrupt(good_csv, tmp_path, "corrupt.csv", 3, bad_median)
    warnings = []
    ok, _ = load(p, warn=warnings.append)
    assert len(warnings) == 1 and "line(s) [3]" in warnings[0]
    total = len(good_csv.read_text(encoding="utf-8").splitlines()) - 1
    assert len(ok) == total - 1                         # only the bad row is gone
    analyze(p, tmp_path / "out")                        # and plotting still works


def test_truncated_row_is_skipped_with_warning(tmp_path, good_csv) -> None:     # attack #50: used to be silent
    p = _corrupt(good_csv, tmp_path, "trunc.csv", 4, lambda line: ",".join(line.split(",")[:4]))
    warnings = []
    load(p, warn=warnings.append)
    assert len(warnings) == 1 and "line(s) [4]" in warnings[0]


def test_unknown_algorithm_name_is_skipped(tmp_path, good_csv) -> None:
    p = _corrupt(good_csv, tmp_path, "unknown.csv", 2, lambda line: "bogosort" + line[line.index(","):])
    warnings = []
    load(p, warn=warnings.append)
    assert warnings and "line(s) [2]" in warnings[0]


def test_unknown_status_is_reported(tmp_path, good_csv) -> None:
    # Found while writing these tests: a row whose status is neither ok nor skipped
    # (e.g. corrupted "ok" -> "xok") used to be ignored silently.
    p = _corrupt(good_csv, tmp_path, "status.csv", 5, lambda line: line.replace(",ok,", ",xok,", 1))
    warnings = []
    load(p, warn=warnings.append)
    assert len(warnings) == 1 and "unknown status" in warnings[0] and "line(s) [5]" in warnings[0]


def test_repeated_configurations_keep_the_last_row(tmp_path, good_csv) -> None:
    # Edge run 2026-11-16: a CSV holding a configuration twice (two result files joined, or a
    # benchmark started with a repeated name) crashed `plot` with a TypeError in summary_table.
    lines = good_csv.read_text(encoding="utf-8").splitlines()
    total = len(lines) - 1
    newer = lines[1].split(",")
    newer[5] = "123.4567"                               # trial_median_ms of the repeated first row
    p = write(tmp_path, "twice.csv", "\n".join(lines + lines[1:4] + [",".join(newer)]) + "\n")
    warnings = []
    ok, _ = load(p, warn=warnings.append)
    assert len(ok) == total                             # one row per configuration again
    assert len(warnings) == 1 and "more than once" in warnings[0] and "[2, 3, 4, 77]" in warnings[0]
    first = ok[(ok.algorithm == newer[0]) & (ok.input_type == newer[1]) & (ok.n == int(newer[2]))]
    assert first.ms.tolist() == [123.4567]              # the row furthest down the file won
    analyze(p, tmp_path / "out")                        # and every figure and table is still made
    assert "123.4567" in (tmp_path / "out" / "tables" / "runtime_random.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("column, value", [
    ("n", "100000000000"),          # used to end in MemoryError: the analysis rebuilds an input of size n
    ("n", "inf"), ("n", "1e400"),   # used to stop the whole plot with a pandas "non-finite values" error
    ("n", "0"), ("n", "-5"), ("n", "1.5"),                  # used to be plotted as if they were real sizes
    ("trial_median_ms", "inf"), ("trial_median_ms", "-1"),
    ("comparisons", "-7"), ("comparisons", "1.5"), ("writes", "inf"), ("peak_kb", "-1"),
    ("seed", "-1"), ("seed", "1e30"), ("trials", "2.5"),
])
def test_impossible_number_drops_only_that_row(tmp_path, good_csv, column, value) -> None:
    # Edge run 2026-11-16: a value the benchmark could never have written (hand-edited or damaged file).
    col = good_csv.read_text(encoding="utf-8").splitlines()[0].split(",").index(column)

    def damage(line):
        f = line.split(",")
        f[col] = value
        return ",".join(f)

    p = _corrupt(good_csv, tmp_path, "impossible.csv", 2, damage)   # line 2: insertion / random / n=250
    warnings = []
    ok, _ = load(p, warn=warnings.append)
    assert len(warnings) == 1 and "malformed" in warnings[0] and "line(s) [2]" in warnings[0]
    assert len(ok) == len(good_csv.read_text(encoding="utf-8").splitlines()) - 2
    assert ok.n.between(1, 100_000).all()


def test_zero_runtime_is_a_legal_measurement(tmp_path, good_csv) -> None:
    # 0.0000 ms is what a sort faster than the 4-decimal rounding is recorded as: keep the row.
    p = _corrupt(good_csv, tmp_path, "zero.csv", 2, lambda line: ",".join(
        "0.0000" if i == 5 else f for i, f in enumerate(line.split(","))))
    warnings = []
    ok, _ = load(p, warn=warnings.append)
    assert not warnings and (ok.ms == 0).sum() == 1
    import warnings as python_warnings

    with python_warnings.catch_warnings():
        python_warnings.simplefilter("error", RuntimeWarning)     # T(500)/T(250) must not divide by zero
        paths = analyze(p, tmp_path / "out")
    doubling = (paths["tables"] / "doubling.md").read_text(encoding="utf-8")
    assert "inf" not in doubling and "| insertion | — |" in doubling


def test_csv_path_that_is_a_folder(tmp_path) -> None:
    # Edge run 2026-11-16: used to say "cannot write figures/tables under ..." (wrong side of the problem).
    with pytest.raises(SystemExit, match="cannot read"):
        main(["--csv", str(tmp_path), "--out", str(tmp_path / "out"), OUTSIDE])


def test_single_item_inputs_plot_without_warnings(tmp_path, recwarn) -> None:
    # n = 1 means 0 comparisons everywhere; the pivot chart (log axis) is skipped instead of
    # letting matplotlib print "Data has no positive values" warnings.
    p = tmp_path / "one.csv"
    run_benchmark(build_grid(["quick_first", "quick_random", "quick_median3"], ["random", "sorted", "reverse",
                                                                              "many_duplicates"], [1]),
                  trials=1, seed=1, out=p, verbose=False)
    paths = analyze(p, tmp_path / "out")
    assert not [w for w in recwarn if "log-scaled" in str(w.message)]
    assert not list(paths["figures"].glob("*quick_pivots*"))


@pytest.mark.parametrize("kinds", [["random"], ["sorted"]])
def test_csv_with_one_input_type_still_plots(tmp_path, kinds) -> None:
    # README "Custom benchmark" then "Plot a scratch run": the log-log figures (random and sorted)
    # used to crash with AttributeError when the CSV had no rows of their input type.
    csv = tmp_path / "partial.csv"
    run_benchmark(build_grid(["merge", "heap"], kinds, [250, 500, 1000]), trials=1, seed=1, out=csv, verbose=False)
    paths = analyze(csv, tmp_path / "out")
    captions = (paths["figures"] / "captions.md").read_text(encoding="utf-8")
    assert "loglog_random" in captions and "loglog_sorted" in captions
    assert captions.count("Gray lines show the expected growth") == 1   # only the figure that has data


def test_csv_with_only_large_sizes_gets_one_runtime_panel(tmp_path) -> None:
    # Every size is above LINEAR_ZOOM_N: there is no "n ≤ 5,000" panel to draw, so no (a)/(b) split.
    csv = tmp_path / "large.csv"
    run_benchmark(build_grid(["merge", "heap"], ["random"], [6000, 12000]), trials=1, seed=1, out=csv, verbose=False)
    paths = analyze(csv, tmp_path / "out")
    caption = (paths["figures"] / "fig01_runtime_random.txt").read_text(encoding="utf-8")
    assert "(a)" not in caption and "(b)" not in caption


def test_csv_text_cannot_break_a_markdown_table(tmp_path, good_csv) -> None:
    # Security review: the `reason` text of a skipped row is copied from the CSV into
    # tables/skipped.md. A "|" used to add a column and a line break used to end the table.
    import csv

    with good_csv.open(newline="", encoding="utf-8") as f:
        columns = next(csv.reader(f))
    p = tmp_path / "hostile.csv"
    p.write_text(good_csv.read_text(encoding="utf-8"), encoding="utf-8")
    with p.open("a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=columns).writerow(
            {"algorithm": "bubble", "input_type": "random", "n": 9000, "status": "skipped",
             "reason": "a | b\n| injected | row |\r\nback\\|slash"})
    paths = analyze(p, tmp_path / "out")
    lines = (paths["tables"] / "skipped.md").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 5                               # heading, blank, header, separator, ONE data row
    assert lines[4] == r"| bubble | random | 9,000 | a \| b \| injected \| row \| back\\\|slash |"
    # every "|" that is not escaped is a real column border: 4 columns -> 5 borders
    assert lines[4].replace("\\\\", "").replace("\\|", "").count("|") == 5


def test_cli_prints_warning_to_stderr(tmp_path, good_csv, capsys) -> None:
    def bad_comparisons(line):
        f = line.split(",")
        f[7] = "not-a-number"                         # comparisons
        return ",".join(f)

    p = _corrupt(good_csv, tmp_path, "c2.csv", 3, bad_comparisons)
    assert main(["--csv", str(p), "--out", str(tmp_path / "o"), OUTSIDE]) == 0
    assert "warning: skipped 1 malformed row(s)" in capsys.readouterr().err
