"""Saving and loading commissions as a JSON file in the user's data folder."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from .models import DEFAULT_PAINT_STEPS, Project, step_list_problem

DATA_ENV_VAR = "LEMUR_TRACKER_DATA"
SCHEMA_VERSION = 1


def default_data_path() -> Path:
    """%APPDATA%\\LemurTracker on Windows, ~/.local/share/LemurTracker elsewhere.

    Set LEMUR_TRACKER_DATA to a file path to use a different file.
    """
    override = os.environ.get(DATA_ENV_VAR)
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "LemurTracker" / "commissions.json"


def load_data(path: Path) -> tuple[list[Project], list[str]]:
    """Return the saved projects and painting steps (defaults if nothing is saved yet).

    Raises ValueError (including json.JSONDecodeError) or KeyError if the
    file exists but can't be read as Lemur Tracker data.
    """
    if not path.exists():
        return [], list(DEFAULT_PAINT_STEPS)
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object at the top level")
    steps = data.get("paint_steps")
    # A damaged step list isn't worth refusing the whole file over; units keep
    # their step names, so re-adding a step brings their progress back.
    if not isinstance(steps, list) or not all(isinstance(s, str) for s in steps) or step_list_problem(steps):
        steps = list(DEFAULT_PAINT_STEPS)
    return [Project.from_dict(p) for p in data.get("projects", [])], steps


def save_data(path: Path, projects: list[Project], paint_steps: list[str]) -> None:
    """Write everything, replacing the file atomically so a crash can't truncate it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": SCHEMA_VERSION,
        "paint_steps": paint_steps,
        "projects": [p.to_dict() for p in projects],
    }
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def quarantine(path: Path) -> Path:
    """Move an unreadable data file aside so it isn't overwritten, and return its new path."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = path.with_name(f"{path.name}.unreadable-{stamp}")
    os.replace(path, target)
    return target


DEFAULT_SETTINGS = {"sound": True}


def settings_path(data_path: Path) -> Path:
    """Settings live beside the commissions file."""
    return data_path.with_name("settings.json")


def load_settings(path: Path) -> dict:
    """Saved settings over the defaults. A missing or unreadable file just means defaults."""
    settings = dict(DEFAULT_SETTINGS)
    try:
        with path.open(encoding="utf-8") as f:
            saved = json.load(f)
    except (OSError, ValueError):
        return settings
    if isinstance(saved, dict):
        settings.update({k: v for k, v in saved.items() if k in DEFAULT_SETTINGS})
    return settings


def save_settings(path: Path, settings: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
