"""Data model: a commission (Project) made up of Units that move through painting steps."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from enum import Enum


def new_id() -> str:
    return uuid.uuid4().hex


class DetailLevel(str, Enum):
    """Painting detail levels, declared lowest to highest."""

    BATTLE_READY = "Battle Ready"
    PARADE = "Parade"
    SHOWCASE = "Showcase"

    @property
    def rank(self) -> int:
        return list(DetailLevel).index(self) + 1

    @property
    def pips(self) -> str:
        """Glanceable marker, e.g. '●●○' for Parade."""
        total = len(DetailLevel)
        return "●" * self.rank + "○" * (total - self.rank)


# Suggestions only; the unit type and effects fields accept any text.
# Each suggested unit type comes with the usual 40k model count for a unit of
# that type, which a new unit starts from.
UNIT_TYPE_MODELS = {
    "HQ": 1,
    "Character": 1,
    "Squad": 10,
    "Battleline": 10,
    "Elites": 5,
    "Fast Attack": 5,
    "Heavy Support": 5,
    "Vehicle": 1,
    "Monster": 1,
    "Dedicated Transport": 1,
    "Fortification": 1,
    "Other": 1,
}
UNIT_TYPES = list(UNIT_TYPE_MODELS)


def typical_model_count(unit_type: str) -> int | None:
    """The usual model count for a unit of this type, or None for a type not in the list."""
    wanted = unit_type.strip().casefold()
    return next((n for name, n in UNIT_TYPE_MODELS.items() if name.casefold() == wanted), None)

COMMON_EFFECTS = [
    "Object source lighting (OSL)",
    "Non-metallic metal (NMM)",
    "Freehand",
    "Weathering",
    "Battle damage",
    "Glowing weapons",
    "Gemstones",
    "Lenses / eye glow",
    "Fire / flames",
    "Verdigris",
    "Marble",
]


def parse_effects(text: str) -> list[str]:
    """Split comma-separated effects, dropping blanks and repeats."""
    effects: list[str] = []
    for part in text.split(","):
        effect = part.strip()
        if effect and effect.casefold() not in (e.casefold() for e in effects):
            effects.append(effect)
    return effects


# Models in a unit are batch-painted: the whole unit moves through the steps
# together. Build always comes first (skipped for models that arrive
# ready-built) and Done always comes last; the painting steps between them are
# editable in the app and saved with the commissions.
BUILD_STEP = "Build"
DONE = "Done"
DEFAULT_PAINT_STEPS = (
    "Prime",
    "Base coat",
    "Metallics",
    "Wash",
    "Highlights",
    "Details & effects",
    "Basing",
    "Varnish",
)
_paint_steps = list(DEFAULT_PAINT_STEPS)

PHASE_BUILDING = "Building"
PHASE_PAINTING = "Painting"
PHASE_DONE = "Done"


def paint_steps() -> list[str]:
    """The painting steps in use, in order."""
    return list(_paint_steps)


def all_steps() -> list[str]:
    """Everywhere a unit can be, in order."""
    return [BUILD_STEP, *_paint_steps, DONE]


def steps_for(needs_building: bool) -> list[str]:
    """A unit's steps in order."""
    return [BUILD_STEP, *_paint_steps] if needs_building else list(_paint_steps)


def step_list_problem(steps: list[str]) -> str | None:
    """Why `steps` can't be the painting steps, or None if they're fine."""
    if not steps:
        return "Keep at least one painting step."
    seen = set()
    for step in steps:
        if not step or step != step.strip():
            return "Step names can't be blank or start or end with spaces."
        key = step.casefold()
        if key in (BUILD_STEP.casefold(), DONE.casefold()):
            return f"“{step}” is built in: Build always comes first and Done always comes last."
        if key in seen:
            return f"“{step}” is in the list twice."
        seen.add(key)
    return None


def set_paint_steps(steps: list[str]) -> None:
    problem = step_list_problem(steps)
    if problem:
        raise ValueError(problem)
    _paint_steps[:] = steps


def step_destinations(rows: list[tuple[str | None, str]]) -> dict[str, str]:
    """Where units on each current painting step end up after an edit.

    `rows` is the edited list in order: (the current step each row came from,
    or None for a new step, and its new name). Units on a renamed step follow
    the new name; units on a removed step move on to the next step that's
    still in the list, or to Done if there isn't one.
    """
    survivors = {old: new for old, new in rows if old is not None}
    return {
        step: next((survivors[later] for later in _paint_steps[i:] if later in survivors), DONE)
        for i, step in enumerate(_paint_steps)
    }


def change_paint_steps(projects: list[Project], rows: list[tuple[str | None, str]]) -> None:
    """Switch to the edited step list, moving units as step_destinations describes."""
    new_steps = [new for _old, new in rows]
    problem = step_list_problem(new_steps)
    if problem:
        raise ValueError(problem)
    destinations = step_destinations(rows)
    for project in projects:
        for unit in project.units:
            unit.step = destinations.get(unit.step, unit.step)
    _paint_steps[:] = new_steps


def phase_of(step: str) -> str:
    if step == BUILD_STEP:
        return PHASE_BUILDING
    return PHASE_DONE if step == DONE else PHASE_PAINTING


@dataclass
class Unit:
    """One entry in a commission: an HQ, a squad, a vehicle, and so on."""

    name: str
    unit_type: str = "Squad"
    model_count: int = 1
    detail_level: DetailLevel = DetailLevel.BATTLE_READY
    effects: list[str] = field(default_factory=list)
    needs_building: bool = True
    # The step every model in the unit is on now, or DONE.
    step: str = BUILD_STEP
    notes: str = ""
    id: str = field(default_factory=new_id)

    @property
    def steps(self) -> list[str]:
        return steps_for(self.needs_building)

    @property
    def steps_done(self) -> int:
        steps = self.steps
        if self.step == DONE:
            return len(steps)
        # A step outside this unit's list (Build on a ready-built unit) means nothing is done yet.
        return steps.index(self.step) if self.step in steps else 0

    @property
    def current_step(self) -> str:
        steps, done = self.steps, self.steps_done
        return steps[done] if done < len(steps) else DONE

    @property
    def phase(self) -> str:
        return phase_of(self.current_step)

    @property
    def is_done(self) -> bool:
        return self.current_step == DONE

    def advance(self) -> None:
        """Move the whole unit on to its next step."""
        self.step = [*self.steps, DONE][min(self.steps_done + 1, len(self.steps))]

    def step_back(self) -> None:
        self.step = self.steps[max(self.steps_done - 1, 0)]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "unit_type": self.unit_type,
            "model_count": self.model_count,
            "detail_level": self.detail_level.value,
            "effects": list(self.effects),
            "needs_building": self.needs_building,
            "step": self.step,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Unit:
        return cls(
            id=data.get("id") or new_id(),
            name=data["name"],
            unit_type=data.get("unit_type", "Squad"),
            model_count=max(1, int(data.get("model_count", 1))),
            detail_level=DetailLevel(data.get("detail_level", DetailLevel.BATTLE_READY.value)),
            effects=list(data.get("effects", [])),
            needs_building=bool(data.get("needs_building", True)),
            step=data.get("step", BUILD_STEP),
            notes=data.get("notes", ""),
        )


@dataclass
class Project:
    """A painting commission for one client."""

    name: str
    client_name: str = ""
    client_address: str = ""
    accepted_on: date = field(default_factory=date.today)
    units: list[Unit] = field(default_factory=list)
    notes: str = ""
    delivered: bool = False
    id: str = field(default_factory=new_id)

    @property
    def model_count(self) -> int:
        return sum(u.model_count for u in self.units)

    def _steps(self) -> tuple[int, int]:
        """(done, total) unit steps, each weighted by the unit's model count.

        A unit moves through its steps as one batch, but a step on a 20-model
        squad is more work than the same step on a lone HQ.
        """
        done = sum(u.steps_done * u.model_count for u in self.units)
        total = sum(len(u.steps) * u.model_count for u in self.units)
        return done, total

    @property
    def progress(self) -> float:
        """Fraction of work done, 0.0 to 1.0."""
        done, total = self._steps()
        return done / total if total else 0.0

    @property
    def percent(self) -> int:
        """Whole percent done, rounded down so 100% only shows when finished."""
        done, total = self._steps()
        return done * 100 // total if total else 0

    @property
    def is_complete(self) -> bool:
        return bool(self.units) and all(u.is_done for u in self.units)

    def step_counts(self) -> dict[str, int]:
        """Number of models on each step, in all_steps() order."""
        counts = {step: 0 for step in all_steps()}
        for unit in self.units:
            counts[unit.current_step] += unit.model_count
        return counts

    def detail_counts(self) -> dict[DetailLevel, int]:
        """Number of models at each detail level, lowest to highest."""
        counts = {level: 0 for level in DetailLevel}
        for unit in self.units:
            counts[unit.detail_level] += unit.model_count
        return counts

    def days_since_accepted(self, today: date | None = None) -> int:
        return ((today or date.today()) - self.accepted_on).days

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "client_name": self.client_name,
            "client_address": self.client_address,
            "accepted_on": self.accepted_on.isoformat(),
            "notes": self.notes,
            "delivered": self.delivered,
            "units": [u.to_dict() for u in self.units],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Project:
        return cls(
            id=data.get("id") or new_id(),
            name=data["name"],
            client_name=data.get("client_name", ""),
            client_address=data.get("client_address", ""),
            accepted_on=date.fromisoformat(data["accepted_on"]) if data.get("accepted_on") else date.today(),
            notes=data.get("notes", ""),
            delivered=bool(data.get("delivered", False)),
            units=[Unit.from_dict(u) for u in data.get("units", [])],
        )
