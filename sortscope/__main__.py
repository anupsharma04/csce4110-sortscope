"""SortScope entry point: interactive menu + argparse CLI (M6, menu owner: Gaurav).

    python -m sortscope                      # interactive numbered menu
    python -m sortscope visualize --algo insertion --input nearly_sorted --n 40
    python -m sortscope visualize --demo all | --demo insertion | --demo quick [--save out.gif]
    python -m sortscope benchmark [--quick] [--sizes ...] [--algorithms ...] [--types ...]
    python -m sortscope plot [--csv results/results.csv]
    python -m sortscope sort "5, 3, 9, 1"    # sort your own list with every algorithm
    python -m sortscope test                 # run the pytest suite

Every demo step is a single command; the menu just builds the same arguments.
"""

from __future__ import annotations

import argparse
import os
import statistics
import subprocess
import sys
from pathlib import Path

from sortscope import analysis, benchmark, visualizer
from sortscope.counter import OpCounter
from sortscope.inputs import input_kinds
from sortscope.registry import QUADRATIC, get_info, get_sort, names
from sortscope.validation import (INTERVAL_MS, PROJECT_ROOT, SORT_LIST_MAX, STEPS_PER_FRAME, VIS_LIST_MAX, VIS_N,
                                  check_int, parse_int_list, safe_console)

# `sort` times each algorithm like the benchmark does (median of 5 trials). Above this many
# items it times a single trial instead, so a long list with Θ(n²) sorts isn't run 6 times.
SORT_TIMING_FULL_MAX = 2000
SORT_TIMING_TRIALS = 5


# --------------------------------------------------------------------------- sort my list
def sort_list(values: list[int], algos: list[str]) -> str:
    """Sort a copy of ``values`` with each algorithm; return a table of counts and runtime.

    Two separate runs per algorithm, as in the benchmark: one with
    OpCounter for the counts, then timing trials with NullCounter so counting work is not
    inside the measured time. The counts are exact and repeatable; the time is not (tiny
    lists take microseconds, so expect it to vary from run to run).
    """
    trials = SORT_TIMING_TRIALS if len(values) <= SORT_TIMING_FULL_MAX else 1
    lines = [f"input:  {values}", f"sorted: {sorted(values)}", "",
             f"{'algorithm':<22}{'comparisons':>12}{'swaps':>8}{'writes':>8}{'time ms':>10}  stable"]
    for name in algos:
        arr, c = list(values), OpCounter()
        get_sort(name, seed=0)(arr, c)
        if arr != sorted(values):  # explicit check: `assert` is stripped under python -O
            raise RuntimeError(f"{name} did not sort the list correctly")
        ms = statistics.median(benchmark.time_trials(name, values, trials, seed=0))
        info = get_info(name)
        lines.append(f"{info.label:<22}{c.comparisons:>12}{c.swaps:>8}{c.writes:>8}{ms:>10.4f}"
                     f"  {'yes' if info.stable else 'no'}")
    how = f"median of {trials} runs" if trials > 1 else "one run"
    lines += ["", f"time ms: {how} without counting (NullCounter); counts are exact, times vary by machine"]
    return "\n".join(lines)


def run_tests(extra: list[str] | None = None) -> int:
    """Run pytest in a subprocess (same interpreter); extra arguments are passed through.

    Refuses to start when it is itself running inside pytest (pytest sets PYTEST_CURRENT_TEST
    while a test runs): a test that drives the menu into "Run tests" would otherwise start the
    whole suite again, which would reach the same test and start it again, without end.
    """
    if "PYTEST_CURRENT_TEST" in os.environ:
        print("  not starting the tests: already running inside pytest")
        return 1
    # cwd: pytest.ini and tests/ live in the project folder, wherever the command was typed.
    return subprocess.call([sys.executable, "-m", "pytest", "-q", *(extra or [])], cwd=PROJECT_ROOT)


# --------------------------------------------------------------------------- argparse
def build_parser() -> argparse.ArgumentParser:
    """The argparse parser with every subcommand (visualize, benchmark, plot, sort, test, menu)."""
    parser = argparse.ArgumentParser(prog="sortscope", description="Sorting visualizer and benchmark tool.")
    sub = parser.add_subparsers(dest="command")
    visualizer.add_arguments(sub.add_parser("visualize", help="animate one or two sorts (bars, live counters)"))
    benchmark.add_arguments(sub.add_parser("benchmark", help="run the benchmark grid -> results/results.csv"))
    analysis.add_arguments(sub.add_parser("plot", help="figures + tables from results/results.csv"))
    p = sub.add_parser("sort", help="sort your own list with every algorithm and show the counts")
    p.add_argument("values", nargs="?",
                   help='e.g. "5, 3, 9, 1" (put -- before a list that starts with "-", e.g. -- "-5,3"); '
                        "use - to read from stdin. Long lists: use --file or stdin, because the Windows "
                        "command line is limited to about 32,000 characters")
    p.add_argument("--file", type=Path, help="read the numbers from a text file instead")
    p.add_argument("--algo", nargs="+", choices=names(), default=names(), metavar="ALGO")
    sub.add_parser("test", help="run the pytest suite (extra arguments, e.g. -k counts -v, go to pytest)")
    sub.add_parser("menu", help="interactive menu (also the default with no command in a terminal)")
    return parser


def dispatch(args: argparse.Namespace) -> int:
    """Run the subcommand selected in ``args``; returns the process exit code."""
    if args.command == "visualize":
        return visualizer.run(args)
    if args.command == "benchmark":
        return benchmark.run(args)
    if args.command == "plot":
        return analysis.run(args)
    if args.command == "sort":
        if (args.values is None) == (args.file is None):
            raise SystemExit('error: give the numbers ("5, 3, 1"), - for stdin, or --file PATH (exactly one)')
        try:
            if args.file is not None:
                text = args.file.read_text(encoding="utf-8-sig")
            elif args.values == "-":
                text = sys.stdin.read()
            else:
                text = args.values
            values = parse_int_list(text, SORT_LIST_MAX)
        except (OSError, ValueError) as e:
            raise SystemExit(f"error: {e}")
        slow = [a for a in args.algo if a in QUADRATIC]
        if slow and len(values) > SORT_TIMING_FULL_MAX:
            # rough: n²/2 operations per Θ(n²) sort; one counted run (OpCounter is ~1.5x slower
            # than a timing run) plus one timing run (lists this long get a single timing trial)
            est = 2.5 * benchmark.SECONDS_PER_WORK_UNIT * len(slow) * len(values) ** 2 / 2
            print(f"note: {len(values):,} items with {len(slow)} Θ(n²) sort(s) may take about {est:.0f} s "
                  f"(use --algo merge quick_median3 ... to skip them)", file=sys.stderr, flush=True)
        print(sort_list(values, args.algo))
        return 0
    if args.command == "test":
        return run_tests(args.pytest_args)
    if args.command == "menu":
        return interactive_menu()
    raise SystemExit(f"unknown command {args.command!r}")


# --------------------------------------------------------------------------- menu
MENU = """
SortScope — CSCE 4110 (Big O Squad)
  1) Visualize a sort (choose algorithm, input, size and speed)
  2) Demo: all algorithms on one 40-item random list
  3) Demo: Insertion Sort on nearly sorted vs reverse
  4) Demo: Quick Sort first pivot vs median-of-three on sorted
  5) Sort my own list (counts and runtime for every algorithm)
  6) Benchmark — quick grid (seconds)
  7) Benchmark — full grid (minutes)
  8) Plot results (figures + tables)
  9) Run tests
  0) Quit
"""


def _ask(prompt: str, choices: list[str] | None = None, default: str | None = None) -> str:
    hint = f" [{default}]" if default else ""
    while True:
        # Windows PowerShell prefixes piped text with a byte-order mark (﻿); drop it.
        ans = input(f"{prompt}{hint}: ").lstrip("﻿").strip() or (default or "")
        if choices is None or ans in choices:
            return ans
        print(f"  choose one of: {', '.join(choices)}")


def _ask_int(prompt: str, default: int, lo: int, hi: int) -> int:
    """Re-prompt until the answer passes the same rule the CLI uses (validation.check_int)."""
    while True:
        try:
            return check_int(_ask(prompt, default=str(default)), prompt, lo, hi)
        except ValueError as e:
            print(f"  {e}")


def _ask_list(prompt: str, max_len: int) -> list[int] | None:
    """Re-prompt until the numbers parse (validation.parse_int_list); blank line = back to menu."""
    while True:
        text = _ask(f"{prompt} (blank = back)")
        if not text:
            return None
        try:
            return parse_int_list(text, max_len)
        except ValueError as e:
            print(f"  {e}")


def interactive_menu() -> int:
    """Numbered text menu; re-prompts on bad input, exits cleanly on Ctrl+C / Ctrl+D."""
    parser = build_parser()
    while True:
        print(MENU)
        try:
            choice = _ask("choose", [str(i) for i in range(10)])
            if choice == "0":
                return 0
            if choice == "1":
                algo = _ask(f"algorithm ({', '.join(names())})", names(), "insertion")
                kind = _ask(f"input ({', '.join(input_kinds())})", input_kinds(), "random")
                n = _ask_int("n", 30, *VIS_N)
                # Speed controls (proposal M3): the defaults are the CLI's own defaults.
                interval = _ask_int("speed: ms per frame (smaller = faster)", 40, *INTERVAL_MS)
                spf = _ask_int("speed: steps per frame (larger = faster)", 1, *STEPS_PER_FRAME)
                dispatch(parser.parse_args(["visualize", "--algo", algo, "--input", kind, "--n", str(n),
                                            "--interval", str(interval), "--steps-per-frame", str(spf)]))
            elif choice in ("2", "3", "4"):
                demo = {"2": "all", "3": "insertion", "4": "quick"}[choice]  # demo parts 2, 3, 4
                dispatch(parser.parse_args(["visualize", "--demo", demo, "--n", "40"]))
            elif choice == "5":
                values = _ask_list('your numbers, e.g. "5, 3, 9, 1"', VIS_LIST_MAX)
                if values is None:
                    continue
                print(sort_list(values, names()))
                if _ask("animate it? (y/n)", ["y", "n"], "n") == "y":
                    algo = _ask("algorithm", names(), "insertion")
                    as_text = " ".join(map(str, values))
                    dispatch(parser.parse_args(["visualize", "--algo", algo, f"--list={as_text}", "--interval", "300"]))
            elif choice == "6":
                dispatch(parser.parse_args(["benchmark", "--quick"]))
            elif choice == "7":
                dispatch(parser.parse_args(["benchmark"]))
            elif choice == "8":
                dispatch(parser.parse_args(["plot"]))
            elif choice == "9":
                run_tests()
        except (EOFError, KeyboardInterrupt):  # Ctrl-D / Ctrl-C: leave cleanly, no traceback
            print("\nbye")
            return 0
        except (ValueError, SystemExit) as e:  # bad input or a command's error message: stay in the menu
            print(f"  {e}")


def parse_cli(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line. Only `test` accepts unknown options; they are passed to pytest
    (argparse.REMAINDER can't capture arguments that start with '-', hence parse_known_args)."""
    parser = build_parser()
    args, extra = parser.parse_known_args(argv)
    if extra and args.command != "test":
        parser.error(f"unrecognized arguments: {' '.join(extra)}")
    args.pytest_args = extra
    return args


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``python -m sortscope``: menu in a terminal, otherwise the chosen command."""
    safe_console()
    args = parse_cli(argv)
    if args.command is None:
        if sys.stdin.isatty():
            return interactive_menu()
        build_parser().print_help()
        return 0
    try:
        return dispatch(args)
    except KeyboardInterrupt:  # Ctrl+C during a long benchmark/animation: no traceback
        print("\ninterrupted", file=sys.stderr)
        return 130            # conventional exit code for "terminated by Ctrl+C"


if __name__ == "__main__":
    raise SystemExit(main())
