"""Smoke test: the package and every skeleton module import cleanly.

Real test modules (correctness, stability, closed-form counts, step equivalence,
inputs) are added alongside each phase.
"""

import importlib

import pytest

MODULES = [
    "sortscope",
    "sortscope.__main__",
    "sortscope.counter",
    "sortscope.registry",
    "sortscope.inputs",
    "sortscope.algorithms",
    "sortscope.steps",
    "sortscope.visualizer",
    "sortscope.benchmark",
    "sortscope.analysis",
]


@pytest.mark.parametrize("name", MODULES)
def test_module_imports(name: str) -> None:
    importlib.import_module(name)


def test_cli_without_command_prints_help() -> None:
    from sortscope.__main__ import main

    assert main([]) == 0
