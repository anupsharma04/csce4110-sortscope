"""CLI wiring and the analysis pipeline on a tiny benchmark."""

import matplotlib
import pytest

matplotlib.use("Agg")

from sortscope.__main__ import build_parser, main, sort_list
from sortscope.analysis import analyze, fit_slope
from sortscope.benchmark import build_grid, run_benchmark


def test_sort_list_reports_every_algorithm(capsys) -> None:
    assert main(["sort", "5, 3, -2, 8"]) == 0
    out = capsys.readouterr().out
    assert "sorted: [-2, 3, 5, 8]" in out
    for label in ("Bubble", "Selection", "Insertion", "Merge", "Quick (first pivot)"):
        assert label in out
    # Selection always makes n(n-1)/2 = 6 comparisons
    assert any(line.startswith("Selection") and line.split()[1] == "6" for line in sort_list([5, 3, -2, 8], ["selection"]).splitlines())


def test_sort_list_reports_runtime_for_every_run() -> None:
    # Proposal objective 2: comparisons, swaps/writes AND runtime for every run.
    lines = sort_list([5, 3, -2, 8], ["insertion", "merge"]).splitlines()
    header = next(line for line in lines if line.startswith("algorithm"))
    assert header.split() == ["algorithm", "comparisons", "swaps", "writes", "time", "ms", "stable"]
    for label in ("Insertion", "Merge"):
        row = next(line for line in lines if line.startswith(label))
        assert float(row.split()[-2]) >= 0.0          # the time column, just before "stable"
    assert "median of 5 runs" in lines[-1]
    # long lists get one timing trial so Θ(n²) sorts aren't repeated
    assert "one run" in sort_list(list(range(2001, 0, -1)), ["merge"]).splitlines()[-1]


def test_menu_demo_all_and_speed_controls(monkeypatch) -> None:
    # Proposal demo part 2 (all algorithms, 40-item random list) and M3 "speed and size controls"
    # must be reachable from the menu, not only from the CLI.
    seen = []
    monkeypatch.setattr("sortscope.visualizer.run", lambda args: seen.append(args) or 0)
    answers = iter(["2", "1", "merge", "reverse", "25", "120", "3", "0"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    assert main(["menu"]) == 0
    assert seen[0].demo == "all" and seen[0].n == 40
    assert (seen[1].algo, seen[1].input, seen[1].n) == (["merge"], ["reverse"], 25)
    assert (seen[1].interval, seen[1].steps_per_frame) == (120, 3)


def test_menu_sort_my_list_then_quit(monkeypatch, capsys) -> None:
    answers = iter(["5", "5, -3, 1", "n", "0"])   # sort my list, don't animate, quit
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    assert main(["menu"]) == 0
    out = capsys.readouterr().out
    assert "sorted: [-3, 1, 5]" in out and "Quick (median-of-3)" in out


def test_menu_recovers_from_bad_input_and_eof(monkeypatch, capsys) -> None:
    answers = iter(["42", "5", "1, x"])            # invalid choice, then a bad list, then EOF
    def fake_input(prompt=""):
        try:
            return next(answers)
        except StopIteration:
            raise EOFError
    monkeypatch.setattr("builtins.input", fake_input)
    assert main(["menu"]) == 0
    out = capsys.readouterr().out
    assert "choose one of" in out and "not an integer" in out


def test_sort_reads_long_list_from_file_and_stdin(tmp_path, monkeypatch, capsys) -> None:
    # Regression (attack #38): a 10,000-number paste exceeds the Windows command-line
    # limit, so `sort` must accept the numbers from a file or from stdin.
    import io
    import random

    rng = random.Random(5)
    values = [rng.randint(-10**6, 10**6) for _ in range(10_000)]
    f = tmp_path / "nums.txt"
    f.write_text("\n".join(map(str, values)), encoding="utf-8")
    assert main(["sort", "--file", str(f), "--algo", "merge", "quick_median3"]) == 0
    assert f"sorted: {sorted(values)[:3]}"[:-1] in capsys.readouterr().out

    monkeypatch.setattr("sys.stdin", io.StringIO("3 1 2"))
    assert main(["sort", "-", "--algo", "insertion"]) == 0
    assert "sorted: [1, 2, 3]" in capsys.readouterr().out

    for bad in (["sort"], ["sort", "1 2", "--file", str(f)], ["sort", "--file", str(tmp_path / "nope.txt")]):
        with pytest.raises(SystemExit) as e:
            main(bad)
        assert str(e.value).startswith("error:")


def test_sort_warns_before_slow_quadratic_runs(tmp_path, capsys) -> None:
    # Review finding #5: a big list with Θ(n²) sorts must announce the wait instead of looking frozen.
    f = tmp_path / "n.txt"
    f.write_text(" ".join(str(i % 97) for i in range(2500)), encoding="utf-8")
    assert main(["sort", "--file", str(f), "--algo", "insertion", "merge"]) == 0
    err = capsys.readouterr().err
    assert "2,500 items with 1 Θ(n²) sort(s) may take about" in err
    assert main(["sort", "--file", str(f), "--algo", "merge"]) == 0          # no quadratic sort: no note
    assert "may take" not in capsys.readouterr().err


def test_subcommands_parse() -> None:
    p = build_parser()
    assert p.parse_args(["visualize", "--algo", "insertion", "--input", "nearly_sorted", "--n", "40"]).n == 40
    assert p.parse_args(["benchmark", "--quick"]).quick
    assert p.parse_args(["plot"]).csv.name == "results.csv"
    from sortscope.__main__ import parse_cli

    assert parse_cli(["test", "-k", "counts", "-q"]).pytest_args == ["-k", "counts", "-q"]
    assert parse_cli(["test"]).pytest_args == []
    with pytest.raises(SystemExit):      # unknown options are still errors for other commands
        parse_cli(["sort", "1 2", "--bogus"])


def test_fit_slope_recovers_power_law() -> None:
    import numpy as np

    n = np.array([500.0, 1000, 2000, 4000])
    assert abs(fit_slope(n, 3e-6 * n**2) - 2) < 1e-9


def test_analysis_end_to_end(tmp_path) -> None:
    csv_path = tmp_path / "results.csv"
    grid = build_grid(["insertion", "merge", "quick_first", "quick_random", "quick_median3"],
                      ["random", "sorted", "reverse", "nearly_sorted", "many_duplicates"], [250, 500, 1000])
    run_benchmark(grid, trials=1, seed=1, out=csv_path, verbose=False)
    paths = analyze(csv_path, tmp_path)
    figs = sorted(p.name for p in paths["figures"].glob("*.png"))
    assert len(figs) == 10
    assert all((paths["figures"] / f.replace(".png", ".txt")).exists() for f in figs)
    assert "Figure 1:" in (paths["figures"] / "captions.md").read_text(encoding="utf-8")
    slopes = (paths["tables"] / "slopes.md").read_text(encoding="utf-8")
    assert "| insertion |" in slopes
    doubling = (paths["tables"] / "doubling.md").read_text(encoding="utf-8")
    assert "250→500" in doubling and "500→1000" in doubling
