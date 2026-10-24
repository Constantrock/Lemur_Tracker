"""The client's look: dark academia and goth in her favourite purple, plus the lemur's own colours."""

from __future__ import annotations

import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from .models import PHASE_BUILDING, PHASE_DONE, PHASE_PAINTING

# Candlelit ink backgrounds, parchment text, amethyst for actions and
# selection, and antique gilt for titles and fine rules.
INK = "#120E17"  # header and status bar
BG = "#1A1521"  # window
PANEL = "#231C2C"  # panels, cards, dialogs
RAISED = "#2F2639"  # buttons, table headings
RAISED_HOVER = "#3B3047"
FIELD = "#16111C"  # text boxes and lists
BORDER = "#3E3249"
SELECTED = "#33244A"  # the selected commission card
TEXT = "#EDE4D3"  # parchment
TEXT_MUTED = "#A99DB4"
TEXT_DISABLED = "#6C6276"
AMETHYST = "#7E4FB8"
AMETHYST_HOVER = "#9467CC"
AMETHYST_DEEP = "#5B3590"
LAVENDER = "#BBA2E6"  # purple that reads as text on the dark
GILT = "#C9A55C"  # antique gold
GILT_DIM = "#6E5A35"  # hairline rules
CRIMSON = "#A23246"
FOREST = "#3F6B4F"

# Celebrations arrive as a gilt-edged note on parchment.
PARCHMENT = "#EADFC8"
PARCHMENT_INK = "#2A2130"
PARCHMENT_MUTED = "#6E6070"

# The lemur keeps its own colours: ash fur, black-and-white rings, amber eyes.
FUR = "#8E8A86"
FUR_LIGHT = "#C9C4BE"
RING_BLACK = "#0E0B11"
RING_WHITE = "#EFE8DC"
LEMUR_EYE = "#E8962E"
# Unpainted miniatures are grey plastic, so the unfilled tail is too.
GREY_PLASTIC = "#5A5560"

PHASE_TINT = {
    PHASE_BUILDING: "#38333F",
    PHASE_PAINTING: "#45305C",
    PHASE_DONE: "#2C4535",
}
# Pipeline cells with no models on that step.
EMPTY_STEP = "#1F1926"

# Palatino first: Windows has Palatino Linotype, and most Linux systems have
# its URW twin, P052. Headings use it; dense text stays in the system sans.
SERIF_FAMILIES = ("Palatino Linotype", "P052", "URW Palladio L", "Book Antiqua", "Georgia", "Noto Serif", "DejaVu Serif")

LEMUR_FACTS = [
    "Wild lemurs live only on Madagascar and the nearby Comoro Islands.",
    "A group of lemurs is called a troop, or sometimes a conspiracy.",
    "A ring-tailed lemur's tail is longer than the rest of its body.",
    "Ring-tailed lemur troops are led by the females.",
    "Ring-tailed lemurs sunbathe sitting upright with their arms spread to the sun.",
    "Male ring-tailed lemurs hold 'stink fights', wafting scent at rivals with their tails.",
    "The aye-aye is a lemur that taps on wood and listens for grubs inside.",
    "Mouse lemurs are among the smallest primates in the world.",
    "Lemurs groom with a 'toothcomb' of lower front teeth and a special grooming claw.",
    "Sifakas cross open ground by hopping sideways, which looks a lot like dancing.",
    "The indri, the largest living lemur, sings in eerie wailing choruses.",
    "Ring-tailed lemurs spend more time on the ground than most other lemurs.",
]


class Fonts:
    """Serif display fonts over the platform's default sans (Segoe UI on Windows)."""

    def __init__(self, root: tk.Misc) -> None:
        base = tkfont.nametofont("TkDefaultFont", root=root)
        family = base.actual("family")
        available = set(tkfont.families(root))
        serif = next((f for f in SERIF_FAMILIES if f in available), family)
        size = 10
        base.configure(size=size)
        tkfont.nametofont("TkTextFont", root=root).configure(size=size)
        tkfont.nametofont("TkHeadingFont", root=root).configure(size=size, weight="bold")
        self.body = base
        self.small = tkfont.Font(root=root, family=family, size=size - 1)
        self.bold = tkfont.Font(root=root, family=family, size=size, weight="bold")
        self.subtitle = tkfont.Font(root=root, family=serif, size=size + 1, slant="italic")
        self.card_title = tkfont.Font(root=root, family=serif, size=size + 3, weight="bold")
        self.title = tkfont.Font(root=root, family=serif, size=size + 8, weight="bold")
        self.app_title = tkfont.Font(root=root, family=serif, size=size + 12, weight="bold")
        self.huge = tkfont.Font(root=root, family=serif, size=size + 16, weight="bold")


def use_dark_title_bar(window: tk.Misc) -> None:
    """Ask Windows 10/11 for a dark title bar to match. Does nothing elsewhere."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        on = ctypes.c_int(1)
        # DWMWA_USE_IMMERSIVE_DARK_MODE is 20, or 19 on early Windows 10 builds.
        for attribute in (20, 19):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(on), ctypes.sizeof(on)) == 0:
                break
    except (AttributeError, OSError):
        pass


def apply_styles(root: tk.Tk) -> Fonts:
    fonts = Fonts(root)
    root.configure(background=BG)

    # Classic Tk widgets (menus, drop-down lists, Linux message boxes) read these.
    for pattern, value in (
        ("*background", BG),
        ("*foreground", TEXT),
        ("*selectBackground", AMETHYST),
        ("*selectForeground", TEXT),
        ("*activeBackground", AMETHYST),
        ("*activeForeground", TEXT),
        ("*highlightBackground", BG),
        ("*insertBackground", TEXT),
        ("*Menu.background", PANEL),
        ("*Menu.relief", "flat"),
        ("*TCombobox*Listbox.background", FIELD),
        ("*TCombobox*Listbox.foreground", TEXT),
        ("*TCombobox*Listbox.selectBackground", AMETHYST),
        ("*TCombobox*Listbox.selectForeground", TEXT),
    ):
        root.option_add(pattern, value)

    style = ttk.Style(root)
    # "clam" looks the same on Windows and Linux and takes custom colours.
    style.theme_use("clam")
    style.configure(
        ".",
        background=BG,
        foreground=TEXT,
        bordercolor=BORDER,
        lightcolor=BG,
        darkcolor=BG,
        troughcolor=FIELD,
        focuscolor=AMETHYST,
        selectbackground=AMETHYST,
        selectforeground=TEXT,
        fieldbackground=FIELD,
        insertcolor=TEXT,
        arrowcolor=TEXT_MUTED,
    )
    # Replace clam's light hover and unfocused-selection colours.
    style.map(
        ".",
        background=[("disabled", BG), ("active", BG)],
        foreground=[("disabled", TEXT_DISABLED)],
        selectbackground=[("!focus", AMETHYST_DEEP)],
        selectforeground=[("!focus", TEXT)],
    )

    style.configure("TFrame", background=BG)
    style.configure("Panel.TFrame", background=PANEL)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Heading.TLabel", background=BG, foreground=GILT, font=fonts.title)
    style.configure("Panel.TLabel", background=PANEL)
    style.configure("Muted.TLabel", background=PANEL, foreground=TEXT_MUTED)
    style.configure("Title.TLabel", background=PANEL, foreground=GILT, font=fonts.title)
    style.configure("Section.TLabel", background=PANEL, foreground=GILT, font=fonts.card_title)
    style.configure("Status.TLabel", background=INK, foreground=TEXT_MUTED, padding=(10, 4))

    for name, background in (
        ("TCheckbutton", BG),
        ("Panel.TCheckbutton", PANEL),
        ("Header.TCheckbutton", INK),
        ("TRadiobutton", BG),
        ("Panel.TRadiobutton", PANEL),
    ):
        style.configure(
            name,
            background=background,
            foreground=TEXT,
            indicatorbackground=FIELD,
            indicatorforeground=LAVENDER,
            upperbordercolor=BORDER,
            lowerbordercolor=BORDER,
        )
        style.map(name, background=[("active", background)], indicatorbackground=[("pressed", RAISED)])

    style.configure(
        "TButton",
        padding=(10, 4),
        background=RAISED,
        foreground=TEXT,
        bordercolor=BORDER,
        lightcolor=RAISED,
        darkcolor=RAISED,
    )
    style.map(
        "TButton",
        background=[("disabled", PANEL), ("pressed", BORDER), ("active", RAISED_HOVER)],
        foreground=[("disabled", TEXT_DISABLED)],
        lightcolor=[("disabled", PANEL), ("pressed", BORDER), ("active", RAISED_HOVER)],
        darkcolor=[("disabled", PANEL), ("pressed", BORDER), ("active", RAISED_HOVER)],
    )
    style.configure(
        "Accent.TButton",
        background=AMETHYST,
        foreground=TEXT,
        font=fonts.bold,
        bordercolor=AMETHYST_DEEP,
        lightcolor=AMETHYST,
        darkcolor=AMETHYST,
    )
    style.map(
        "Accent.TButton",
        background=[("disabled", PANEL), ("pressed", AMETHYST_DEEP), ("active", AMETHYST_HOVER)],
        foreground=[("disabled", TEXT_DISABLED)],
        bordercolor=[("disabled", BORDER)],
        lightcolor=[("disabled", PANEL), ("pressed", AMETHYST_DEEP), ("active", AMETHYST_HOVER)],
        darkcolor=[("disabled", PANEL), ("pressed", AMETHYST_DEEP), ("active", AMETHYST_HOVER)],
    )
    # A button that reads like a text link.
    style.configure(
        "Link.TButton",
        background=PANEL,
        foreground=GILT,
        bordercolor=PANEL,
        lightcolor=PANEL,
        darkcolor=PANEL,
        padding=(4, 0),
        font=fonts.small,
    )
    style.map(
        "Link.TButton",
        background=[("active", PANEL), ("pressed", PANEL)],
        foreground=[("active", TEXT)],
        lightcolor=[("pressed", PANEL)],
        darkcolor=[("pressed", PANEL)],
    )

    for name in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(
            name,
            fieldbackground=FIELD,
            foreground=TEXT,
            background=RAISED,
            insertcolor=TEXT,
            arrowcolor=TEXT,
            bordercolor=BORDER,
            lightcolor=FIELD,
            darkcolor=FIELD,
        )
        style.map(
            name,
            fieldbackground=[("readonly", FIELD), ("disabled", PANEL)],
            foreground=[("disabled", TEXT_DISABLED)],
            background=[("active", RAISED_HOVER), ("pressed", RAISED_HOVER)],
            bordercolor=[("focus", AMETHYST)],
            lightcolor=[("focus", AMETHYST_DEEP)],
            selectbackground=[("readonly", "!focus", FIELD), ("!focus", AMETHYST_DEEP)],
            selectforeground=[("!focus", TEXT)],
        )

    style.configure(
        "Treeview",
        background=PANEL,
        fieldbackground=PANEL,
        foreground=TEXT,
        bordercolor=BORDER,
        lightcolor=PANEL,
        darkcolor=PANEL,
        rowheight=int(fonts.body.metrics("linespace") * 1.8),
    )
    style.configure(
        "Treeview.Heading",
        background=RAISED,
        foreground=GILT,
        font=fonts.bold,
        padding=(6, 4),
        bordercolor=BORDER,
        lightcolor=RAISED,
        darkcolor=RAISED,
    )
    style.map("Treeview.Heading", background=[("active", RAISED_HOVER)])
    style.map("Treeview", background=[("selected", AMETHYST)], foreground=[("selected", TEXT)])

    style.configure(
        "TScrollbar",
        background=RAISED,
        troughcolor=BG,
        bordercolor=BORDER,
        lightcolor=RAISED,
        darkcolor=RAISED,
        arrowcolor=TEXT_MUTED,
        gripcount=0,
    )
    style.map(
        "TScrollbar",
        background=[("pressed", AMETHYST_DEEP), ("active", RAISED_HOVER)],
        arrowcolor=[("disabled", TEXT_DISABLED)],
    )
    style.configure("TPanedwindow", background=BG)
    style.configure("Sash", background=BG, bordercolor=BG, lightcolor=BG, gripcount=0, sashthickness=6)
    return fonts
