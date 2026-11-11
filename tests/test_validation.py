"""Every input-validation rule, at every boundary: CLI flags, the menu, typed lists.

Rule summary (sortscope/validation.py):
* integers: ASCII whole numbers only, inside a per-mode range; the message says the range
* names: argparse `choices`; the message lists the valid names
* typed lists: commas and/or whitespace; the bad token and its position are named; length capped
* menu: re-prompts on bad input; Ctrl+C / Ctrl+D leave cleanly
* the sort functions themselves do no validation (they stay pure)
"""

from __future__ import annotations

import builtins

import matplotlib

matplotlib.use("Agg")

import pytest

from sortscope import __main__ as cli
from sortscope.counter import OpCounter
from sortscope.registry import get_sort, names
from sortscope.validation import (BENCH_N, SORT_LIST_MAX, VIS_LIST_MAX, VIS_N, check_int,
                                  parse_int_list)


def cli_error(argv: list[str], capsys) -> str:
    """Run the CLI parser on argv, assert it rejects it, return the error text."""
    with pytest.raises(SystemExit) as e:
        cli.parse_cli(argv)
    assert e.value.code == 2
    return capsys.readouterr().err


# ----------------------------------------------------------------- check_int
@pytest.mark.parametrize("value, expected", [("0", 0), ("200", 200), (" 7 ", 7), ("+5", 5), (12, 12)])
def test_check_int_accepts_whole_numbers_in_range(value, expected) -> None:
    assert check_int(value, "n", 0, 200) == expected


@pytest.mark.parametrize("value", ["abc", "1.5", "1e3", "1_000", "0x10", "", " ", "３", "١", "--5", True, None, 2.0])
def test_check_int_rejects_non_integers(value) -> None:
    with pytest.raises(ValueError, match=r"n must be a whole number from 0 to 200; got"):
        check_int(value, "n", 0, 200)


@pytest.mark.parametrize("value", ["-1", "201", str(10**7)])
def test_check_int_rejects_out_of_range_and_says_why(value) -> None:
    with pytest.raises(ValueError, match=r"from 0 to 200; got .* \(small inputs only\)"):
        check_int(value, "n", 0, 200, hint="small inputs only")


# ----------------------------------------------------------------- visualize flags
@pytest.mark.parametrize("bad", ["-1", "201", "10000000", "abc", "3.5"])
def test_visualize_n_range(bad, capsys) -> None:
    err = cli_error(["visualize", "--n", bad], capsys)
    assert f"--n must be a whole number from {VIS_N[0]} to {VIS_N[1]}" in err


@pytest.mark.parametrize("ok", ["0", "200"])
def test_visualize_n_boundaries_accepted(ok) -> None:
    assert cli.parse_cli(["visualize", "--n", ok]).n == int(ok)


@pytest.mark.parametrize("flag, bad, rng", [
    ("--interval", "0", "1 to 10,000"), ("--interval", "10001", "1 to 10,000"),
    ("--steps-per-frame", "0", "1 to 10,000"), ("--seed", "-1", "0 to 4,294,967,295"),
])
def test_visualize_other_numeric_flags(flag, bad, rng, capsys) -> None:
    assert f"{flag} must be a whole number from {rng}" in cli_error(["visualize", flag, bad], capsys)


def test_visualize_list_names_bad_token_and_caps_length(capsys) -> None:
    assert "not an integer: 'x' (item 2)" in cli_error(["visualize", "--list", "1 x 3"], capsys)
    too_many = " ".join(["1"] * (VIS_LIST_MAX + 1))
    assert f"too many items ({VIS_LIST_MAX + 1:,}); the maximum here is {VIS_LIST_MAX}" in cli_error(
        ["visualize", "--list", too_many], capsys)
    assert cli.parse_cli(["visualize", "--list", " ".join(["1"] * VIS_LIST_MAX)]).custom == [1] * VIS_LIST_MAX


@pytest.mark.parametrize("flag, bad, valid", [
    ("--algo", "bogo", "bubble"), ("--input", "zigzag", "nearly_sorted"), ("--demo", "everything", "quick"),
])
def test_visualize_names_list_valid_choices(flag, bad, valid, capsys) -> None:
    err = cli_error(["visualize", flag, bad], capsys)
    assert f"invalid choice: '{bad}'" in err and valid in err


# ----------------------------------------------------------------- benchmark flags
@pytest.mark.parametrize("bad", ["0", "-5", str(BENCH_N[1] + 1), "1.5", "big"])
def test_benchmark_sizes_range(bad, capsys) -> None:
    err = cli_error(["benchmark", "--sizes", "100", bad], capsys)
    assert f"--sizes value must be a whole number from 1 to {BENCH_N[1]:,}" in err


def test_benchmark_sizes_over_max_explains_the_limit(capsys) -> None:
    err = cli_error(["benchmark", "--sizes", "200000"], capsys)
    assert "proposal's grid goes up to 100,000" in err and "recorded as skipped" in err


def test_benchmark_size_boundaries_accepted() -> None:
    assert cli.parse_cli(["benchmark", "--sizes", "1", str(BENCH_N[1])]).sizes == [1, BENCH_N[1]]


@pytest.mark.parametrize("flag, bad", [("--trials", "0"), ("--trials", "101"), ("--seed", "-3"), ("--seed", "x")])
def test_benchmark_trials_and_seed(flag, bad, capsys) -> None:
    assert f"{flag} must be a whole number from" in cli_error(["benchmark", flag, bad], capsys)


@pytest.mark.parametrize("flag, bad, valid", [("--algorithms", "heap", "quick_median3"), ("--types", "zigzag", "reverse")])
def test_benchmark_names_list_valid_choices(flag, bad, valid, capsys) -> None:
    err = cli_error(["benchmark", flag, bad], capsys)
    assert f"invalid choice: '{bad}'" in err and valid in err


# ----------------------------------------------------------------- sort command
def test_sort_caps_length_and_names_bad_token(tmp_path, capsys) -> None:
    f = tmp_path / "too_many.txt"
    f.write_text(" ".join(["1"] * (SORT_LIST_MAX + 1)), encoding="utf-8")
    with pytest.raises(SystemExit, match=r"too many items \(10,001\); the maximum here is 10,000"):
        cli.main(["sort", "--file", str(f)])
    with pytest.raises(SystemExit, match=r"not an integer: '2\.5' \(item 3\)"):
        cli.main(["sort", "1, 2, 2.5"])
    err = cli_error(["sort", "1 2", "--algo", "bogo"], capsys)
    assert "invalid choice: 'bogo'" in err and "quick_median3" in err


# ----------------------------------------------------------------- parse_int_list
@pytest.mark.parametrize("text, expected", [
    ("5,3,9", [5, 3, 9]), ("5 3 9", [5, 3, 9]), ("5, 3 ,9", [5, 3, 9]), ("5\n3\t9", [5, 3, 9]),
    ("[5, 3, 9]", [5, 3, 9]), (",,5,,3,,", [5, 3]), ("+5 -3 0", [5, -3, 0]), ("﻿7", [7]),
    ("-1000000000000000000", [-10**18]),
])
def test_list_separators(text, expected) -> None:
    assert parse_int_list(text, 100) == expected


@pytest.mark.parametrize("text, token, item", [
    ("1;2;3", "1;2;3", 1), ("1 2.0", "2.0", 2), ("1 2 three", "three", 3), ("0x10", "0x10", 1),
    ("1e3", "1e3", 1), ("1_000", "1_000", 1), ("--5", "--5", 1), ("4 ３", "３", 2),
])
def test_list_rejects_non_integers_naming_token(text, token, item) -> None:
    with pytest.raises(ValueError) as e:
        parse_int_list(text, 100)
    assert f"not an integer: {token!r} (item {item})" in str(e.value)


def test_list_unicode_digit_gets_hint() -> None:
    with pytest.raises(ValueError, match=r"use digits 0-9"):
        parse_int_list("١ ٢", 100)


@pytest.mark.parametrize("text", ["", "   ", "[]", ",,,", "﻿"])
def test_list_empty(text) -> None:
    with pytest.raises(ValueError, match="enter at least one integer"):
        parse_int_list(text, 100)


def test_list_length_cap_boundary() -> None:
    assert len(parse_int_list(" ".join(["1"] * 5), 5)) == 5
    with pytest.raises(ValueError, match=r"too many items \(6\); the maximum here is 5"):
        parse_int_list(" ".join(["1"] * 6), 5)
    assert len(parse_int_list(" ".join(["1"] * 10_000), None)) == 10_000   # None = no cap


def test_list_too_many_digits() -> None:
    with pytest.raises(ValueError, match=r"integer too long: item 2 has 31 digits \(maximum 30\)"):
        parse_int_list("1 " + "9" * 31, 100)


# ----------------------------------------------------------------- menu
def scripted(monkeypatch, answers):
    it = iter(answers)

    def fake_input(prompt=""):
        try:
            ans = next(it)
        except StopIteration:
            raise EOFError
        if isinstance(ans, BaseException):
            raise ans
        return ans

    monkeypatch.setattr(builtins, "input", fake_input)


def test_menu_reprompts_for_bad_n_then_uses_good_one(monkeypatch, capsys) -> None:
    calls = []
    monkeypatch.setattr(cli, "dispatch", lambda args: calls.append(args) or 0)
    scripted(monkeypatch, ["1", "bogo", "merge", "random", "abc", "-1", "999", "25", "", "", "0"])  # "" = default speed
    assert cli.interactive_menu() == 0    # (main(["menu"]) would route through the patched dispatch)
    out = capsys.readouterr().out
    assert "choose one of:" in out                                   # bad algorithm name
    assert out.count("n must be a whole number from 0 to 200") == 3  # abc, -1, 999
    assert calls[0].algo == ["merge"] and calls[0].n == 25


def test_menu_reprompts_for_bad_list(monkeypatch, capsys) -> None:
    scripted(monkeypatch, ["5", "1 two 3", "1;2", "3, 1, 2", "n", "0"])
    assert cli.main(["menu"]) == 0
    out = capsys.readouterr().out
    assert "not an integer: 'two' (item 2)" in out and "not an integer: '1;2' (item 1)" in out
    assert "sorted: [1, 2, 3]" in out


def test_menu_blank_list_goes_back(monkeypatch, capsys) -> None:
    scripted(monkeypatch, ["5", "", "0"])
    assert cli.main(["menu"]) == 0
    assert "sorted:" not in capsys.readouterr().out


def test_menu_bad_choice_reprompts(monkeypatch, capsys) -> None:
    scripted(monkeypatch, ["10", "x", "0"])
    assert cli.main(["menu"]) == 0
    assert capsys.readouterr().out.count("choose one of: 0, 1, 2, 3, 4, 5, 6, 7, 8, 9") == 2


def test_menu_run_tests_does_not_recurse_inside_pytest(monkeypatch, capsys) -> None:
    # Regression: a scripted menu test that chose "Run tests" started pytest inside pytest,
    # which started it again, without end. run_tests() must refuse when already under pytest.
    def no_subprocess(*args, **kwargs):
        raise AssertionError("run_tests started a subprocess from inside pytest")
    monkeypatch.setattr(cli.subprocess, "call", no_subprocess)
    scripted(monkeypatch, ["9", "0"])            # 9 = Run tests
    assert cli.main(["menu"]) == 0
    assert "already running inside pytest" in capsys.readouterr().out
    assert cli.run_tests() == 1


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt(), EOFError()])
def test_menu_ctrl_c_and_ctrl_d_exit_cleanly(monkeypatch, capsys, interrupt) -> None:
    scripted(monkeypatch, ["5", interrupt])
    assert cli.main(["menu"]) == 0
    assert "bye" in capsys.readouterr().out


def test_ctrl_c_during_a_command_inside_the_menu(monkeypatch, capsys) -> None:
    def boom(args):
        raise KeyboardInterrupt
    monkeypatch.setattr(cli, "dispatch", boom)
    scripted(monkeypatch, ["6"])                 # benchmark --quick, interrupted
    assert cli.interactive_menu() == 0
    assert "bye" in capsys.readouterr().out


def test_ctrl_c_during_a_cli_command_exits_130(monkeypatch, capsys) -> None:
    def boom(args):
        raise KeyboardInterrupt
    monkeypatch.setattr(cli, "dispatch", boom)
    assert cli.main(["sort", "3 1 2"]) == 130
    assert "interrupted" in capsys.readouterr().err


# ----------------------------------------------------------------- sorts stay pure
@pytest.mark.parametrize("name", names())
def test_sort_functions_do_not_validate(name) -> None:
    """The sorts accept anything comparable with `<` — no type or range checks inside them.
    (Validation lives only at the input boundaries above.)"""
    for data in (["pear", "apple", "fig"], [2.5, -1.0, 2.5, 0.0], [10**40, -(10**40), 0], []):
        arr = list(data)
        get_sort(name, seed=1)(arr, OpCounter())
        assert arr == sorted(data)
