"""Visualizer logic (headless): event->state mapping, panel pairing, saving a GIF."""

import matplotlib

matplotlib.use("Agg")

import pytest

# Some tests build an animation and step frames by hand without rendering it;
# matplotlib warns when such an object is garbage-collected. Harmless here.
pytestmark = pytest.mark.filterwarnings("ignore:Animation was deleted")

from sortscope.counter import OpCounter
from sortscope.inputs import generate
from sortscope.registry import get_sort, names
from sortscope.visualizer import COLORS, PanelState, build_animation, main, make_panels


@pytest.mark.parametrize("name", names())
def test_panel_ends_sorted_with_benchmark_counts(name: str) -> None:
    arr = generate("random", 25, seed=3)
    p = PanelState(name, "random", arr, seed=3)
    while not p.done:
        p.advance(7)
    c = OpCounter()
    expected = list(arr)
    get_sort(name, seed=3)(expected, c)
    assert p.arr == expected
    assert (p.comparisons, p.swaps, p.writes) == (c.comparisons, c.swaps, c.writes)
    assert p.final == set(range(25))
    assert p.pivot == -1
    p.advance(1)  # a "hold" frame after the last event clears the last highlight
    assert all(p.bar_style(i)[0] == COLORS["final"] for i in range(25))


def test_highlights_are_per_frame() -> None:
    p = PanelState("bubble", "reverse", [3, 2, 1])
    p.advance(1)  # compare(1, 0)
    assert p.compared == {0, 1} and p.bar_style(0)[0] == COLORS["compare"]
    p.advance(1)  # swap(0, 1): previous compare highlight cleared
    assert p.compared == set() and p.changed == {0, 1}
    assert p.bar_style(0) == (COLORS["change"], 1.6)
    assert p.arr == [2, 3, 1]


def test_make_panels_pairing() -> None:
    pairs = lambda ps: [(p.algo, p.kind) for p in ps]
    assert pairs(make_panels(["insertion"], ["nearly_sorted", "reverse"], 10, 0)) == [
        ("insertion", "nearly_sorted"), ("insertion", "reverse")]
    assert pairs(make_panels(["quick_first", "quick_median3"], ["sorted"], 10, 0)) == [
        ("quick_first", "sorted"), ("quick_median3", "sorted")]
    ps = make_panels(["merge", "bubble"], ["random"], 10, 0, custom=[3, 1, 2])
    assert [p.arr for p in ps] == [[3, 1, 2], [3, 1, 2]] and ps[0].kind == "custom"
    with pytest.raises(ValueError):   # 3 algorithms with 2 inputs: ambiguous pairing
        make_panels(["bubble", "merge", "insertion"], ["random", "sorted"], 10, 0)


def test_demo_all_and_inputs_build_grids() -> None:
    from sortscope.visualizer import DEMOS

    algos, kinds = DEMOS["all"]
    panels = make_panels(algos, kinds, 12, 0)
    assert [p.algo for p in panels] == names()
    assert len({tuple(p.arr) for p in panels}) == 1          # all on the same input
    algos, kinds = DEMOS["inputs"]
    assert [p.kind for p in make_panels(algos, kinds, 12, 0)] == [
        "random", "sorted", "reverse", "nearly_sorted", "many_duplicates"]


@pytest.mark.parametrize("demo", ["all", "inputs"])
def test_grid_demo_saves_gif(tmp_path, demo: str) -> None:
    out = tmp_path / f"{demo}.gif"
    assert main(["--demo", demo, "--n", "8", "--steps-per-frame", "20", "--save", str(out), "--allow-outside-results"]) == 0
    assert out.exists() and out.stat().st_size > 0


@pytest.mark.filterwarnings("ignore:Animation was deleted")  # we step frames by hand, never render
def test_animation_runs_all_frames_side_by_side() -> None:
    panels = make_panels(["quick_first", "quick_median3"], ["sorted"], 30, 0)
    fig, anim, update = build_animation(panels, interval=1, steps_per_frame=5)
    for f in range(200):
        update(f)
    assert all(p.done for p in panels)
    assert all(p.arr == list(range(30)) for p in panels)


@pytest.mark.parametrize("name", names())
def test_reset_restores_the_original_input_and_replays_identically(name: str) -> None:
    arr = generate("random", 25, seed=3)
    p = PanelState(name, "random", arr, seed=3)
    p.advance(40)                       # stop mid-sort, with highlights and counters set
    assert p.pos == 40 and p.comparisons > 0
    p.reset()
    assert p.arr == arr == p.initial
    assert (p.pos, p.comparisons, p.swaps, p.writes) == (0, 0, 0, 0)
    assert (p.compared, p.changed, p.final, p.pivot) == (set(), set(), set(), -1)
    assert all(p.bar_style(i) == (COLORS["default"], 0.0) for i in range(25))
    while not p.done:                   # the replay does exactly the benchmark's work again
        p.advance(7)
    c = OpCounter()
    expected = list(arr)
    get_sort(name, seed=3)(expected, c)
    assert p.arr == expected
    assert (p.comparisons, p.swaps, p.writes) == (c.comparisons, c.swaps, c.writes)


def test_reset_after_finishing() -> None:
    p = PanelState("merge", "custom", [4, -2, 3, -2, 1])
    while not p.done:
        p.advance(3)
    assert p.arr == [-2, -2, 1, 3, 4]
    p.reset()
    assert p.arr == [4, -2, 3, -2, 1] and not p.done and p.final == set()


def _press(fig, key: str) -> None:
    """Send a key press to the figure the way a real window would."""
    from matplotlib.backend_bases import KeyEvent

    fig.canvas.callbacks.process("key_press_event", KeyEvent("key_press_event", fig.canvas, key))


def test_space_pauses_and_r_restarts() -> None:
    from sortscope.visualizer import KEY_HINTS

    panels = make_panels(["quick_first", "insertion"], ["reverse"], 20, 0)
    start = list(panels[0].arr)
    fig, anim, update = build_animation(panels, interval=1, steps_per_frame=3, interactive=True)
    assert [t.get_text() for t in fig.texts] == [KEY_HINTS]     # hints are on the figure
    update(0)
    assert [p.pos for p in panels] == [3, 3]
    _press(fig, " ")                    # pause: frames no longer advance anything
    update(1)
    assert [p.pos for p in panels] == [3, 3]
    assert fig.texts[0].get_text().startswith("PAUSED")
    _press(fig, " ")                    # resume
    update(2)
    assert [p.pos for p in panels] == [6, 6]
    _press(fig, "x")                    # other keys do nothing
    assert [p.pos for p in panels] == [6, 6]

    _press(fig, " ")                    # restart while paused: rewinds AND un-pauses
    _press(fig, "r")
    assert all(p.pos == 0 and p.arr == start and p.comparisons == 0 for p in panels)
    assert fig.texts[0].get_text() == KEY_HINTS
    update(3)
    assert [p.pos for p in panels] == [3, 3]

    for f in range(400):                # run to the end, then restart the finished animation
        update(f)
    assert all(p.done and p.arr == sorted(start) for p in panels)
    counts = [(p.comparisons, p.swaps, p.writes) for p in panels]
    _press(fig, " ")                    # space on a finished animation is ignored
    _press(fig, "r")
    assert all(p.pos == 0 and p.arr == start for p in panels)
    for f in range(400):
        update(f)
    assert [(p.comparisons, p.swaps, p.writes) for p in panels] == counts


def test_saved_animation_has_no_key_hints() -> None:
    fig, anim, update = build_animation(make_panels(["bubble"], ["random"], 8, 0))
    assert fig.texts == [] and not hasattr(fig, "controls") and len(fig.axes) == 1   # no widgets either
    _press(fig, "r")                    # keys are not connected: nothing happens, nothing breaks


def _click(fig, widget) -> None:
    """Press and release the left mouse button in the middle of a widget, like a real click."""
    from matplotlib.backend_bases import MouseEvent

    x, y = widget.ax.transAxes.transform((0.5, 0.5))
    for name in ("button_press_event", "button_release_event"):
        fig.canvas.callbacks.process(name, MouseEvent(name, fig.canvas, x, y, button=1))


def _window(algos=("insertion",), kinds=("reverse",), n=20, custom=None):
    panels = make_panels(list(algos), list(kinds), n, 0, custom)
    fig, anim, update = build_animation(panels, interval=1, steps_per_frame=3, interactive=True)
    return panels, fig, update, fig.controls.widgets


def test_buttons_start_pause_restart() -> None:
    panels, fig, update, w = _window()
    start = list(panels[0].arr)
    update(0)
    _click(fig, w.pause)
    update(1)
    assert panels[0].pos == 3 and fig.texts[0].get_text().startswith("PAUSED")
    _click(fig, w.start)
    update(2)
    assert panels[0].pos == 6
    _press(fig, " ")                    # the keyboard shortcut still works next to the buttons
    _click(fig, w.restart)              # restart while paused: rewinds and plays
    assert panels[0].pos == 0 and panels[0].arr == start
    update(3)
    assert panels[0].pos == 3


def test_radio_buttons_load_a_new_panel_and_wait_for_start() -> None:
    panels, fig, update, w = _window()
    update(0)
    w.algo.set_active(names().index("merge"))
    p = panels[0]
    assert (p.algo, p.kind, p.pos) == ("merge", "reverse", 0) and p.arr == generate("reverse", 20, 0)
    assert "Merge" in fig.axes[0].get_title(loc="left")
    update(1)                           # paused until Start
    assert p.pos == 0
    w.kind.set_active(w.kind.labels.index(next(t for t in w.kind.labels if t.get_text() == "many_duplicates")))
    p = panels[0]
    assert (p.algo, p.kind) == ("merge", "many_duplicates") and p.arr == generate("many_duplicates", 20, 0)
    _click(fig, w.start)
    for f in range(200):
        update(f)
    c = OpCounter()                     # the newly chosen sort still matches the benchmark counts
    expected = generate("many_duplicates", 20, 0)
    get_sort("merge", seed=0)(expected, c)
    assert p.arr == expected and (p.comparisons, p.swaps, p.writes) == (c.comparisons, c.swaps, c.writes)


def test_n_and_speed_sliders() -> None:
    panels, fig, update, w = _window()
    w.n.set_val(50)
    p = panels[0]
    assert p.arr == generate("reverse", 50, 0) and len(fig.axes[0].patches) == 50
    assert (w.n.valmin, w.n.valmax) == (5, 200)
    w.speed.set_val(7)
    update(0)
    assert p.pos == 0                   # the n change paused it
    _press(fig, " ")                    # space starts it, like the Start button
    update(1)
    assert p.pos == 7                   # 7 events per frame now


def test_side_by_side_window_keeps_its_pairing() -> None:
    panels, fig, update, w = _window(["quick_first", "quick_median3"], ["sorted"])
    assert not hasattr(w, "algo") and not hasattr(w, "kind")    # radios are single-panel only
    w.n.set_val(12)                     # the n slider applies to every panel
    assert [(p.algo, p.kind, p.arr) for p in panels] == [
        ("quick_first", "sorted", list(range(12))), ("quick_median3", "sorted", list(range(12)))]
    _click(fig, w.start)
    update(0)
    assert [p.pos for p in panels] == [3, 3]


def test_typed_list_survives_control_changes() -> None:
    panels, fig, update, w = _window(custom=[4, -2, 3, -2, 1])
    assert [t.get_text() for t in w.kind.labels][-1] == "custom"
    w.n.set_val(30)                     # n does not apply to a typed list
    w.algo.set_active(names().index("selection"))
    assert (panels[0].algo, panels[0].arr) == ("selection", [4, -2, 3, -2, 1])
    w.kind.set_active(0)                # away to a generated input ...
    assert len(panels[0].arr) == 30
    w.kind.set_active(len(w.kind.labels) - 1)   # ... and back to the typed list
    assert panels[0].arr == [4, -2, 3, -2, 1]


def test_save_gif(tmp_path) -> None:
    out = tmp_path / "bubble.gif"
    assert main(["--algo", "bubble", "--list", "4 2 3 1", "--interval", "50", "--save", str(out), "--allow-outside-results"]) == 0
    assert out.exists() and out.stat().st_size > 0


def test_bad_save_target_fails_before_rendering(tmp_path, monkeypatch) -> None:
    from matplotlib import animation

    with pytest.raises(SystemExit, match="must end in"):
        main(["--algo", "bubble", "--n", "5", "--save", str(tmp_path / "x.avi"), "--allow-outside-results"])
    monkeypatch.setattr(animation.writers, "is_available", lambda name: False)
    with pytest.raises(SystemExit, match="ffmpeg"):
        main(["--algo", "bubble", "--n", "5", "--save", str(tmp_path / "x.mp4"), "--allow-outside-results"])
    assert not (tmp_path / "x.mp4").exists()


def test_rejects_huge_n() -> None:
    with pytest.raises(SystemExit):
        main(["--n", "5000", "--save", "x.gif"])


def test_save_outside_results_is_refused(tmp_path) -> None:
    # Review finding #1: --save could write (or overwrite) a .gif anywhere on disk.
    with pytest.raises(SystemExit, match="refusing to write outside"):
        main(["--algo", "bubble", "--n", "5", "--save", str(tmp_path / "x.gif")])
    assert not (tmp_path / "x.gif").exists()
