"""Custom widgets: the ringed-tail progress bar, the lemur logo, celebrations, and a scrolling frame."""

from __future__ import annotations

import math
import random
import time
import tkinter as tk
import tkinter.font as tkfont
from collections.abc import Callable
from tkinter import ttk

from .theme import (
    AMETHYST,
    AMETHYST_DEEP,
    BG,
    CRIMSON,
    FUR,
    FUR_LIGHT,
    GILT,
    GREY_PLASTIC,
    LAVENDER,
    LEMUR_EYE,
    PANEL,
    PARCHMENT,
    PARCHMENT_INK,
    PARCHMENT_MUTED,
    RING_BLACK,
    RING_WHITE,
    Fonts,
)

FRAME_MS = 33  # about 30 frames a second


def draw_star(canvas: tk.Canvas, cx: float, cy: float, r: float, fill: str, tags: str = "") -> int:
    """A four-pointed sparkle."""
    k = r * 0.3
    points = [cx, cy - r, cx + k, cy - k, cx + r, cy, cx + k, cy + k, cx, cy + r, cx - k, cy + k, cx - r, cy, cx - k, cy - k]
    return canvas.create_polygon(points, fill=fill, outline="", tags=tags)


def draw_bat(canvas: tk.Canvas, cx: float, cy: float, span: float, fill: str, tags: str = "") -> int:
    """A little bat silhouette, `span` wide."""
    outline = [
        (-1.0, -0.3), (-0.5, -0.1), (-0.15, -0.25), (-0.1, -0.45), (0.0, -0.3),
        (0.1, -0.45), (0.15, -0.25), (0.5, -0.1), (1.0, -0.3), (0.8, 0.05),
        (0.6, -0.02), (0.45, 0.2), (0.3, 0.08), (0.15, 0.3), (0.0, 0.4),
        (-0.15, 0.3), (-0.3, 0.08), (-0.45, 0.2), (-0.6, -0.02), (-0.8, 0.05),
    ]
    half = span / 2
    points = [c for x, y in outline for c in (cx + x * half, cy + y * half)]
    return canvas.create_polygon(points, fill=fill, outline="", tags=tags)


class TailProgress(tk.Canvas):
    """A progress bar drawn as a ring-tailed lemur's tail.

    Painted black and white rings fill in from the left over grey plastic,
    and the tail gets its black tip when the work is finished.

    With `sway` pixels of headroom above and below, `wag()` shakes the tail:
    the base stays put and the swing widens towards the tip.
    """

    TICK_MS = 16  # about 60 frames a second, so the wag looks fluid
    GROW_SECONDS = 0.66
    WAG_CYCLES = 20
    WAG_SECONDS = 10.0
    WAG_WAVES = 1.25  # how many ripples run down the tail at once
    WAG_SETTLE = 0.2  # the last fifth of the wag eases back to still

    def __init__(
        self, master: tk.Misc, height: int = 16, background: str = PANEL, width: int = 60, sway: int = 0, **kw
    ) -> None:
        # Request a small width and let pack/grid stretch it, so labels beside it keep their room.
        super().__init__(
            master, width=width, height=height + 2 * sway, background=background, highlightthickness=0, bd=0, **kw
        )
        self._height = height
        self._sway = sway
        self._value = 0.0
        self._shown = 0.0  # what's drawn; trails _value while growing
        # Both animations run off the clock, so a slow frame doesn't stretch them out.
        self._growth: tuple[float, float, float, Callable[[float], None] | None] | None = None
        self._wag_started: float | None = None
        self._wag_t: float | None = None  # how far through the wag (0.0 to 1.0), or None when still
        self._animation: str | None = None
        self.bind("<Configure>", lambda _e: self.redraw())
        self.bind("<Destroy>", lambda _e: self._stop_animation())

    def set(self, value: float) -> None:
        """Jump straight to `value`. A wag in progress carries on."""
        self._growth = None
        self._value = self._shown = min(1.0, max(0.0, value))
        if self._wag_t is None:
            self._stop_animation()
        self.redraw()

    def animate_from(self, start: float, on_frame: Callable[[float], None] | None = None) -> None:
        """Grow from `start` up to the current value, sparkling at the growing tip.

        `on_frame` is called each frame with how far through the growth it is (0.0 to 1.0).
        """
        self._growth = (min(1.0, max(0.0, start)), self._value, time.monotonic(), on_frame)
        self._run()

    def wag(self) -> None:
        """Shake the tail like a happy lemur: WAG_CYCLES swings over WAG_SECONDS."""
        if self._sway:
            self._wag_started, self._wag_t = time.monotonic(), 0.0
            self._run()

    def stop_wag(self) -> None:
        if self._wag_t is not None:
            self._wag_started = self._wag_t = None
            if self._growth is None:
                self._stop_animation()
            self.redraw()

    def _run(self) -> None:
        self._stop_animation()
        self._tick()

    def _tick(self) -> None:
        now = time.monotonic()
        sparkle = False
        if self._growth is not None:
            start, target, began, on_frame = self._growth
            done = min(1.0, (now - began) / self.GROW_SECONDS)
            eased = 1 - (1 - done) ** 3
            self._shown = start + (target - start) * eased
            sparkle = done < 1
            if on_frame:
                on_frame(eased)
            if done >= 1:
                self._growth = None
        if self._wag_started is not None:
            self._wag_t = (now - self._wag_started) / self.WAG_SECONDS
            if self._wag_t >= 1:
                self._wag_started = self._wag_t = None
        self.redraw(sparkle=sparkle)
        busy = self._growth is not None or self._wag_t is not None
        self._animation = self.after(self.TICK_MS, self._tick) if busy else None

    def _stop_animation(self) -> None:
        if self._animation is not None:
            self.after_cancel(self._animation)
            self._animation = None

    def _bend(self, u: float) -> float:
        """How far the tail is pushed up or down at `u` along it (0 at the base, 1 at the tip)."""
        t = self._wag_t
        if t is None:
            return 0.0
        settle = min(1.0, (1 - t) / self.WAG_SETTLE)
        u = min(1.0, max(0.0, u))
        # A wave ripples from the base to the tip, swinging wider the further along it gets.
        phase = 2 * math.pi * (self.WAG_CYCLES * t - self.WAG_WAVES * u)
        return self._sway * settle * u**1.2 * math.sin(phase)

    def redraw(self, sparkle: bool = False) -> None:
        self.delete("all")
        width = self.winfo_width()
        if width < self._height * 3:
            return
        top, bottom = 1 + self._sway, self._height - 1 + self._sway
        left, right = 1, width - 2
        d = bottom - top
        r = d / 2
        start, end = left + r, right - r
        bent = self._wag_t is not None

        def dy(x: float) -> float:
            return self._bend((x - start) / (end - start))

        def edge(x1: float, x2: float, y: float) -> list[float]:
            """Points along the tail from x1 to x2 at height y, following the bend."""
            steps = max(1, math.ceil(abs(x2 - x1) / 2))
            xs = [x1 + (x2 - x1) * k / steps for k in range(steps + 1)]
            return [c for x in xs for c in (x, y + dy(x))]

        def band(x1: float, x2: float, fill: str) -> None:
            if not bent:
                self.create_rectangle(x1, top, x2, bottom, fill=fill, outline="")
                return
            self.create_polygon(edge(x1, x2, top) + edge(x2, x1, bottom), fill=fill, outline="")

        tip = dy(end)

        self.create_oval(left, top, left + d, bottom, fill=GREY_PLASTIC, outline="")
        self.create_oval(right - d, top + tip, right, bottom + tip, fill=GREY_PLASTIC, outline="")
        band(start, end, GREY_PLASTIC)

        fill_to = start + (end - start) * self._shown
        if self._shown > 0:
            self.create_oval(left, top, left + d, bottom, fill=RING_BLACK, outline="")
            ring = max(4.0, d * 0.8)
            x, dark = start, False
            while x < fill_to:
                x2 = min(x + ring, fill_to)
                band(x, x2, RING_BLACK if dark else RING_WHITE)
                x, dark = x2, not dark
            if self._shown >= 1:
                band(right - d, end, RING_BLACK)
                self.create_oval(right - d, top + tip, right, bottom + tip, fill=RING_BLACK, outline="")

        # A gilt outline frames the tail.
        self.create_arc(left, top, left + d, bottom, start=90, extent=180, style=tk.ARC, outline=GILT)
        self.create_arc(right - d, top + tip, right, bottom + tip, start=270, extent=180, style=tk.ARC, outline=GILT)
        self.create_line(edge(start, end, top), fill=GILT)
        self.create_line(edge(start, end, bottom), fill=GILT)

        if sparkle:
            for _ in range(3):
                draw_star(
                    self,
                    fill_to + random.uniform(-d, d * 0.4),
                    (top + bottom) / 2 + dy(fill_to) + random.uniform(-r, r),
                    random.uniform(r * 0.4, r * 0.8),
                    random.choice((GILT, LAVENDER, RING_WHITE)),
                )


def _mirror(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return [(100 - x, y) for x, y in points]


def draw_lemur(canvas: tk.Canvas, x: float, y: float, size: float, tags: str = "") -> None:
    """A ring-tailed lemur face with its top-left corner at (x, y), drawn on a 100x100 grid."""
    scale = size / 100

    def xy(points: list[tuple[float, float]]) -> list[float]:
        return [c for px, py in points for c in (x + px * scale, y + py * scale)]

    def poly(points: list[tuple[float, float]], fill: str, smooth: bool = True) -> None:
        canvas.create_polygon(xy(points), fill=fill, outline="", smooth=smooth, tags=tags)

    def circle(cx: float, cy: float, r: float, fill: str) -> None:
        canvas.create_oval(xy([(cx - r, cy - r), (cx + r, cy + r)]), fill=fill, outline="", tags=tags)

    left_ear = [(14, 34), (20, 4), (44, 22)]
    inner_ear = [(20, 28), (23, 12), (36, 23)]
    for ear, colour in ((left_ear, FUR), (inner_ear, FUR_LIGHT)):
        poly(ear, colour, smooth=False)
        poly(_mirror(ear), colour, smooth=False)

    canvas.create_oval(xy([(10, 14), (90, 90)]), fill=FUR, outline="", tags=tags)
    poly([(50, 24), (78, 34), (80, 62), (60, 96), (40, 96), (20, 62), (22, 34)], RING_WHITE)

    eye_patch = [(20, 46), (34, 38), (47, 42), (46, 62), (34, 66), (24, 58)]
    poly(eye_patch, RING_BLACK)
    poly(_mirror(eye_patch), RING_BLACK)
    for cx in (35, 65):
        circle(cx, 51, 8, LEMUR_EYE)
        circle(cx, 51, 3.5, RING_BLACK)
        circle(cx + 2.5, 48.5, 1.6, RING_WHITE)

    poly([(46, 66), (54, 66), (57, 86), (50, 92), (43, 86)], RING_BLACK)
    circle(50, 86, 5, RING_BLACK)


def draw_ringed_tail(
    canvas: tk.Canvas,
    x: float,
    y: float,
    length: float,
    thickness: float,
    angle: float,
    curl: float,
    tags: str = "",
) -> None:
    """A black-and-white ringed tail rising from (x, y).

    `angle` is the direction at the base in radians; `curl` is how far it bends by the tip.
    """
    rings = 14
    step = length / rings
    for i in range(rings):
        along = i / (rings - 1)
        heading = angle + curl * along
        x += step * math.cos(heading)
        y -= step * math.sin(heading)
        r = thickness / 2 * (1 - 0.3 * along)
        white = i % 2 == 0 and i < rings - 1  # black tip, like the real thing
        canvas.create_oval(
            x - r,
            y - r,
            x + r,
            y + r,
            fill=RING_WHITE if white else RING_BLACK,
            outline=FUR if white else "",
            tags=tags,
        )


class LemurLogo(tk.Canvas):
    """The lemur face as a standalone widget."""

    def __init__(self, master: tk.Misc, size: int = 48, background: str = BG, **kw) -> None:
        super().__init__(
            master, width=size, height=size, background=background, highlightthickness=0, bd=0, **kw
        )
        draw_lemur(self, 0, 0, size)


def _ease_out_back(t: float) -> float:
    """0 to 1 with a little overshoot at the end, for a springy pop."""
    return 1 + 2.70158 * (t - 1) ** 3 + 1.70158 * (t - 1) ** 2


def _fit(font: tkfont.Font, text: str, width: float) -> str:
    """Shorten `text` with an ellipsis until it fits in `width` pixels."""
    if font.measure(text) <= width:
        return text
    while text and font.measure(text + "…") > width:
        text = text[:-1]
    return text.rstrip() + "…"


class Celebration(tk.Canvas):
    """A short lemur party on a gilt-edged parchment note: the lemur pops up, wags its
    ringed tail and throws confetti, and a few bats flutter off.

    Everything animates inside this one fixed canvas. It removes itself when
    it's finished, and a click sends it away early.
    """

    CONFETTI = [GILT, AMETHYST, LAVENDER, CRIMSON, RING_BLACK, FUR]
    # level: width, height, lemur size, frames on screen, frames that burst confetti, pieces per burst
    LEVELS = {
        "step": (410, 130, 64, 66, (6,), 26),
        "unit": (410, 130, 64, 84, (6, 22), 36),
        "commission": (560, 300, 110, 150, (6, 24, 42, 60, 78, 96), 50),
    }

    def __init__(
        self,
        master: tk.Misc,
        fonts: Fonts,
        level: str,
        headline: str,
        message: str,
        footnote: str,
        tally: str = "",
        on_close: Callable[[], None] | None = None,
    ) -> None:
        width, height, self._size, self._frames, self._bursts, self._pieces = self.LEVELS[level]
        super().__init__(
            master,
            width=width,
            height=height,
            background=PARCHMENT,
            highlightthickness=3,
            highlightbackground=GILT,
            bd=0,
            cursor="hand2",
        )
        self.level = level
        self._width, self._height = width, height
        self._big = level == "commission"
        self._on_close = on_close
        self._confetti: list[list] = []
        self._job: str | None = None

        if self._big:
            self._lemur_x, self._rest_y = (width - self._size) / 2 + 20, 24
            text_x, anchor, rows, room = width / 2, "center", (176, 214, 244, 272), width - 30
            text_fonts = (fonts.huge, fonts.card_title, fonts.body, fonts.bold)
        else:
            self._lemur_x, self._rest_y = 44, (height - self._size) / 2 + 4
            text_x, anchor, rows = 44 + self._size + 28, "w", (30, 60, 84, 106)
            room = width - text_x - 14
            text_fonts = (fonts.title, fonts.body, fonts.small, fonts.bold)
        # Words start 30px right and slide into place.
        for text, row, font, colour in zip(
            (headline, message, footnote, tally), rows, text_fonts, (AMETHYST_DEEP, PARCHMENT_INK, PARCHMENT_MUTED, AMETHYST)
        ):
            self.create_text(
                text_x + 30,
                row,
                text=_fit(font, text, room),
                font=font,
                fill=colour,
                anchor=anchor,
                state="hidden",
                tags="words",
            )
        self.bind("<Button-1>", lambda _e: self.close())
        self._tick(0)

    def close(self) -> None:
        if self._job is not None:
            self.after_cancel(self._job)
            self._job = None
        if self.winfo_exists():
            self.destroy()
        if self._on_close:
            self._on_close()

    def _lemur_y(self, i: int) -> float:
        hidden = self._height + 10
        pop, leave = 9, 10
        if i < pop:
            return hidden + (self._rest_y - hidden) * _ease_out_back(i / pop)
        if i >= self._frames - leave:
            t = (i - (self._frames - leave)) / leave
            return self._rest_y + (hidden - self._rest_y) * t * t
        return self._rest_y - abs(math.sin(i * 0.3)) * self._size * 0.08  # happy hopping

    def _draw_lemur(self, i: int) -> None:
        self.delete("lemur")
        y, size = self._lemur_y(i), self._size
        wag = 0.3 * math.sin(i * 0.4)
        # Out to the left and curling up over the top, like a question mark.
        draw_ringed_tail(
            self,
            self._lemur_x + size * 0.25,
            y + size * 0.85,
            size * 1.3,
            size * 0.22,
            angle=2.75 + wag,
            curl=-3.0,
            tags="lemur",
        )
        draw_lemur(self, self._lemur_x, y, size, tags="lemur")
        self.tag_raise("confetti")

    def _burst(self) -> None:
        if self._big:
            x, y = random.uniform(0.2, 0.8) * self._width, self._height * 0.3
        else:
            x, y = self._lemur_x + self._size / 2, self._rest_y + self._size * 0.2
        spread, rise = ((-6, 6), (-9, -4)) if self._big else ((-3, 7), (-7, -3))
        for _ in range(self._pieces):
            colour = random.choice(self.CONFETTI)
            px, py = x + random.uniform(-6, 6), y + random.uniform(-6, 6)
            shape = random.random()
            if shape < 0.12:
                # Bats flutter up and away instead of falling.
                item = draw_bat(self, px, py, random.uniform(12, 16), RING_BLACK, tags="confetti")
                self._confetti.append([item, random.uniform(-3, 3), random.uniform(-3, -1.5), -0.05])
                continue
            if shape < 0.3:
                item = draw_star(self, px, py, random.uniform(3, 5), colour, tags="confetti")
            elif shape < 0.6:
                r = random.uniform(2, 3.5)
                item = self.create_oval(px - r, py - r, px + r, py + r, fill=colour, outline="", tags="confetti")
            else:
                w, h = random.uniform(3, 7), random.uniform(2, 4)
                item = self.create_rectangle(px, py, px + w, py + h, fill=colour, outline="", tags="confetti")
            self._confetti.append([item, random.uniform(*spread), random.uniform(*rise), 0.5])

    def _move_confetti(self) -> None:
        kept = []
        for piece in self._confetti:
            item, vx, vy, gravity = piece
            self.move(item, vx, vy)
            piece[1], piece[2] = vx * 0.98, vy + gravity
            if not -30 < self.coords(item)[1] < self._height + 10:
                self.delete(item)
            else:
                kept.append(piece)
        self._confetti = kept

    def _tick(self, i: int) -> None:
        if i >= self._frames:
            self.close()
            return
        self._draw_lemur(i)
        if i in self._bursts:
            self._burst()
        self._move_confetti()
        if i == 3:
            self.itemconfigure("words", state="normal")
        if 3 <= i < 9:
            self.move("words", -5, 0)
        self._job = self.after(FRAME_MS, self._tick, i + 1)


class ScrollableFrame(ttk.Frame):
    """A vertically scrolling container; put children in `.inner`."""

    def __init__(self, master: tk.Misc, background: str = BG, **kw) -> None:
        super().__init__(master, **kw)
        self.canvas = tk.Canvas(
            self, background=background, highlightthickness=0, bd=0, yscrollincrement=20
        )
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, background=background)
        window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.inner.bind(
            "<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(window, width=e.width))
        # Wheel events go to the widget under the pointer (a card, a label...),
        # so listen globally and only scroll when the pointer is over this frame.
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_all(sequence, self._on_wheel, add="+")

    def _on_wheel(self, event: tk.Event) -> None:
        widget = self.winfo_containing(event.x_root, event.y_root)
        if widget is None or not (widget is self or str(widget).startswith(f"{self}.")):
            return
        if self.canvas.yview() == (0.0, 1.0):
            return
        if event.num == 4:
            step = -1
        elif event.num == 5:
            step = 1
        else:
            step = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(step * 3, "units")
