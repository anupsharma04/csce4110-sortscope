"""Bar-chart animation of a sort, driven by step events (M3, owner: Anup).

How events become frames (the part to walk through in the video):

1. ``PanelState`` runs the step generator once up front and stores the full
   event list (cheap for the small n we animate).
2. Every animation frame calls ``advance(steps_per_frame)``: it clears the
   previous frame's highlights, then applies the next k events to the
   panel's *own* copy of the array:
       compare i j  -> bars i, j yellow;            comparisons += 1
       swap i j     -> exchange heights, bars red;  swaps += 1, writes += 2
       write i v    -> set height of bar i, red;    writes += 1
       pivot i      -> bar i violet until the next pivot event (-1 = none)
       sorted i     -> bar i green from now on
3. ``_draw`` repaints bar heights and colors and the counter text.
   Color priority per bar: swapped/written > pivot > compared > final > default
   (the pivot is compared on almost every step, so it must win over yellow).
   Bar height is value - min + 1, so the smallest value is still a visible bar.
   Red/green are hard to tell apart for some color-blind viewers, so swapped or
   written bars also get a dark outline, and a legend names every color.

Because the counters are computed from the events, the numbers on screen are
the same ones the counted benchmark version reports (tests prove this).

Controls in the window (not in saved GIF/MP4 files; see ``build_animation``):
    space / Start, Pause buttons   pause / resume
    r / Restart button             restart every panel from its original unsorted input
    n slider, speed slider         input size (5-200), events applied per frame
    radio buttons (one panel only) algorithm and input type
Changing n, the algorithm or the input type builds a new ``PanelState`` and
waits, paused, for Start. Restart is ``PanelState.reset()``: put back the saved copy of the input, zero
the counters, rewind to event 0. The event list is reused, not recomputed —
the same input (and seed) always produces the same events.

Examples:
    python -m sortscope visualize --algo insertion --input random --n 30
    python -m sortscope visualize --demo insertion      # nearly sorted vs reverse
    python -m sortscope visualize --demo quick          # first vs median-of-3 on sorted
    python -m sortscope visualize --algo merge --list "5 3 9 1 7" --interval 200
    python -m sortscope visualize --demo quick --save results/figures/quick.gif
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, field

from sortscope.inputs import generate, input_kinds
from sortscope.validation import (ALLOW_OUTSIDE_FLAG, INTERVAL_MS, SEED, STEPS_PER_FRAME, VIS_LIST_MAX, VIS_N,
                                  check_output_path, int_arg, parse_int_list, safe_console)
from sortscope.registry import get_info, names
from sortscope.steps import Event, get_steps

# Validated with the dataviz palette checker (light surface): every pair is
# distinguishable with normal vision; red/green is in the color-blind warning
# band, hence the extra outline on swapped/written bars.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
GRID = "#e1e0d9"
COLORS = {
    "default": "#c3c2b7",   # neutral gray: nothing is happening to this bar
    "compare": "#eda100",   # yellow
    "change": "#e34948",    # red: swapped or written this frame
    "pivot": "#6250d6",     # violet
    "final": "#1baf7a",     # green: known to be in its final position
}
LEGEND = [
    ("compare", "compared"),
    ("change", "swapped / written"),
    ("pivot", "pivot"),
    ("final", "final position"),
    ("default", "untouched"),
]

MAX_PANELS = 8
DEMOS = {
    # demo part 2: every algorithm on the same input, racing side by side
    "all": (names(), ["random"]),
    # demo part 3: same algorithm, how sortedness changes the work
    "insertion": (["insertion"], ["nearly_sorted", "reverse"]),
    "inputs": (["insertion"], input_kinds()),
    # demo part 4: same input, how the pivot rule changes the work
    "quick": (["quick_first", "quick_median3"], ["sorted"]),
}


@dataclass
class PanelState:
    """Everything one subplot needs: the array as shown, counters, highlights."""

    algo: str
    kind: str
    arr: list[int]
    seed: int = 0
    initial: list[int] = field(init=False)   # the unsorted input, kept for reset()
    events: list[Event] = field(init=False)
    pos: int = field(default=0, init=False)
    comparisons: int = field(default=0, init=False)
    swaps: int = field(default=0, init=False)
    writes: int = field(default=0, init=False)
    compared: set[int] = field(default_factory=set, init=False)
    changed: set[int] = field(default_factory=set, init=False)
    final: set[int] = field(default_factory=set, init=False)
    pivot: int = field(default=-1, init=False)

    def __post_init__(self) -> None:
        self.arr = list(self.arr)
        self.initial = list(self.arr)
        self.events = list(get_steps(self.algo, seed=self.seed)(self.arr))

    def reset(self) -> None:
        """Rewind to the original unsorted input: array, counters and highlights as at the start.

        ``events`` is kept: it was generated from ``initial`` with the same seed,
        so replaying it from position 0 repeats exactly the same sort.
        """
        self.arr[:] = self.initial
        self.pos = 0
        self.comparisons = self.swaps = self.writes = 0
        self.compared.clear()
        self.changed.clear()
        self.final.clear()
        self.pivot = -1

    @property
    def done(self) -> bool:
        """True once every event of this panel has been applied."""
        return self.pos >= len(self.events)

    def apply(self, ev: Event) -> None:
        """Apply one event to this panel's array, highlights and counters (see module docstring)."""
        kind = ev[0]
        if kind == "compare":
            self.compared.update((ev[1], ev[2]))
            self.comparisons += 1
        elif kind == "swap":
            i, j = ev[1], ev[2]
            self.arr[i], self.arr[j] = self.arr[j], self.arr[i]
            self.changed.update((i, j))
            self.swaps += 1
            self.writes += 2
        elif kind == "write":
            self.arr[ev[1]] = ev[2]
            self.changed.add(ev[1])
            self.writes += 1
        elif kind == "pivot":
            self.pivot = ev[1]
        elif kind == "sorted":
            self.final.add(ev[1])

    def advance(self, k: int) -> None:
        """One animation frame: forget last frame's highlights, apply k events."""
        self.compared.clear()
        self.changed.clear()
        for _ in range(k):
            if self.done:
                self.pivot = -1
                return
            self.apply(self.events[self.pos])
            self.pos += 1
        if self.done:
            self.pivot = -1

    def bar_style(self, i: int) -> tuple[str, float]:
        """(color, outline width) for bar i, using the priority order above."""
        if i in self.changed:
            return COLORS["change"], 1.6
        if i == self.pivot:
            return COLORS["pivot"], 0.0
        if i in self.compared:
            return COLORS["compare"], 0.0
        if i in self.final:
            return COLORS["final"], 0.0
        return COLORS["default"], 0.0

    def status_text(self) -> str:
        """The live counter line shown under the bars."""
        return (
            f"step {self.pos:>6,}/{len(self.events):,}   "
            f"comparisons {self.comparisons:>7,}   swaps {self.swaps:>6,}   writes {self.writes:>7,}"
        )


def make_panels(algos: list[str], kinds: list[str], n: int, seed: int,
                custom: list[int] | None = None) -> list[PanelState]:
    """Pair algorithms with inputs, one panel per pair.

    * several algorithms, one input  -> every algorithm on that same input
    * one algorithm, several inputs  -> that algorithm on every input
    * equal-length lists             -> zipped pairs (algos[i] on kinds[i])
    """
    if not algos or not kinds:
        raise ValueError("give at least one algorithm and one input type")
    if len(algos) > 1 and len(kinds) > 1:
        if len(algos) != len(kinds):
            raise ValueError("with several algorithms AND several inputs, give the same number of each")
        pairs = list(zip(algos, kinds))
    elif len(algos) > 1:
        pairs = [(a, kinds[0]) for a in algos]
    else:
        pairs = [(algos[0], k) for k in kinds]
    if len(pairs) > MAX_PANELS:
        raise ValueError(f"at most {MAX_PANELS} panels")
    panels = []
    for algo, kind in pairs:
        get_info(algo)  # validates the name
        arr = list(custom) if custom is not None else generate(kind, n, seed)
        panels.append(PanelState(algo, "custom" if custom is not None else kind, arr, seed))
    return panels


KEY_HINTS = "space: pause / resume    r: restart"
CONTROL_STRIP = 0.7   # inches under the plots for the buttons and sliders (window only)
RADIO_COLUMN = 1.9    # inches left of the plot for the radio buttons (single-panel window only)
N_SLIDER = (5, 200)
SPEED_SLIDER_MAX = 50  # events per frame


def build_animation(panels: list[PanelState], interval: int = 30, steps_per_frame: int = 1,
                    hold_frames: int = 25, interactive: bool = False):
    """Create the figure and FuncAnimation. Returns (fig, anim, update_fn).

    ``interactive=True`` (the on-screen window) adds the controls and the
    key-hint text; saved files use ``interactive=False``: a fixed number of
    frames, no widgets, no hints.

    Controls (keys and widgets call the same functions, exposed as ``fig.controls``):
        Start / Pause / Restart buttons; space = pause/resume, r = restart
        n slider      new input of that size             } these three load the new
        radio buttons algorithm and input type            } unsorted input and wait,
                      (only when there is one panel)      } paused, for Start
        speed slider  events applied per frame
    A change replaces the PanelState(s) inside ``panels`` (the list is edited in place).
    """
    import itertools
    from types import SimpleNamespace

    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation
    from matplotlib.patches import Patch

    # Layout: 1-2 panels in a row; more go into a grid of up to 4 columns.
    count = len(panels)
    ncols = count if count <= 2 else min(4, math.ceil(count / 2)) if count <= 8 else 4
    nrows = math.ceil(count / ncols)
    cell_w, cell_h = (6.5, 4.8) if count <= 2 else (4.6, 3.8)
    # The window is made a little bigger so the widgets do not shrink the plots.
    radios = interactive and count == 1
    strip = CONTROL_STRIP if interactive else 0.0
    side = RADIO_COLUMN if radios else 0.0
    width, height = cell_w * ncols + side, cell_h * nrows + 0.4 + strip
    fig, grid = plt.subplots(nrows, ncols, figsize=(width, height), squeeze=False)
    fig.patch.set_facecolor(SURFACE)
    axes = list(grid.flat)
    for ax in axes[count:]:   # unused grid cells
        ax.set_visible(False)
    axes = axes[:count]
    title_size = 11 if count <= 2 else 9.5

    def setup_axes(ax, p: PanelState):
        """(Re)build one subplot for panel p. Returns (bars, counter text, height offset)."""
        ax.clear()
        n = len(p.arr)
        # Heights are value - lo + 1 so the minimum is a short but visible bar
        # (and negative values work). Only relative height matters, so no y axis.
        lo = min(p.arr, default=0)
        span = max(p.arr, default=0) - lo + 1
        ax.set_facecolor(SURFACE)
        ax.set_ylim(0, span * 1.03)
        ax.set_xlim(-0.6, n - 0.4)
        ax.set_xticks([])
        ax.set_yticks([])
        for side_name in ("top", "right", "left"):
            ax.spines[side_name].set_visible(False)
        ax.spines["bottom"].set_color(GRID)
        ax.set_title(f"{get_info(p.algo).label}  ·  {p.kind.replace('_', ' ')}  ·  n={n}",
                     color=INK, fontsize=title_size, loc="left")
        width_ = 0.8 if n <= 60 else 0.95        # leave a visible gap between bars when possible
        bar_set = ax.bar(range(n), [v - lo + 1 for v in p.arr], width=width_,
                         color=COLORS["default"], edgecolor=INK, linewidth=0)
        # The live counters sit under the bars, in the x-label slot.
        text = ax.set_xlabel("", fontsize=8.5 if count <= 2 else 7, family="monospace", color=INK_SECONDARY)
        return bar_set, text, lo - 1

    bars, texts, offsets = (list(col) for col in zip(*(setup_axes(ax, p) for ax, p in zip(axes, panels))))
    fig.legend(handles=[Patch(facecolor=COLORS[k], label=label,
                              edgecolor=INK if k == "change" else "none", linewidth=1.2)
                        for k, label in LEGEND],
               loc="lower center", ncol=len(LEGEND), frameon=False, fontsize=9)
    # Bottom to top: legend, control strip, plots, and (window only) a thin strip for the key hints.
    legend_frac = 0.07 if nrows == 1 else 0.04
    top = 1 - 0.25 / height if interactive else 1
    fig.tight_layout(rect=(side / width, legend_frac + strip / height, 1, top))
    hint = fig.text(0.992, 0.992, KEY_HINTS, ha="right", va="top", fontsize=7.5,
                    color=INK_SECONDARY) if interactive else None
    paused = False
    n = len(panels[0].arr)                                               # what the n slider controls
    custom = panels[0].initial if panels[0].kind == "custom" else None   # the user-typed list, if any

    def draw() -> None:
        """Repaint every bar's height and color and every counter line."""
        for p, bar_set, text, off in zip(panels, bars, texts, offsets):
            for i, rect in enumerate(bar_set):
                rect.set_height(p.arr[i] - off)
                color, lw = p.bar_style(i)
                rect.set_facecolor(color)
                rect.set_linewidth(lw)
            text.set_text(p.status_text())
        if hint is not None:
            hint.set_text(f"PAUSED    {KEY_HINTS}" if paused else KEY_HINTS)

    def finished() -> bool:
        return all(p.done for p in panels)

    def update(frame: int):
        """FuncAnimation callback: advance each panel by steps_per_frame events, then redraw."""
        if paused:   # a timer tick that was already queued when pause was pressed
            return []
        settled = finished()                    # finished *before* this frame
        for p in panels:
            p.advance(steps_per_frame)
        draw()
        if interactive and settled:
            # Everything is sorted and the last highlights have been cleared:
            # stop the timer instead of redrawing an unchanging picture. Restart wakes it.
            anim.pause()
        return []

    # ---- control actions: the keys and the widgets both call these ----

    def set_paused(flag: bool) -> None:
        nonlocal paused
        paused = flag
        if flag:
            anim.pause()                        # stops the frame timer
        else:
            anim.resume()
        draw()
        fig.canvas.draw_idle()                  # the timer may be stopped, so repaint now

    def start() -> None:
        set_paused(False)

    def pause() -> None:
        if not finished():                      # nothing left to pause; Restart replays
            set_paused(True)

    def toggle() -> None:
        start() if paused else pause()

    def restart() -> None:
        """Rewind every panel to its original unsorted input and play (even if paused)."""
        for p in panels:
            p.reset()
        set_paused(False)

    def change(algo: str | None = None, kind: str | None = None, size: float | None = None) -> None:
        """A setting changed: build fresh panel(s), show the new unsorted input, wait for Start.

        ``algo``/``kind``/``size`` left as None keep the current value. A typed
        list (kind "custom") is used as it is, so the n slider does not affect it.
        """
        nonlocal n
        n = n if size is None else int(size)
        for i, old in enumerate(panels):
            new_kind = kind or old.kind
            arr = custom if new_kind == "custom" else generate(new_kind, n, old.seed)
            panels[i] = PanelState(algo or old.algo, new_kind, arr, old.seed)
            bars[i], texts[i], offsets[i] = setup_axes(axes[i], panels[i])
        set_paused(True)

    def set_speed(value: float) -> None:
        nonlocal steps_per_frame
        steps_per_frame = max(1, int(value))

    def on_key(event) -> None:
        key = (event.key or "").lower()
        if key in (" ", "space"):
            toggle()
        elif key == "r":
            restart()

    def add_widgets() -> SimpleNamespace:
        """Create the matplotlib widgets and connect each one to its action above."""
        from matplotlib.widgets import Button, RadioButtons, Slider

        def place(x: float, y: float, w: float, h: float):
            """A small axes for one widget; position and size in inches from the bottom-left corner."""
            return fig.add_axes((x / width, y / height, w / width, h / height), facecolor=SURFACE)

        w = SimpleNamespace()
        y = legend_frac * height + 0.2          # the control strip sits just above the legend
        for k, (label, action) in enumerate((("Start", start), ("Pause", pause), ("Restart", restart))):
            button = Button(place(0.2 + 0.9 * k, y, 0.8, 0.3), label, color=SURFACE, hovercolor=GRID)
            button.on_clicked(lambda event, action=action: action())
            setattr(w, label.lower(), button)
        w.n = Slider(place(3.2, y + 0.05, 1.5, 0.2), "n", *N_SLIDER, valinit=n, valstep=1,
                     color=INK_SECONDARY)
        w.n.on_changed(lambda value: change(size=value))
        w.speed = Slider(place(5.8, y + 0.05, 1.5, 0.2), "speed", 1, max(SPEED_SLIDER_MAX, steps_per_frame),
                         valinit=steps_per_frame, valstep=1, valfmt="%d / frame", color=INK_SECONDARY)
        w.speed.on_changed(set_speed)
        if radios:                              # one panel: let the user pick what it shows
            p = panels[0]
            kinds = input_kinds() + (["custom"] if custom is not None else [])
            w.algo = RadioButtons(place(0.15, height - 2.55, 1.6, 2.0), names(),
                                  active=names().index(p.algo), activecolor=INK)
            w.algo.on_clicked(lambda label: change(algo=label))
            w.kind = RadioButtons(place(0.15, height - 4.65, 1.6, 1.75), kinds,
                                  active=kinds.index(p.kind), activecolor=INK)
            w.kind.on_clicked(lambda label: change(kind=label))
            for radio, title in ((w.algo, "algorithm"), (w.kind, "input")):
                radio.ax.set_title(title, fontsize=9, color=INK_SECONDARY, loc="left")
                for side_name in radio.ax.spines:
                    radio.ax.spines[side_name].set_color(GRID)
                for text in radio.labels:
                    text.set_fontsize(8.5)
        return w

    draw()  # initial state
    if interactive:
        # Frames never run out, so the animation can be restarted any number of
        # times; update() stops the timer itself once every panel is sorted.
        frames = itertools.count
        fig.canvas.mpl_connect("key_press_event", on_key)
        # Kept on the figure for two reasons: matplotlib only holds weak references
        # to widgets (they stop responding if nothing else refers to them), and the
        # tests call these actions directly.
        fig.controls = SimpleNamespace(start=start, pause=pause, restart=restart, change=change,
                                       set_speed=set_speed, widgets=add_widgets())
    else:
        longest = max(len(p.events) for p in panels)
        frames = math.ceil(longest / steps_per_frame) + hold_frames  # hold the final picture
    anim = FuncAnimation(fig, update, frames=frames, interval=interval, repeat=False,
                         blit=False, cache_frame_data=False)
    return fig, anim, update


def check_save_target(path: str, allow_outside: bool = True) -> str:
    """Fail fast (before any rendering) if the animation can't or mustn't be written there.

    Checks the extension (.gif/.mp4), ffmpeg for .mp4, and — for the CLI, which passes
    ``allow_outside=False`` unless --allow-outside-results — that the file is under results/.
    Returns the resolved path.
    """
    from matplotlib import animation

    try:
        resolved = check_output_path(path, suffixes=(".gif", ".mp4"), allow_outside=allow_outside)
    except ValueError as e:
        raise SystemExit(f"error: --save: {e}") from None
    if resolved.suffix.lower() == ".mp4" and not animation.writers.is_available("ffmpeg"):
        raise SystemExit("saving .mp4 needs ffmpeg on your PATH (e.g. `winget install Gyan.FFmpeg`, "
                         "then open a new terminal); or save as .gif, which needs nothing extra")
    return str(resolved)


def save_animation(anim, path: str, interval: int) -> None:
    """Write ``anim`` as GIF (Pillow) or MP4 (ffmpeg) at 1000/interval frames per second."""
    from pathlib import Path

    from matplotlib import animation

    check_save_target(path)
    Path(path).parent.mkdir(parents=True, exist_ok=True)  # e.g. results/figures/ on a fresh checkout
    fps = max(1, round(1000 / interval))
    if path.lower().endswith(".gif"):
        writer = animation.PillowWriter(fps=fps)
    else:
        writer = animation.FFMpegWriter(fps=fps)
    anim.save(path, writer=writer)


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Register the `visualize` command's flags on ``parser`` (all validated at parse time)."""
    parser.add_argument("--algo", nargs="+", default=["insertion"], choices=names(), metavar="ALGO",
                        help=f"one or more of: {', '.join(names())}")
    parser.add_argument("--input", nargs="+", default=["random"], choices=input_kinds(), metavar="KIND",
                        help=f"one or more of: {', '.join(input_kinds())}")
    parser.add_argument("--demo", choices=sorted(DEMOS),
                        help="preset: all (every algorithm, same input) | insertion (nearly sorted vs reverse) | "
                             "inputs (insertion on all 5 inputs) | quick (first vs median-of-3 on sorted)")
    # All numeric flags and the typed list are validated by argparse at parse time, using the
    # shared rules in sortscope.validation, so a bad value never reaches the drawing code.
    parser.add_argument("--n", type=int_arg("--n", *VIS_N, hint="the visualizer is for small inputs; "
                                            "use `sortscope benchmark` for large n"),
                        default=30, help=f"number of bars ({VIS_N[0]}-{VIS_N[1]})")
    parser.add_argument("--seed", type=int_arg("--seed", *SEED), default=0)
    parser.add_argument("--list", dest="custom", type=_list_arg,
                        help=f'your own list, e.g. "5, 3, 9, 1" (at most {VIS_LIST_MAX} integers)')
    parser.add_argument("--interval", type=int_arg("--interval", *INTERVAL_MS), default=40,
                        help=f"milliseconds per frame ({INTERVAL_MS[0]}-{INTERVAL_MS[1]:,})")
    parser.add_argument("--steps-per-frame", type=int_arg("--steps-per-frame", *STEPS_PER_FRAME), default=1,
                        help=f"events applied per frame ({STEPS_PER_FRAME[0]}-{STEPS_PER_FRAME[1]:,})")
    parser.add_argument("--save", help="write a .gif or .mp4 (inside results/) instead of opening a window")
    parser.add_argument(ALLOW_OUTSIDE_FLAG, action="store_true", help="allow --save outside results/")


def _list_arg(text: str) -> list[int]:
    try:
        return parse_int_list(text, VIS_LIST_MAX)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from None


def run(args: argparse.Namespace) -> int:
    """`sortscope visualize`: build the panels, then show a window or save a GIF/MP4."""
    algos, kinds = (DEMOS[args.demo] if args.demo else (args.algo, args.input))
    custom = args.custom  # already a validated list of ints (or None)
    try:
        panels = make_panels(list(algos), list(kinds), args.n, args.seed, custom)
    except ValueError as e:  # e.g. 3 algorithms with 2 inputs, or more than MAX_PANELS panels
        raise SystemExit(f"error: {e}") from None

    if args.save:
        args.save = check_save_target(args.save, allow_outside=args.allow_outside_results)
        import matplotlib
        matplotlib.use("Agg")  # no window needed when writing a file
    import matplotlib.pyplot as plt

    if not args.save and "r" in plt.rcParams["keymap.home"]:
        # matplotlib's own "r" shortcut resets the zoom; here "r" means restart.
        plt.rcParams["keymap.home"].remove("r")
    fig, anim, _ = build_animation(panels, args.interval, args.steps_per_frame, interactive=not args.save)
    if args.save:
        try:
            save_animation(anim, args.save, args.interval)
        except OSError as e:  # read-only folder, path is a directory, disk full, ...
            raise SystemExit(f"error: cannot write {args.save}: {e.strerror or e}") from None
        print(f"saved {args.save}")
    else:
        plt.show()
    plt.close(fig)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Standalone entry point: ``python -m sortscope.visualizer``."""
    safe_console()
    parser = argparse.ArgumentParser(prog="sortscope.visualizer", description="Animate a sort.")
    add_arguments(parser)
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
