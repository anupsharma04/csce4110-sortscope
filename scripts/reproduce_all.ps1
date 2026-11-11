# Reproduce every SortScope result from scratch (Windows PowerShell version of reproduce_all.sh):
#   tests -> full benchmark (results/results.csv) -> figures + tables -> demo GIFs.
# Run from anywhere with the project's virtual environment active:
#   powershell -ExecutionPolicy Bypass -File scripts\reproduce_all.ps1
# Takes roughly 10-20 minutes, mostly the benchmark. Keep the machine otherwise idle.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$py = if ($env:PYTHON) { $env:PYTHON } else { "python" }

function Run([string]$label, [string[]]$cmd) {
    Write-Output "== $label"
    & $py @cmd
    if ($LASTEXITCODE -ne 0) { throw "step failed: $label" }
}

Run "1/4 tests" @("-m", "pytest", "-q")
Run "2/4 full benchmark (5 trials, seed 4110)" @("-m", "sortscope", "benchmark")
Run "3/4 figures and tables" @("-m", "sortscope", "plot")
Run "4/4 demo animation (insertion)" @("-m", "sortscope", "visualize", "--demo", "insertion", "--n", "40",
    "--steps-per-frame", "4", "--save", "results/figures/demo_insertion.gif")
Run "4/4 demo animation (quick)" @("-m", "sortscope", "visualize", "--demo", "quick", "--n", "40",
    "--steps-per-frame", "4", "--save", "results/figures/demo_quick.gif")
Write-Output "done: results/results.csv, results/figures/, results/tables/"
