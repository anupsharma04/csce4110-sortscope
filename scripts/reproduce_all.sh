#!/usr/bin/env bash
# Reproduce every SortScope result from scratch:
#   tests -> full benchmark (results/results.csv) -> figures + tables -> demo GIFs.
# Run from anywhere, with the project's virtual environment active
# (or set PYTHON=/path/to/python). Takes roughly 10-20 minutes, mostly the benchmark.
set -euo pipefail

cd "$(dirname "$0")/.."
PY="${PYTHON:-python}"

echo "== 1/4 tests"
"$PY" -m pytest -q

echo "== 2/4 full benchmark (5 trials, seed 4110)"
"$PY" -m sortscope benchmark

echo "== 3/4 figures and tables"
"$PY" -m sortscope plot

echo "== 4/4 demo animations"
"$PY" -m sortscope visualize --demo insertion --n 40 --steps-per-frame 4 --save results/figures/demo_insertion.gif
"$PY" -m sortscope visualize --demo quick --n 40 --steps-per-frame 4 --save results/figures/demo_quick.gif

echo "done: results/results.csv, results/figures/, results/tables/"
