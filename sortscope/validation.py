"""Input validation for every user-facing boundary: CLI flags, the interactive menu,
and typed number lists. One place, one wording.

Design rule: the sort functions themselves never validate. They take a
list and a counter and stay pure. Everything a *user* can type is checked here first.

Limits per mode:
* visualizer  n: 0..200      (bars become unreadable beyond ~200; use the benchmark)
* benchmark   n: 1..100,000  (the largest size in the proposal; Θ(n²) sorts above 5,000
                              are still recorded as skipped by the benchmark itself)
* typed lists: 200 items for the visualizer/menu, 10,000 for `sortscope sort`
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Outputs (CSV, figures, tables, animations) may only be written inside <project>/results/,
# so a typo like `--out README.md` can never overwrite source files. Paths are anchored to the
# project folder, not the current directory, so running from elsewhere doesn't scatter files.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "results"
ALLOW_OUTSIDE_FLAG = "--allow-outside-results"

VIS_N = (0, 200)
BENCH_N = (1, 100_000)
TRIALS = (1, 100)
SEED = (0, 2**32 - 1)
INTERVAL_MS = (1, 10_000)
STEPS_PER_FRAME = (1, 10_000)
VIS_LIST_MAX = VIS_N[1]
SORT_LIST_MAX = 10_000
MAX_DIGITS = 30            # |value| < 10^30 — far beyond anything the tool needs

_INT_RE = re.compile(r"[+-]?[0-9]+")   # ASCII digits only: no '1.5', '1e3', '1_000', '３'


def safe_console() -> None:
    """Never crash on a character the output stream can't encode.

    Our messages use Θ, ≈, ², → ... A Windows terminal shows them, but when output is piped or
    redirected (``> log.txt``, ``| more``) Python falls back to the legacy code page (cp1252),
    where printing "≈" raises UnicodeEncodeError and kills a benchmark at its first line.
    With errors="replace" such a character becomes "?" instead; the encoding is unchanged.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError, OSError):  # replaced stream (tests, IDEs): leave it
            pass


def check_int(value: object, name: str, lo: int, hi: int, hint: str = "") -> int:
    """Return ``value`` as an int in [lo, hi], or raise ValueError saying what is allowed."""
    allowed = f"{name} must be a whole number from {lo:,} to {hi:,}"
    text = str(value).strip()
    if isinstance(value, bool) or not _INT_RE.fullmatch(text):
        raise ValueError(f"{allowed}; got {value!r}")
    n = int(text)
    if not lo <= n <= hi:
        raise ValueError(f"{allowed}; got {n:,}" + (f" ({hint})" if hint else ""))
    return n


def int_arg(name: str, lo: int, hi: int, hint: str = ""):
    """argparse ``type=`` function: same rule and message as :func:`check_int`."""

    def parse(text: str) -> int:
        """argparse type hook: apply check_int, report failures as argparse errors."""
        try:
            return check_int(text, name, lo, hi, hint)
        except ValueError as e:
            raise argparse.ArgumentTypeError(str(e)) from None

    parse.__name__ = name  # argparse uses this in some messages
    return parse


def check_output_path(path: Path | str, *, suffixes: tuple[str, ...] = (), allow_outside: bool = False) -> Path:
    """Validate where a command is about to write; return the resolved path.

    * must lie inside ``results/`` (unless ``allow_outside``, i.e. the user passed
      ``--allow-outside-results`` on purpose)
    * if ``suffixes`` is given, the file name must end with one of them (``.csv``, ``.gif``, ...)
    """
    p = Path(path).expanduser().resolve()
    if suffixes and p.suffix.lower() not in suffixes:
        raise ValueError(f"output file must end in {' or '.join(suffixes)}; got {p.name!r}")
    if not allow_outside and not p.is_relative_to(RESULTS_DIR):
        raise ValueError(f"refusing to write outside {RESULTS_DIR} (got {p}); write under results/ "
                         f"or pass {ALLOW_OUTSIDE_FLAG} if you really mean it")
    return p


def parse_int_list(text: str, max_len: int | None) -> list[int]:
    """Parse "5, 3 -2,8" / "[5, 3, -2]" / one number per line into a list of ints.

    * separators: commas and/or any whitespace (newlines included); runs of them count as one
    * surrounding [ ] are allowed; a leading byte-order mark (PowerShell pipes) is ignored
    * every token must be an ASCII integer like 42, -7 or +3; the error names the bad token
      and its position
    * the list may not be empty and may not exceed ``max_len`` items
    """
    cleaned = text.lstrip("﻿").strip()
    if cleaned.startswith("[") and cleaned.endswith("]"):
        cleaned = cleaned[1:-1]
    tokens = cleaned.replace(",", " ").split()
    if not tokens:
        raise ValueError("enter at least one integer, e.g. 5, 3, 9, 1")
    if max_len is not None and len(tokens) > max_len:
        raise ValueError(f"too many items ({len(tokens):,}); the maximum here is {max_len:,}")
    values: list[int] = []
    for pos, tok in enumerate(tokens, 1):
        if not _INT_RE.fullmatch(tok):
            hint = " (use digits 0-9)" if any(ch.isdigit() for ch in tok) and not tok.isascii() else ""
            raise ValueError(f"not an integer: {tok!r} (item {pos}){hint}")
        if len(tok.lstrip("+-")) > MAX_DIGITS:
            raise ValueError(f"integer too long: item {pos} has {len(tok.lstrip('+-'))} digits "
                             f"(maximum {MAX_DIGITS})")
        values.append(int(tok))
    return values
