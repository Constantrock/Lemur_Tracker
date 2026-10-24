# Lemur Tracker

A desktop app for tracking miniature painting commissions, from a single HQ
model up to a whole Warhammer 40k army.

Each commission records:

- the commission name, the client's name and address, and the date it was accepted
- its units (HQ, squad, vehicle, and so on), each with a model count, a detail
  level (Battle Ready, Parade or Showcase), any special painting effects (for
  example "OSL on power sword"), and the step the unit is on

The left side of the window lists every active commission with its progress.
The right side shows the selected commission's plan.

## Running it

You need Python 3.10 or newer with Tkinter. Nothing else needs installing.

```bash
python3 run.py            # or: python3 -m lemur_tracker
```

On Ubuntu/Debian, if Tkinter is missing: `sudo apt install python3-tk`.
The python.org Windows installer includes Tkinter.

## Using it

- **New commission** (or Ctrl+N) adds a commission. **Edit details** changes it.
- **+ Add unit** adds a unit. Double-click a unit to edit it, or to jump it
  straight to any step.
- A new unit's model count starts at the usual 40k size for its type: 1 for
  HQ, Character, Vehicle, Monster, Dedicated Transport, Fortification and
  Other; 5 for Elites, Fast Attack and Heavy Support; 10 for Squad and
  Battleline. It follows the type until you type your own number. Editing an
  existing unit never changes its count. The sizes are in `UNIT_TYPE_MODELS`
  in `lemur_tracker/models.py`.
- Models are batch-painted, so every model in a unit is on the same step. By
  default units go through these steps:

  Build → Prime → Base coat → Metallics → Wash → Highlights → Details & effects → Basing → Varnish → Done

- Select one or more units and click **Next step** to move them all on together.
  **Step back** undoes a step.
- Untick **Needs building** for models that arrive already assembled. They
  start at Prime.
- The "Models on each step" strip shows where the whole commission stands.
- Click **Edit steps** above the strip (or File → Painting steps…) to add,
  rename, remove or reorder the painting steps. Units on a renamed step follow
  the new name. Units on a removed step move on to the next step, and the app
  asks before moving them. Build always comes first and Done always comes last.
- **Mark delivered** hides a finished commission. Tick **Show delivered** to
  see delivered commissions again.

### How progress is counted

Each finished step counts once for every model in the unit. So moving a
10-model squad on a step adds more progress than moving a single HQ on a step.
The percentage rounds down, so 100% only appears when everything is done.

The progress bar is a ring-tailed lemur's tail. Black and white rings fill in
as steps are finished. The grey part is still bare plastic.

### Rewards

Every **Next step** earns an instant reward, so small wins feel like wins:

- a chirpy chime whose pitch climbs as the unit gets closer to done
- a card where the lemur pops up wagging its ringed tail, with confetti, a
  headline for the step just finished ("Primed!"), a random cheer, and a
  running count of steps this session
- the progress tail grows with sparkles, and the step boxes the models just
  moved into flash

Finishing a unit gets a bigger flourish. Finishing a whole commission gets a
fanfare and a full-size party. Rewards never block anything: they clear
themselves after a few seconds, or you can click one away. **Step back** stays
quiet.

Untick **Sound effects** in the header to mute the chimes. The setting is
remembered.

## Where data is saved

| Platform | File |
| --- | --- |
| Windows | `%APPDATA%\LemurTracker\commissions.json` |
| Linux | `~/.local/share/LemurTracker/commissions.json` |

The painting step list is saved in the same file. The sound setting is kept in
`settings.json` in the same folder.

Set the `LEMUR_TRACKER_DATA` environment variable to use a different file, for
example a sample or test file. Saves are atomic, so a crash mid-save can't
truncate the file. If the file ever can't be read, the app moves it aside as
`commissions.json.unreadable-<timestamp>` instead of overwriting it.

## Tests

```bash
python3 -m unittest -v
```

The GUI tests in `tests/test_app.py` open a hidden Tk window. They skip
themselves when no display is available.

## Building a Windows app (later)

Not tried yet. On a Windows machine with Python installed, the usual route is:

```bat
pip install pyinstaller
pyinstaller --windowed --onefile --name "Lemur Tracker" run.py
```

This should produce `dist\Lemur Tracker.exe`.

## Code layout

| File | Contents |
| --- | --- |
| `lemur_tracker/models.py` | Commissions, units, painting steps, detail levels, progress maths |
| `lemur_tracker/storage.py` | JSON load and save, data file location |
| `lemur_tracker/app.py` | Main window |
| `lemur_tracker/dialogs.py` | Add and edit forms |
| `lemur_tracker/rewards.py` | Reward chimes (generated in code, no audio files), cheers, playback |
| `lemur_tracker/widgets.py` | Tail progress bar, lemur drawing, celebration cards, scrolling list |
| `lemur_tracker/theme.py` | The look (dark academia and goth in purple, Palatino headings), styles, lemur facts |
