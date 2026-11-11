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


def test_cli_prints_warning_to_stderr(tmp_path, good_csv, capsys) -> None:
    def bad_comparisons(line):
        f = line.split(",")
        f[7] = "not-a-number"                         # comparisons
        return ",".join(f)

    p = _corrupt(good_csv, tmp_path, "c2.csv", 3, bad_comparisons)
    assert main(["--csv", str(p), "--out", str(tmp_path / "o"), OUTSIDE]) == 0
    assert "warning: skipped 1 malformed row(s)" in capsys.readouterr().err
