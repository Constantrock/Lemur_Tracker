"""Main window: the troop of commissions on the left, the selected plan on the right."""

from __future__ import annotations

import random
import sys
import tkinter as tk
from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from tkinter import messagebox, ttk

from . import __version__
from .dialogs import ProjectDialog, StepsDialog, UnitDialog
from .models import (
    BUILD_STEP,
    DEFAULT_PAINT_STEPS,
    DONE,
    Project,
    Unit,
    all_steps,
    change_paint_steps,
    paint_steps,
    phase_of,
    set_paint_steps,
    step_destinations,
)
from .rewards import SoundPlayer, cheer, headline_for
from .storage import (
    default_data_path,
    load_data,
    load_settings,
    quarantine,
    save_data,
    save_settings,
    settings_path,
)
from .theme import (
    AMETHYST,
    BG,
    BORDER,
    EMPTY_STEP,
    FOREST,
    GILT,
    GILT_DIM,
    INK,
    LEMUR_FACTS,
    PANEL,
    PHASE_TINT,
    SELECTED,
    TEXT,
    TEXT_MUTED,
    apply_styles,
    use_dark_title_bar,
)
from .widgets import Celebration, LemurLogo, ScrollableFrame, TailProgress

FACT_INTERVAL_MS = 45_000
MESSAGE_MS = 6_000


def format_date(d: date) -> str:
    return f"{d.day} {d:%b %Y}"


def describe_age(days: int) -> str:
    if days == 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days > 1:
        return f"{days} days ago"
    return "tomorrow" if days == -1 else f"in {-days} days"


def plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def step_summary(project: Project) -> str:
    """Where the models are, e.g. '20 at Prime · 11 at Metallics · 12 done'."""
    if not project.units:
        return "No units yet"
    parts = []
    for step, n in project.step_counts().items():
        if n == 0:
            continue
        if step == DONE:
            parts.append(f"{n} done")
        elif step == BUILD_STEP:
            parts.append(f"{n} to build")
        else:
            parts.append(f"{n} at {step}")
    return " · ".join(parts)


def detail_summary(project: Project) -> str:
    counts = project.detail_counts()
    return " · ".join(f"{n} {level.value}" for level, n in counts.items() if n) or "—"


def effects_summary(project: Project) -> str:
    counts = Counter(effect for unit in project.units for effect in unit.effects)
    return ", ".join(name if n == 1 else f"{name} ×{n}" for name, n in counts.items()) or "None yet"


class LemurTrackerApp:
    def __init__(self, root: tk.Tk, data_path: Path) -> None:
        self.root = root
        self.data_path = data_path
        self.fonts = apply_styles(root)
        self.projects: list[Project] = []
        self.selected_id: str | None = None
        self.search_var = tk.StringVar()
        self.show_delivered_var = tk.BooleanVar(value=False)
        self._facts = random.sample(LEMUR_FACTS, len(LEMUR_FACTS))
        self._fact_index = 0
        self._status_job: str | None = None
        self._settings_path = settings_path(data_path)
        self.sound = SoundPlayer(enabled=load_settings(self._settings_path)["sound"])
        self.sound_var = tk.BooleanVar(value=self.sound.enabled)
        self._celebration: Celebration | None = None
        self._steps_this_session = 0
        self._wagging: str | None = None  # id of the commission whose tail is wagging

        root.title("Lemur Tracker")
        root.geometry("1280x800")
        root.minsize(980, 620)

        self._load()  # first, so the step strip is built from the saved steps
        self._build_menu()
        self._build_header()
        self._build_statusbar()
        self._build_body()

        self.search_var.trace_add("write", lambda *_: self.refresh())
        self.refresh()
        self._next_fact()

    # ----- persistence -------------------------------------------------

    def _load(self) -> None:
        try:
            self.projects, steps = load_data(self.data_path)
        except (ValueError, KeyError, TypeError) as exc:
            moved = quarantine(self.data_path)
            messagebox.showwarning(
                "The troop got muddled",
                f"Lemur Tracker couldn't read its saved commissions ({exc}).\n\n"
                f"The file has been kept safe at:\n{moved}\n\n"
                "Starting with an empty troop.",
                parent=self.root,
            )
            self.projects, steps = [], list(DEFAULT_PAINT_STEPS)
        set_paint_steps(steps)

    def _save(self) -> None:
        try:
            save_data(self.data_path, self.projects, paint_steps())
        except OSError as exc:
            messagebox.showerror(
                "Couldn't save",
                f"Lemur Tracker couldn't save your commissions:\n{exc}\n\n"
                "Your latest change is still on screen. Try again before closing.",
                parent=self.root,
            )

    @contextmanager
    def _changing(self, project: Project) -> Iterator[None]:
        """Wrap a change to `project`: save, redraw, and throw a party if it just finished."""
        was_complete = project.is_complete
        yield
        self._save()
        self.refresh()
        if project.is_complete and not was_complete:
            self._wag_tail(project)
            self.sound.play_commission_done()
            self._celebrate(
                "commission",
                "Tail complete!",
                project.name,
                "Every ring is painted. Time for a victory sunbathe.",
            )

    # ----- layout ------------------------------------------------------

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="New commission…", accelerator="Ctrl+N", command=self.new_project)
        file_menu.add_command(label="Painting steps…", command=self.edit_steps)
        file_menu.add_separator()
        file_menu.add_command(label="Quit", accelerator="Ctrl+Q", command=self.root.destroy)
        menubar.add_cascade(label="File", menu=file_menu)
        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="About Lemur Tracker", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.root.configure(menu=menubar)
        self.root.bind("<Control-n>", lambda _e: self.new_project())
        self.root.bind("<Control-q>", lambda _e: self.root.destroy())

    def _build_header(self) -> None:
        header = tk.Frame(self.root, background=INK, padx=18, pady=12)
        header.pack(side="top", fill="x")
        # A gilt hairline under the header, like a rule in an old ledger.
        tk.Frame(self.root, background=GILT_DIM, height=1).pack(side="top", fill="x")
        logo = LemurLogo(header, size=52, background=INK, cursor="hand2")
        logo.pack(side="left")
        logo.bind("<Button-1>", lambda _e: self._next_fact())
        titles = tk.Frame(header, background=INK)
        titles.pack(side="left", padx=(12, 0))
        tk.Label(titles, text="Lemur Tracker", font=self.fonts.app_title, bg=INK, fg=GILT).pack(anchor="w")
        tk.Label(
            titles,
            text="Painting commissions, one ring at a time",
            font=self.fonts.subtitle,
            bg=INK,
            fg=TEXT_MUTED,
        ).pack(anchor="w")
        ttk.Button(header, text="+  New commission", style="Accent.TButton", command=self.new_project).pack(
            side="right"
        )
        ttk.Checkbutton(
            header,
            text="Sound effects",
            variable=self.sound_var,
            command=self._toggle_sound,
            style="Header.TCheckbutton",
        ).pack(side="right", padx=(0, 20))

    def _build_statusbar(self) -> None:
        self.status = ttk.Label(self.root, style="Status.TLabel", anchor="w", cursor="hand2")
        self.status.pack(side="bottom", fill="x")
        self.status.bind("<Button-1>", lambda _e: self._next_fact())

    def _build_body(self) -> None:
        panes = ttk.PanedWindow(self.root, orient="horizontal")
        panes.pack(fill="both", expand=True)
        left = ttk.Frame(panes, padding=(14, 14, 8, 14))
        right = ttk.Frame(panes, padding=(8, 14, 14, 14))
        panes.add(left, weight=0)
        panes.add(right, weight=1)
        self._build_list(left)
        self._build_detail(right)

    def _build_list(self, parent: ttk.Frame) -> None:
        top = ttk.Frame(parent)
        top.pack(fill="x")
        ttk.Label(top, text="Your troop", style="Heading.TLabel").pack(side="left")
        self.count_label = ttk.Label(top, foreground=TEXT_MUTED, font=self.fonts.small)
        self.count_label.pack(side="left", padx=(10, 0), pady=(8, 0))

        filters = ttk.Frame(parent)
        filters.pack(fill="x", pady=(8, 10))
        ttk.Label(filters, text="Search").pack(side="left")
        ttk.Entry(filters, textvariable=self.search_var, width=16).pack(
            side="left", fill="x", expand=True, padx=(6, 10)
        )
        ttk.Checkbutton(
            filters, text="Show delivered", variable=self.show_delivered_var, command=self.refresh
        ).pack(side="right")

        self.card_list = ScrollableFrame(parent)
        self.card_list.canvas.configure(width=340)
        self.card_list.pack(fill="both", expand=True)

    def _build_detail(self, parent: ttk.Frame) -> None:
        container = tk.Frame(parent, background=PANEL, highlightthickness=1, highlightbackground=BORDER)
        container.pack(fill="both", expand=True)
        self.detail_container = container
        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)
        self.empty_view = self._build_empty_view(container)
        self.detail_view = self._build_detail_view(container)
        for view in (self.empty_view, self.detail_view):
            view.grid(row=0, column=0, sticky="nsew")

    def _build_empty_view(self, parent: tk.Misc) -> ttk.Frame:
        frame = ttk.Frame(parent, style="Panel.TFrame")
        centre = ttk.Frame(frame, style="Panel.TFrame")
        centre.place(relx=0.5, rely=0.42, anchor="center")
        LemurLogo(centre, size=120, background=PANEL).pack()
        self.empty_title = ttk.Label(centre, style="Title.TLabel")
        self.empty_title.pack(pady=(16, 4))
        self.empty_text = ttk.Label(centre, style="Muted.TLabel", justify="center", wraplength=420)
        self.empty_text.pack()
        self.empty_button = ttk.Button(
            centre, text="+  New commission", style="Accent.TButton", command=self.new_project
        )
        return frame

    def _build_detail_view(self, parent: tk.Misc) -> ttk.Frame:
        frame = ttk.Frame(parent, style="Panel.TFrame", padding=20)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(5, weight=1)

        top = ttk.Frame(frame, style="Panel.TFrame")
        top.grid(row=0, column=0, sticky="ew")
        self.d_name = ttk.Label(top, style="Title.TLabel")
        self.d_name.pack(side="left")
        ttk.Button(top, text="Delete", command=self.delete_project).pack(side="right")
        self.deliver_button = ttk.Button(top, command=self.toggle_delivered, width=18)
        self.deliver_button.pack(side="right", padx=(0, 8))
        ttk.Button(top, text="Edit details", command=self.edit_project).pack(side="right", padx=(0, 8))

        progress = ttk.Frame(frame, style="Panel.TFrame")
        progress.grid(row=1, column=0, sticky="ew")  # the tail's sway gives it room above and below
        self.d_tail = TailProgress(progress, height=24, background=PANEL, sway=16)
        self.d_tail.pack(side="left", fill="x", expand=True)
        self.d_percent = ttk.Label(progress, style="Title.TLabel", width=5, anchor="e")
        self.d_percent.pack(side="right", padx=(12, 0))

        pipeline = ttk.Frame(frame, style="Panel.TFrame")
        pipeline.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        caption = ttk.Frame(pipeline, style="Panel.TFrame")
        caption.pack(fill="x", pady=(0, 3))
        ttk.Label(caption, text="Models on each step", style="Muted.TLabel", font=self.fonts.small).pack(side="left")
        ttk.Button(caption, text="Edit steps", style="Link.TButton", command=self.edit_steps).pack(side="right")
        self.d_pipeline = pipeline
        self.d_cells: tk.Frame | None = None
        self.d_steps: dict[str, tuple[tk.Frame, tk.Label, tk.Label]] = {}
        self._build_step_cells()

        info = ttk.Frame(frame, style="Panel.TFrame")
        info.grid(row=3, column=0, sticky="ew", pady=(16, 0))
        info.columnconfigure(1, weight=1, uniform="values")
        info.columnconfigure(3, weight=1, uniform="values")
        self._info_wrap = 0
        info.bind("<Configure>", self._wrap_info)
        self.d_fields: dict[str, ttk.Label] = {}
        for col, keys in ((0, ["Client", "Address", "Notes"]), (2, ["Accepted", "Models", "Detail", "Effects"])):
            for row, key in enumerate(keys):
                ttk.Label(info, text=key, style="Muted.TLabel").grid(
                    row=row, column=col, sticky="nw", padx=(0, 12), pady=2
                )
                value = ttk.Label(info, style="Panel.TLabel", justify="left")
                value.grid(row=row, column=col + 1, sticky="nw", padx=(0, 24), pady=2)
                self.d_fields[key] = value

        bar = ttk.Frame(frame, style="Panel.TFrame")
        bar.grid(row=4, column=0, sticky="ew", pady=(18, 6))
        # The bar and table move whenever the info above changes height.
        bar.bind("<Configure>", lambda _e: self._repaint_detail())
        ttk.Label(bar, text="Units", style="Section.TLabel").pack(side="left")
        ttk.Button(bar, text="+ Add unit", command=self.add_unit).pack(side="left", padx=(12, 0))
        remove = ttk.Button(bar, text="Remove", command=self.remove_units)
        edit = ttk.Button(bar, text="Edit", command=self.edit_unit)
        self.back_button = ttk.Button(bar, text="Step back", command=self.step_back)
        self.next_button = ttk.Button(bar, text="Next step", style="Accent.TButton", command=self.next_step)
        for button in (remove, edit, self.back_button, self.next_button):
            button.pack(side="right", padx=(8, 0))
        self.unit_buttons = [remove, edit, self.back_button, self.next_button]

        tree_frame = ttk.Frame(frame, style="Panel.TFrame")
        tree_frame.grid(row=5, column=0, sticky="nsew")
        # Size the fixed-content columns from the font so they fit on any platform.
        heading, cell, pad = self.fonts.bold.measure, self.fonts.body.measure, 28
        columns = {
            "name": ("Unit", 150, "w"),
            "type": ("Type", 90, "w"),
            "models": ("Models", heading("Models") + pad, "center"),
            "detail": ("Detail level", cell("●●○  Battle Ready") + pad, "w"),
            "effects": ("Effects", 140, "w"),
            "step": ("Current step", cell("Details & effects  ·  9/9") + pad, "w"),
        }
        self.tree = ttk.Treeview(tree_frame, columns=list(columns), show="headings", selectmode="extended")
        for col, (text, width, anchor) in columns.items():
            self.tree.heading(col, text=text, anchor=anchor)
            self.tree.column(col, width=width, minwidth=50, anchor=anchor, stretch=col in ("name", "effects"))
        for phase, tint in PHASE_TINT.items():
            self.tree.tag_configure(phase, background=tint)
        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._sync_unit_buttons())
        self.tree.bind("<Delete>", lambda _e: self.remove_units())
        self.tree_empty = ttk.Label(
            self.tree,
            text="No units yet. Add the HQ, squads and vehicles in this commission.",
            style="Muted.TLabel",
        )
        return frame

    def _wrap_info(self, event: tk.Event) -> None:
        # Each value column gets half the row, less its key label and padding.
        wrap = max(160, event.width // 2 - 110)
        if wrap == self._info_wrap:
            return
        self._info_wrap = wrap
        for label in self.d_fields.values():
            label.configure(wraplength=wrap)

    def _repaint_detail(self) -> None:
        """Repaint the whole detail view after widgets in it have moved.

        Some X servers (seen on XWayland) leave stale pixels on moved widgets.
        Re-stacking the two views makes the server re-expose every widget.
        """
        if self.selected_project is not None and self.root.tk.call("tk", "windowingsystem") == "x11":
            self.empty_view.tkraise()
            self.detail_view.tkraise()

    def _build_step_cells(self) -> None:
        """(Re)build the 'Models on each step' strip for the current step list."""
        if self.d_cells is not None:
            self.d_cells.destroy()
        self.d_cells = cells = tk.Frame(self.d_pipeline, background=PANEL)
        cells.pack(fill="x")
        self.d_steps = {}
        for col, step in enumerate(all_steps()):
            cells.columnconfigure(col, weight=1, uniform="steps")
            cell = tk.Frame(cells, padx=4, pady=3)
            cell.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 3, 0))
            # Count packed at the bottom so counts line up even when a step name wraps.
            count = tk.Label(cell, font=self.fonts.bold)
            count.pack(side="bottom")
            name = tk.Label(cell, text=step, font=self.fonts.small, justify="center")
            name.pack(side="top")
            self.d_steps[step] = (cell, name, count)
        cells.bind("<Configure>", self._wrap_step_names)

    def _wrap_step_names(self, event: tk.Event) -> None:
        wrap = max(40, event.width // len(self.d_steps) - 12)
        for _cell, name, _count in self.d_steps.values():
            name.configure(wraplength=wrap)

    # ----- drawing -----------------------------------------------------

    @property
    def selected_project(self) -> Project | None:
        return next((p for p in self.projects if p.id == self.selected_id), None)

    def _visible_projects(self) -> list[Project]:
        query = self.search_var.get().strip().casefold()
        show_delivered = self.show_delivered_var.get()
        visible = [
            p
            for p in self.projects
            if (show_delivered or not p.delivered)
            and (not query or query in p.name.casefold() or query in p.client_name.casefold())
        ]
        # Oldest commission first: whoever has waited longest is at the top.
        return sorted(visible, key=lambda p: (p.delivered, p.accepted_on, p.name.casefold()))

    def refresh(self) -> None:
        visible = self._visible_projects()
        if self.selected_project is None and visible:
            self.selected_id = visible[0].id
        self._refresh_cards(visible)
        self._refresh_detail()

    def select_project(self, project_id: str) -> None:
        self.selected_id = project_id
        # Redraw after the click finishes, since the clicked card gets rebuilt.
        self.root.after_idle(self.refresh)

    def _refresh_cards(self, visible: list[Project]) -> None:
        inner = self.card_list.inner
        for child in inner.winfo_children():
            child.destroy()
        active = sum(not p.delivered for p in self.projects)
        self.count_label.configure(text=f"{active} active · {len(self.projects) - active} delivered")

        if not visible:
            if not self.projects:
                text = "No commissions yet.\nThe troop is out sunbathing. Add a commission to put them to work."
            elif self.search_var.get().strip():
                text = f"No commissions match “{self.search_var.get().strip()}”."
            else:
                text = "Every commission has been delivered.\nTick “Show delivered” to see them."
            tk.Label(inner, text=text, bg=BG, fg=TEXT_MUTED, justify="center", wraplength=300, pady=30).pack(
                fill="x"
            )
            return
        for project in visible:
            self._make_card(inner, project).pack(fill="x", padx=(0, 6), pady=(0, 10))

    def _make_card(self, parent: tk.Misc, project: Project) -> tk.Frame:
        selected = project.id == self.selected_id
        bg = SELECTED if selected else PANEL
        card = tk.Frame(
            parent,
            background=bg,
            highlightthickness=2,
            highlightbackground=AMETHYST if selected else BORDER,
            padx=12,
            pady=10,
            cursor="hand2",
        )
        head = tk.Frame(card, background=bg)
        head.pack(fill="x")
        tk.Label(
            head, text=project.name, font=self.fonts.card_title, bg=bg, fg=TEXT, anchor="w", justify="left",
            wraplength=250,
        ).pack(side="left", fill="x", expand=True)
        if project.delivered:
            badge = ("Delivered", FOREST, TEXT)
        elif project.is_complete:
            badge = ("Ready to ship", GILT, INK)
        else:
            badge = None
        if badge:
            text, badge_bg, badge_fg = badge
            tk.Label(head, text=text, font=self.fonts.small, bg=badge_bg, fg=badge_fg, padx=6).pack(
                side="right", anchor="n"
            )

        client = project.client_name or "No client yet"
        tk.Label(
            card,
            text=f"{client} · accepted {describe_age(project.days_since_accepted())}",
            font=self.fonts.small,
            bg=bg,
            fg=TEXT_MUTED,
            anchor="w",
        ).pack(fill="x", pady=(2, 8))

        bar = tk.Frame(card, background=bg)
        bar.pack(fill="x")
        tail = TailProgress(bar, height=14, background=bg)
        tail.pack(side="left", fill="x", expand=True)
        tail.set(project.progress)
        tk.Label(bar, text=f"{project.percent}%", font=self.fonts.bold, bg=bg, fg=TEXT, width=5, anchor="e").pack(
            side="right"
        )

        tk.Label(
            card,
            text=step_summary(project),
            font=self.fonts.small,
            bg=bg,
            fg=TEXT,
            anchor="w",
            justify="left",
            wraplength=290,
        ).pack(fill="x", pady=(6, 0))

        def bind_click(widget: tk.Misc) -> None:
            widget.bind("<Button-1>", lambda _e: self.select_project(project.id))
            for child in widget.winfo_children():
                bind_click(child)

        bind_click(card)
        return card

    def _refresh_detail(self) -> None:
        project = self.selected_project
        if project is None or project.id != self._wagging:
            self._wagging = None
            self.d_tail.stop_wag()
        if project is None:
            self._show_empty()
            return
        self.detail_view.tkraise()
        self.d_name.configure(text=project.name)
        self.deliver_button.configure(text="Mark not delivered" if project.delivered else "Mark delivered")

        fields = self.d_fields
        fields["Client"].configure(text=project.client_name or "—")
        fields["Address"].configure(text=project.client_address or "—")
        fields["Notes"].configure(text=project.notes or "—")
        fields["Accepted"].configure(
            text=f"{format_date(project.accepted_on)} ({describe_age(project.days_since_accepted())})"
        )
        fields["Models"].configure(
            text=f"{plural(project.model_count, 'model')} in {plural(len(project.units), 'unit')}"
        )
        fields["Detail"].configure(text=detail_summary(project))
        fields["Effects"].configure(text=effects_summary(project))

        self.d_tail.set(project.progress)
        self.d_percent.configure(text=f"{project.percent}%")
        self._paint_steps()

        keep = set(self.tree.selection())
        self.tree.delete(*self.tree.get_children())
        for unit in project.units:
            step = "Done ✓" if unit.is_done else f"{unit.current_step}  ·  {unit.steps_done}/{len(unit.steps)}"
            self.tree.insert(
                "",
                "end",
                iid=unit.id,
                values=(
                    unit.name,
                    unit.unit_type,
                    unit.model_count,
                    f"{unit.detail_level.pips}  {unit.detail_level.value}",
                    ", ".join(unit.effects),
                    step,
                ),
                tags=(unit.phase,),
            )
        reselect = [u.id for u in project.units if u.id in keep]
        if reselect:
            self.tree.selection_set(reselect)
        if project.units:
            self.tree_empty.place_forget()
        else:
            self.tree_empty.place(relx=0.5, rely=0.35, anchor="center")
        self._sync_unit_buttons()

    def _paint_steps(self) -> None:
        """Colour the 'Models on each step' strip for the selected commission."""
        project = self.selected_project
        if project is None:
            return
        counts = project.step_counts()
        for step, (cell, name, count) in self.d_steps.items():
            models = counts[step]
            bg = PHASE_TINT[phase_of(step)] if models else EMPTY_STEP
            fg = TEXT if models else TEXT_MUTED
            for widget in (cell, name, count):
                widget.configure(bg=bg)
            name.configure(fg=fg)
            count.configure(text=str(models) if models else "–", fg=fg)

    def _show_empty(self) -> None:
        self.empty_view.tkraise()
        if self.projects:
            self.empty_title.configure(text="Pick a commission")
            self.empty_text.configure(text="Choose one from the troop on the left to see its plan.")
            self.empty_button.pack_forget()
        else:
            self.empty_title.configure(text="Welcome to Lemur Tracker")
            self.empty_text.configure(
                text="Add your first commission and watch its tail fill with rings "
                "as each unit moves through its painting steps."
            )
            self.empty_button.pack(pady=(16, 0))

    def _sync_unit_buttons(self) -> None:
        units = self._selected_units()
        for button in self.unit_buttons:
            button.state(["!disabled"] if units else ["disabled"])
        if units and all(u.is_done for u in units):
            self.next_button.state(["disabled"])
        if units and all(u.steps_done == 0 for u in units):
            self.back_button.state(["disabled"])

    # ----- status bar --------------------------------------------------

    def _next_fact(self) -> None:
        fact = self._facts[self._fact_index % len(self._facts)]
        self._fact_index += 1
        self._set_status(f"Lemur fact: {fact}", FACT_INTERVAL_MS)

    def _say(self, message: str) -> None:
        """Show a message in the status bar for a few seconds, then go back to lemur facts."""
        self._set_status(message, MESSAGE_MS)

    def _set_status(self, text: str, duration_ms: int) -> None:
        if self._status_job is not None:
            self.root.after_cancel(self._status_job)
        self.status.configure(text=text)
        self._status_job = self.root.after(duration_ms, self._next_fact)

    # ----- commission actions -------------------------------------------

    def new_project(self) -> None:
        values = ProjectDialog(self.root, self.fonts).show()
        if values is None:
            return
        project = Project(**values)
        self.projects.append(project)
        self.selected_id = project.id
        self._save()
        self.refresh()
        self._say(f"“{project.name}” joined the troop. Add its units next.")

    def edit_project(self) -> None:
        project = self.selected_project
        if project is None:
            return
        values = ProjectDialog(self.root, self.fonts, project).show()
        if values is None:
            return
        with self._changing(project):
            for key, value in values.items():
                setattr(project, key, value)

    def delete_project(self) -> None:
        project = self.selected_project
        if project is None:
            return
        if not messagebox.askyesno(
            "Shoo this commission away?",
            f"Delete “{project.name}” and its {plural(len(project.units), 'unit')}?\n\nThis can't be undone.",
            icon="warning",
            parent=self.root,
        ):
            return
        self.projects = [p for p in self.projects if p.id != project.id]
        self.selected_id = None
        self._save()
        self.refresh()
        self._say(f"“{project.name}” was deleted.")

    def toggle_delivered(self) -> None:
        project = self.selected_project
        if project is None:
            return
        if not project.delivered and not project.is_complete:
            if not messagebox.askyesno(
                "Not finished yet",
                f"“{project.name}” still has unfinished units. Mark it delivered anyway?",
                parent=self.root,
            ):
                return
        with self._changing(project):
            project.delivered = not project.delivered
        if project.delivered:
            self._wag_tail(project)
            hidden = "" if self.show_delivered_var.get() else " It's tucked out of the list; tick “Show delivered” to see it."
            self._say(f"“{project.name}” delivered. Nice work!{hidden}")

    # ----- unit actions -------------------------------------------------

    def _selected_units(self) -> list[Unit]:
        project = self.selected_project
        if project is None:
            return []
        selection = set(self.tree.selection())
        return [u for u in project.units if u.id in selection]

    def add_unit(self) -> None:
        project = self.selected_project
        if project is None:
            return
        values = UnitDialog(self.root, self.fonts).show()
        if values is None:
            return
        unit = Unit(**values)
        with self._changing(project):
            project.units.append(unit)
        self.tree.selection_set(unit.id)
        self.tree.see(unit.id)

    def edit_unit(self) -> None:
        project, units = self.selected_project, self._selected_units()
        if project is None or not units:
            return
        unit = units[0]
        values = UnitDialog(self.root, self.fonts, unit).show()
        if values is None:
            return
        with self._changing(project):
            for key, value in values.items():
                setattr(unit, key, value)

    def remove_units(self) -> None:
        project, units = self.selected_project, self._selected_units()
        if project is None or not units:
            return
        what = f"“{units[0].name}”" if len(units) == 1 else plural(len(units), "unit")
        if not messagebox.askyesno("Remove units?", f"Remove {what} from “{project.name}”?", parent=self.root):
            return
        removed = {u.id for u in units}
        with self._changing(project):
            project.units = [u for u in project.units if u.id not in removed]

    def next_step(self) -> None:
        self._move_units(Unit.advance, forward=True)

    def step_back(self) -> None:
        self._move_units(Unit.step_back, forward=False)

    def _move_units(self, move: Callable[[Unit], None], forward: bool) -> None:
        """Move each selected unit one step, all its models together."""
        project, units = self.selected_project, self._selected_units()
        if project is None or not units:
            return
        before = {u.id: u.current_step for u in units}
        old_progress, old_percent = project.progress, project.percent
        with self._changing(project):
            for unit in units:
                move(unit)
        moved = [u for u in units if u.current_step != before[u.id]]
        if not moved:
            return
        steps = {u.current_step for u in moved}
        if steps == {DONE}:
            where = "finished"
        elif len(steps) == 1:
            where = f"on {steps.pop()}"
        else:
            where = "on their next steps"
        if len(moved) == 1:
            self._say(f"“{moved[0].name}” is now {where}.")
        else:
            self._say(f"{plural(len(moved), 'unit')} are now {where}.")
        if forward:
            self._reward(project, moved, before, old_progress, old_percent)

    # ----- rewards --------------------------------------------------------

    def _reward(
        self, project: Project, moved: list[Unit], before: dict[str, str], old_progress: float, old_percent: int
    ) -> None:
        """A sound, a growing tail and a lemur party for every step forward."""
        new_percent = project.percent
        self.d_tail.animate_from(
            old_progress,
            lambda f: self.d_percent.configure(text=f"{round(old_percent + (new_percent - old_percent) * f)}%"),
        )
        self._flash_steps({u.current_step for u in moved})
        self._steps_this_session += len(moved)
        if project.is_complete:
            return  # _changing has already thrown the big party

        models = plural(sum(u.model_count for u in moved), "model")
        who = moved[0].name if len(moved) == 1 else plural(len(moved), "unit")
        tally = f"{plural(self._steps_this_session, 'step')} this session"
        finished = [u for u in moved if u.is_done]
        if finished:
            self.sound.play_unit_done()
            headline = "Unit finished!" if len(finished) == 1 else f"{len(finished)} units finished!"
            self._celebrate("unit", headline, f"{who} · {models}", cheer(), tally)
        else:
            # The chime climbs as units get closer to done.
            self.sound.play_step(max(u.steps_done / len(u.steps) for u in moved))
            completed = {before[u.id] for u in moved}
            headline = headline_for(completed.pop()) if len(completed) == 1 else "Steps done!"
            self._celebrate("step", headline, f"{who} · {models}", cheer(), tally)

    def _wag_tail(self, project: Project) -> None:
        """Shake the big tail for a commission that's just finished or shipped, if it's on show."""
        if self.selected_project is project:
            self._wagging = project.id
            self.d_tail.wag()

    def _celebrate(self, level: str, headline: str, message: str, footnote: str, tally: str = "") -> None:
        if self._celebration is not None:
            self._celebration.close()

        def forget() -> None:
            if self._celebration is celebration:
                self._celebration = None

        celebration = Celebration(
            self.root, self.fonts, level, headline, message, footnote, tally, on_close=forget
        )
        if level == "commission":
            celebration.place(in_=self.detail_container, relx=0.5, rely=0.45, anchor="center")
        else:
            celebration.place(relx=1.0, rely=1.0, x=-18, y=-(self.status.winfo_height() + 18), anchor="se")
        self._celebration = celebration  # created last, so it sits on top of the window

    def _flash_steps(self, steps: set[str]) -> None:
        """Briefly light up the strip boxes that models just moved into, like a candle flaring."""
        for step in steps:
            for widget in self.d_steps[step]:
                widget.configure(bg=GILT)
            for label in self.d_steps[step][1:]:
                label.configure(fg=INK)
        self.root.after(450, self._paint_steps)

    def _toggle_sound(self) -> None:
        self.sound.enabled = self.sound_var.get()
        try:
            save_settings(self._settings_path, {"sound": self.sound.enabled})
        except OSError:
            self._say("Couldn't save the sound setting, so it will reset next time.")
        if self.sound.enabled:
            self.sound.play_step(0.5)

    def edit_steps(self) -> None:
        models_on_step: Counter[str] = Counter()
        for project in self.projects:
            for unit in project.units:
                models_on_step[unit.step] += unit.model_count
        values = StepsDialog(self.root, self.fonts, models_on_step).show()
        if values is None:
            return
        rows = values["rows"]
        if rows == [(step, step) for step in paint_steps()]:
            return
        kept = {old for old, _new in rows}
        moving = [
            (step, destination)
            for step, destination in step_destinations(rows).items()
            if step not in kept and models_on_step[step]
        ]
        if moving:
            lines = "\n".join(
                f"•  {plural(models_on_step[step], 'model')} on {step} will move on to {destination}"
                for step, destination in moving
            )
            if not messagebox.askyesno(
                "Move models on?",
                f"Some of the removed steps still have models on them:\n\n{lines}\n\nSave the new steps?",
                parent=self.root,
            ):
                return
        change_paint_steps(self.projects, rows)
        self._save()
        self._build_step_cells()
        self.refresh()
        self._say("Painting steps updated.")

    def _on_tree_double_click(self, event: tk.Event) -> None:
        if self.tree.identify_region(event.x, event.y) == "cell":
            self.edit_unit()

    def show_about(self) -> None:
        messagebox.showinfo(
            "About Lemur Tracker",
            f"Lemur Tracker {__version__}\n\n"
            "Tracks miniature painting commissions, one ring at a time. Each commission's tail "
            "fills with black and white rings as each unit moves through its building and "
            "painting steps; the grey part is still bare plastic.\n\n"
            f"Your commissions are saved in:\n{self.data_path}",
            parent=self.root,
        )


def main() -> None:
    if sys.platform == "win32":
        # Crisp text on high-DPI Windows displays instead of blurry scaling.
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    root = tk.Tk(className="LemurTracker")
    LemurTrackerApp(root, default_data_path())
    use_dark_title_bar(root)
    root.mainloop()
