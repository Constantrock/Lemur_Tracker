"""Rewards for progress: synthesized chimes and the words that go with them.

Every step a unit moves on earns a short chirp-and-chime whose pitch climbs as
the unit nears the end, so progress can be heard as well as seen. Finishing a
unit earns a flourish, and finishing a whole commission earns a fanfare.
Sounds are generated here, so there are no audio files to ship.
"""

from __future__ import annotations

import atexit
import io
import math
import random
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
from collections.abc import Callable
from pathlib import Path

RATE = 22050

STEP_BASE_PITCH = 523.25  # C5: the chime for a unit's first step
# How far the step chime rises, in semitones, between a unit's first step and
# its last. Lower is a slower climb; one octave keeps the final steps mellow.
CLIMB_SEMITONES = 12

STEP_HEADLINES = {
    "Build": "Built!",
    "Prime": "Primed!",
    "Base coat": "Base coat down!",
    "Metallics": "Metallics on!",
    "Wash": "Washed!",
    "Highlights": "Highlighted!",
    "Details & effects": "Details done!",
    "Basing": "Based!",
    "Varnish": "Varnished!",
}

CHEERS = [
    "The troop approves.",
    "Tail wag of approval!",
    "One more ring on the tail.",
    "That's worth a mango.",
    "Sunbathing-level satisfaction.",
    "Leap on to the next one!",
    "The conspiracy grows stronger.",
    "Ring by ring, it adds up.",
    "Top of the troop!",
    "Look at those rings!",
    "Happy lemur noises.",
    "Brush-tastic.",
]


def headline_for(step: str) -> str:
    return STEP_HEADLINES.get(step, f"{step} done!")


def cheer() -> str:
    return random.choice(CHEERS)


# ----- synthesis -------------------------------------------------------


def _tone(freq: float, duration: float, volume: float, chirp: float = 0.0, decay: float = 6.0) -> list[float]:
    """A bell-like note that starts with a quick upward chirp and fades out."""
    samples = []
    phase = 0.0
    for i in range(int(RATE * duration)):
        t = i / RATE
        # Start a little flat and glide up to pitch over 40 ms.
        f = freq * (1 - chirp * max(0.0, 1 - t / 0.04))
        phase += 2 * math.pi * f / RATE
        envelope = min(1.0, t / 0.005) * math.exp(-decay * t)
        wave_ = math.sin(phase) + 0.3 * math.sin(2 * phase) + 0.1 * math.sin(3 * phase)
        samples.append(volume * envelope * wave_ / 1.4)
    return samples


def _mix(parts: list[tuple[float, list[float]]]) -> list[float]:
    """Overlay (start time in seconds, samples) pieces into one track."""
    track = [0.0] * max(int(start * RATE) + len(samples) for start, samples in parts)
    for start, samples in parts:
        offset = int(start * RATE)
        for i, value in enumerate(samples):
            track[offset + i] += value
    return track


def _wav(samples: list[float]) -> bytes:
    scale = 32767 / max(1.0, max(abs(v) for v in samples))  # never clip where notes overlap
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(struct.pack(f"<{len(samples)}h", *(int(v * scale) for v in samples)))
    return buffer.getvalue()


def step_pitch(progress: float) -> float:
    """The chime's pitch in Hz for a unit this far along (0.0 to 1.0)."""
    return STEP_BASE_PITCH * 2 ** (min(max(progress, 0.0), 1.0) * CLIMB_SEMITONES / 12)


def step_chime(progress: float) -> bytes:
    """A two-note 'da-ding'; the further along the unit (0.0 to 1.0), the higher it rings."""
    note = step_pitch(progress)
    return _wav(
        _mix(
            [
                (0.0, _tone(note * 0.75, 0.12, 0.35, chirp=0.15, decay=18)),
                (0.07, _tone(note, 0.45, 0.5, chirp=0.1, decay=7)),
            ]
        )
    )


def unit_done_flourish() -> bytes:
    """A quick rising arpeggio."""
    notes = [1046.50, 1318.51, 1567.98, 2093.00]
    return _wav(_mix([(i * 0.08, _tone(f, 0.6, 0.4, chirp=0.05, decay=5)) for i, f in enumerate(notes)]))


def commission_fanfare() -> bytes:
    """Ta-ta-da-da-dah, then a ringing chord."""
    lead = [(0.0, 783.99), (0.12, 783.99), (0.24, 1046.50), (0.48, 1318.51), (0.6, 1046.50)]
    parts = [(start, _tone(f, 0.3, 0.4, decay=8)) for start, f in lead]
    parts += [(0.78, _tone(f, 1.2, 0.3, decay=2.5)) for f in (1046.50, 1318.51, 1567.98, 2093.00)]
    return _wav(_mix(parts))


# ----- playback --------------------------------------------------------


def _find_player() -> list[str] | None:
    """The command that plays a WAV file here, or None (Windows uses winsound instead)."""
    if sys.platform == "win32":
        return None
    if sys.platform == "darwin":
        return ["afplay"]
    for command in (["paplay"], ["pw-play"], ["aplay", "-q"]):
        if shutil.which(command[0]):
            return command
    return None


class SoundPlayer:
    """Plays reward sounds without blocking the window. Missing audio is never an error."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled
        self._command = _find_player()
        self._dir: Path | None = None
        self._files: dict[str, Path] = {}

    def play_step(self, progress: float) -> None:
        self._play(f"step{step_pitch(progress):.0f}", lambda: step_chime(progress))

    def play_unit_done(self) -> None:
        self._play("unit-done", unit_done_flourish)

    def play_commission_done(self) -> None:
        self._play("commission-done", commission_fanfare)

    def _file_for(self, name: str, render: Callable[[], bytes]) -> Path:
        if name not in self._files:
            if self._dir is None:
                self._dir = Path(tempfile.mkdtemp(prefix="lemur-tracker-sounds-"))
                atexit.register(shutil.rmtree, self._dir, ignore_errors=True)
            path = self._dir / f"{name}.wav"
            path.write_bytes(render())
            self._files[name] = path
        return self._files[name]

    def _play(self, name: str, render: Callable[[], bytes]) -> None:
        if not self.enabled:
            return
        try:
            path = self._file_for(name, render)
            if sys.platform == "win32":
                import winsound

                winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            elif self._command:
                subprocess.Popen(
                    [*self._command, str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
        except (OSError, RuntimeError):
            pass
