"""Modal forms for adding and editing commissions and units."""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from .models import (
    BUILD_STEP,
    DEFAULT_PAINT_STEPS,
    COMMON_EFFECTS,
    DONE,
    UNIT_TYPES,
    DetailLevel,
    Project,
    Unit,
    paint_steps,
    parse_effects,
    step_list_problem,
    steps_for,
    typical_model_count,
)
from .theme import AMETHYST, BORDER, FIELD, PANEL, TEXT, Fonts, use_dark_title_bar


def _text_box(master: tk.Misc, fonts: Fonts, height: int, width: int = 40) -> tk.Text:
    return tk.Text(
        master,
        height=height,
        width=width,
        wrap="word",
        font=fonts.body,
        background=FIELD,
        foreground=TEXT,
        insertbackground=TEXT,
        relief="flat",
        highlightthickness=1,
        highlightbackground=BORDER,
        highlightcolor=AMETHYST,
        padx=6,
        pady=4,
        undo=True,
    )


def _text_value(box: tk.Text) -> str:
    return box.get("1.0", "end-1c").strip()


class _Dialog(tk.Toplevel):
    """Base for a modal form. Subclasses fill `self.body` and implement `_collect`."""

    def __init__(self, parent: tk.Misc, fonts: Fonts, title: str, ok_text: str) -> None:
        super().__init__(parent)
        self.withdraw()
        self.title(title)
        self.configure(background=PANEL)
        use_dark_title_bar(self)
        self.transient(parent)
        self.resizable(False, False)
        self.fonts = fonts
        self.result: dict | None = None
        self._ok_text = ok_text
        self.body = ttk.Frame(self, style="Panel.TFrame", padding=18)
        self.body.pack(fill="both", expand=True)
        self.body.columnconfigure(1, weight=1)
        self.bind("<Escape>", lambda _e: self.destroy())

    def _label(self, row: int, text: str) -> None:
        ttk.Label(self.body, text=text, style="Panel.TLabel").grid(
            row=row, column=0, sticky="nw", padx=(0, 12), pady=5
        )

    def _hint(self, row: int, text: str) -> None:
        ttk.Label(self.body, text=text, style="Muted.TLabel", font=self.fonts.small).grid(
            row=row, column=1, sticky="w", pady=(0, 4)
        )

    def _add_buttons(self, row: int) -> None:
        bar = ttk.Frame(self.body, style="Panel.TFrame")
        bar.grid(row=row, column=0, columnspan=2, sticky="e", pady=(16, 0))
        ttk.Button(bar, text="Cancel", command=self.destroy).pack(side="right")
        ttk.Button(bar, text=self._ok_text, style="Accent.TButton", command=self._on_ok).pack(
            side="right", padx=(0, 8)
        )

    def _collect(self) -> dict | None:
        """Return the form values, or None after telling the user what's wrong."""
        raise NotImplementedError

    def _on_ok(self) -> None:
        values = self._collect()
        if values is not None:
            self.result = values
            self.destroy()

    def _invalid(self, message: str, widget: tk.Widget) -> None:
        messagebox.showwarning("Hang on a tail-flick", message, parent=self)
        widget.focus_set()

    def show(self) -> dict | None:
        self.update_idletasks()
        parent = self.master
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_reqwidth()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_reqheight()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.deiconify()
        self.wait_visibility()
        self.grab_set()
        self.wait_window()
        return self.result


class ProjectDialog(_Dialog):
    """Commission name, client details, acceptance date and notes."""

    def __init__(self, parent: tk.Misc, fonts: Fonts, project: Project | None = None) -> None:
        editing = project is not None
        super().__init__(
            parent,
            fonts,
            "Edit commission" if editing else "New commission",
            "Save" if editing else "Add to the troop",
        )
        self.name_var = tk.StringVar(value=project.name if editing else "")
        self.client_var = tk.StringVar(value=project.client_name if editing else "")
        accepted = project.accepted_on if editing else date.today()
        self.accepted_var = tk.StringVar(value=accepted.isoformat())

        self._label(0, "Commission name")
        self.name_entry = ttk.Entry(self.body, textvariable=self.name_var, width=42)
        self.name_entry.grid(row=0, column=1, sticky="ew", pady=5)

        self._label(1, "Client name")
        ttk.Entry(self.body, textvariable=self.client_var).grid(row=1, column=1, sticky="ew", pady=5)

        self._label(2, "Client address")
        self.address_box = _text_box(self.body, fonts, height=3)
        self.address_box.grid(row=2, column=1, sticky="ew", pady=5)

        self._label(3, "Accepted on")
        self.accepted_entry = ttk.Entry(self.body, textvariable=self.accepted_var, width=14)
        self.accepted_entry.grid(row=3, column=1, sticky="w", pady=(5, 0))
        self._hint(4, "Year-month-day, e.g. 2026-10-23")

        self._label(5, "Notes")
        self.notes_box = _text_box(self.body, fonts, height=3)
        self.notes_box.grid(row=5, column=1, sticky="ew", pady=5)

        if editing:
            self.address_box.insert("1.0", project.client_address)
            self.notes_box.insert("1.0", project.notes)

        self._add_buttons(6)
        self.name_entry.focus_set()

    def _collect(self) -> dict | None:
        name = self.name_var.get().strip()
        if not name:
            self._invalid("Give the commission a name so you can find it in the troop.", self.name_entry)
            return None
        try:
            accepted = date.fromisoformat(self.accepted_var.get().strip())
        except ValueError:
            self._invalid("The accepted date should look like 2026-10-23.", self.accepted_entry)
            return None
        return {
            "name": name,
            "client_name": self.client_var.get().strip(),
            "client_address": _text_value(self.address_box),
            "accepted_on": accepted,
            "notes": _text_value(self.notes_box),
        }


class UnitDialog(_Dialog):
    """A unit's type, size, detail level, effects, and the step it's on."""

    def __init__(self, parent: tk.Misc, fonts: Fonts, unit: Unit | None = None) -> None:
        editing = unit is not None
        super().__init__(parent, fonts, "Edit unit" if editing else "Add unit", "Save" if editing else "Add unit")
        unit = unit or Unit(name="")
        self.name_var = tk.StringVar(value=unit.name)
        self.type_var = tk.StringVar(value=unit.unit_type)
        self.count_var = tk.StringVar(value=str(unit.model_count))
        self.detail_var = tk.StringVar(value=unit.detail_level.value)
        self.effects_var = tk.StringVar(value=", ".join(unit.effects))
        self.needs_building_var = tk.BooleanVar(value=unit.needs_building)
        self.step_var = tk.StringVar(value=unit.current_step)
        self.notes_var = tk.StringVar(value=unit.notes)
        # A new unit starts at the usual size for its type and follows the type
        # until its count is changed by hand. Existing units keep their count.
        self._adding = not editing
        self._auto_count: int | None = None  # the count last filled in for the type
        if self._adding:
            self._auto_count = typical_model_count(unit.unit_type) or unit.model_count
            self.count_var.set(str(self._auto_count))

        self._label(0, "Unit name")
        self.name_entry = ttk.Entry(self.body, textvariable=self.name_var, width=42)
        self.name_entry.grid(row=0, column=1, sticky="ew", pady=5)

        self._label(1, "Unit type")
        ttk.Combobox(self.body, textvariable=self.type_var, values=UNIT_TYPES).grid(
            row=1, column=1, sticky="w", pady=5
        )

        self._label(2, "Models")
        count_row = ttk.Frame(self.body, style="Panel.TFrame")
        count_row.grid(row=2, column=1, sticky="w", pady=5)
        self.count_spin = ttk.Spinbox(count_row, from_=1, to=999, textvariable=self.count_var, width=6)
        self.count_spin.pack(side="left")
        self.count_hint = ttk.Label(count_row, style="Muted.TLabel", font=fonts.small)
        self.count_hint.pack(side="left", padx=(10, 0))
        self.type_var.trace_add("write", lambda *_: self._follow_type())
        self.count_var.trace_add("write", lambda *_: self._sync_count_hint())
        self._sync_count_hint()

        self._label(3, "Detail level")
        levels = ttk.Frame(self.body, style="Panel.TFrame")
        levels.grid(row=3, column=1, sticky="w", pady=5)
        for level in DetailLevel:
            ttk.Radiobutton(
                levels,
                text=f"{level.pips}  {level.value}",
                value=level.value,
                variable=self.detail_var,
                style="Panel.TRadiobutton",
            ).pack(side="left", padx=(0, 14))

        self._label(4, "Painting effects")
        ttk.Entry(self.body, textvariable=self.effects_var).grid(row=4, column=1, sticky="ew", pady=(5, 0))
        quick = ttk.Frame(self.body, style="Panel.TFrame")
        quick.grid(row=5, column=1, sticky="w", pady=(4, 5))
        ttk.Label(quick, text="Separate with commas, or quick add:", style="Muted.TLabel", font=fonts.small).pack(
            side="left"
        )
        self.quick_effect = ttk.Combobox(quick, values=COMMON_EFFECTS, state="readonly", width=28)
        self.quick_effect.pack(side="left", padx=(6, 0))
        self.quick_effect.bind("<<ComboboxSelected>>", self._add_quick_effect)

        self._label(6, "Current step")
        progress = ttk.Frame(self.body, style="Panel.TFrame")
        progress.grid(row=6, column=1, sticky="w", pady=5)
        self.step_combo = ttk.Combobox(progress, textvariable=self.step_var, state="readonly", width=18)
        self.step_combo.pack(side="left", padx=(0, 14))
        ttk.Checkbutton(
            progress,
            text="Needs building",
            variable=self.needs_building_var,
            style="Panel.TCheckbutton",
            command=self._on_needs_building,
        ).pack(side="left")
        self._sync_step_choices()
        self._hint(7, "Every model in the unit moves through the steps together.")

        self._label(8, "Notes")
        ttk.Entry(self.body, textvariable=self.notes_var).grid(row=8, column=1, sticky="ew", pady=5)

        self._add_buttons(9)
        self.name_entry.focus_set()

    def _follow_type(self) -> None:
        """Give a new unit the usual count for its type, unless the count was changed by hand."""
        typical = typical_model_count(self.type_var.get())
        if typical is not None and self._auto_count is not None and self.count_var.get() == str(self._auto_count):
            self._auto_count = typical
            self.count_var.set(str(typical))
        self._sync_count_hint()

    def _sync_count_hint(self) -> None:
        typical = typical_model_count(self.type_var.get())
        usual = self._adding and typical is not None and self.count_var.get() == str(typical)
        self.count_hint.configure(text="usual size for this type" if usual else "")

    def _sync_step_choices(self) -> None:
        self.step_combo.configure(values=[*steps_for(self.needs_building_var.get()), DONE])

    def _on_needs_building(self) -> None:
        self._sync_step_choices()
        # Keep an unstarted unit at the start of its (now longer or shorter) list of steps.
        needs_building, step, first = self.needs_building_var.get(), self.step_var.get(), paint_steps()[0]
        if needs_building and step == first:
            self.step_var.set(BUILD_STEP)
        elif not needs_building and step == BUILD_STEP:
            self.step_var.set(first)

    def _add_quick_effect(self, _event: tk.Event) -> None:
        effects = parse_effects(f"{self.effects_var.get()}, {self.quick_effect.get()}")
        self.effects_var.set(", ".join(effects))
        self.quick_effect.set("")

    def _collect(self) -> dict | None:
        name = self.name_var.get().strip()
        if not name:
            self._invalid("Give the unit a name, like 'Captain' or 'Intercessor Squad'.", self.name_entry)
            return None
        try:
            count = int(self.count_var.get())
        except ValueError:
            count = 0
        if count < 1:
            self._invalid("A unit needs at least one model.", self.count_spin)
            return None
        return {
            "name": name,
            "unit_type": self.type_var.get().strip() or "Other",
            "model_count": count,
            "detail_level": DetailLevel(self.detail_var.get()),
            "effects": parse_effects(self.effects_var.get()),
            "needs_building": self.needs_building_var.get(),
            "step": self.step_var.get(),
            "notes": self.notes_var.get().strip(),
        }


class StepsDialog(_Dialog):
    """Add, rename, remove and reorder the painting steps."""

    def __init__(self, parent: tk.Misc, fonts: Fonts, models_on_step: dict[str, int]) -> None:
        super().__init__(parent, fonts, "Painting steps", "Save steps")
        self._models_on_step = models_on_step
        # One row per step in the edited list: (the step it started as, or None if new; its name now).
        self.rows: list[tuple[str | None, str]] = [(step, step) for step in paint_steps()]
        self.name_var = tk.StringVar()

        ttk.Label(
            self.body,
            text="Every model in a unit moves through these steps together.",
            style="Muted.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(self.body, text=f"{BUILD_STEP}  (first, for units that need building)", style="Muted.TLabel").grid(
            row=1, column=0, sticky="w", padx=(10, 0)
        )
        self.listbox = tk.Listbox(
            self.body,
            height=12,
            width=40,
            font=fonts.body,
            activestyle="none",
            exportselection=False,  # keep the selection while typing in the name box
            selectbackground=AMETHYST,
            selectforeground=TEXT,
            background=FIELD,
            foreground=TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=AMETHYST,
        )
        self.listbox.grid(row=2, column=0, sticky="nsew", pady=4)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)
        ttk.Label(self.body, text=f"{DONE}  (always last)", style="Muted.TLabel").grid(
            row=3, column=0, sticky="w", padx=(10, 0)
        )

        side = ttk.Frame(self.body, style="Panel.TFrame")
        side.grid(row=2, column=1, sticky="n", padx=(10, 0), pady=4)
        for text, command in (("Move up", self._move_up), ("Move down", self._move_down), ("Remove", self._remove)):
            ttk.Button(side, text=text, command=command, width=14).pack(fill="x", pady=(0, 6))
        ttk.Button(side, text="Reset to defaults", command=self._reset, width=14).pack(fill="x", pady=(18, 0))

        name_row = ttk.Frame(self.body, style="Panel.TFrame")
        name_row.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Label(name_row, text="Step name", style="Panel.TLabel").pack(side="left")
        self.name_entry = ttk.Entry(name_row, textvariable=self.name_var, width=24)
        self.name_entry.pack(side="left", padx=(8, 8), fill="x", expand=True)
        ttk.Button(name_row, text="Rename", command=self._rename).pack(side="left")
        ttk.Button(name_row, text="Add", command=self._add).pack(side="left", padx=(6, 0))
        ttk.Label(
            self.body,
            text="Units on a renamed step follow it. Units on a removed step move on to the next one.",
            style="Muted.TLabel",
            font=fonts.small,
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(4, 0))

        self._add_buttons(6)
        self._redraw(select=0)
        self.name_entry.focus_set()

    def _redraw(self, select: int | None = None) -> None:
        self.listbox.delete(0, "end")
        for old, name in self.rows:
            models = self._models_on_step.get(old, 0) if old else 0
            here = f"{models} model{'' if models == 1 else 's'} here"
            self.listbox.insert("end", f"{name}   ·   {here}" if models else name)
        if select is not None and self.rows:
            select = max(0, min(select, len(self.rows) - 1))
            self.listbox.selection_set(select)
            self.listbox.see(select)
            self.name_var.set(self.rows[select][1])

    def _selected(self) -> int | None:
        selection = self.listbox.curselection()
        return selection[0] if selection else None

    def _on_select(self, _event: tk.Event) -> None:
        index = self._selected()
        if index is not None:
            self.name_var.set(self.rows[index][1])

    def _try(self, rows: list[tuple[str | None, str]], select: int) -> None:
        """Use `rows` if they make a valid list; otherwise say why not."""
        problem = step_list_problem([name for _old, name in rows])
        if problem:
            self._invalid(problem, self.name_entry)
            return
        self.rows = rows
        self._redraw(select)

    def _add(self) -> None:
        index = self._selected()
        at = len(self.rows) if index is None else index + 1
        self._try([*self.rows[:at], (None, self.name_var.get().strip()), *self.rows[at:]], at)

    def _rename(self) -> None:
        index = self._selected()
        if index is None:
            return
        rows = list(self.rows)
        rows[index] = (rows[index][0], self.name_var.get().strip())
        self._try(rows, index)

    def _remove(self) -> None:
        index = self._selected()
        if index is None:
            return
        self._try(self.rows[:index] + self.rows[index + 1 :], index)

    def _move(self, index: int | None, offset: int) -> None:
        if index is None or not 0 <= index + offset < len(self.rows):
            return
        rows = list(self.rows)
        rows[index], rows[index + offset] = rows[index + offset], rows[index]
        self.rows = rows
        self._redraw(index + offset)

    def _move_up(self) -> None:
        self._move(self._selected(), -1)

    def _move_down(self) -> None:
        self._move(self._selected(), 1)

    def _reset(self) -> None:
        current = set(paint_steps())
        self.rows = [(step if step in current else None, step) for step in DEFAULT_PAINT_STEPS]
        self._redraw(0)

    def _collect(self) -> dict | None:
        problem = step_list_problem([name for _old, name in self.rows])
        if problem:
            self._invalid(problem, self.name_entry)
            return None
        return {"rows": list(self.rows)}
