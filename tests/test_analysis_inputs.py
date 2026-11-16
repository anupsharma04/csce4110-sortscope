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
