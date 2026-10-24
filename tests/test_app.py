"""Drive the real main window with the dialogs and message boxes stubbed out."""

import json
import tempfile
import time
import tkinter as tk
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from lemur_tracker.app import LemurTrackerApp
from lemur_tracker.dialogs import StepsDialog, UnitDialog
from lemur_tracker.models import BUILD_STEP, DEFAULT_PAINT_STEPS, DONE, DetailLevel, all_steps, paint_steps
from lemur_tracker.storage import load_data, load_settings, settings_path

PROJECT_VALUES = {
    "name": "Lemur Legion",
    "client_name": "Ari",
    "client_address": "1 Baobab Ave",
    "accepted_on": date(2026, 10, 1),
    "notes": "",
}
UNIT_VALUES = {
    "name": "Captain",
    "unit_type": "HQ",
    "model_count": 1,
    "detail_level": DetailLevel.SHOWCASE,
    "effects": ["OSL on sword"],
    "needs_building": True,
    "step": BUILD_STEP,
    "notes": "",
}


def dialog_returning(values):
    return mock.Mock(return_value=mock.Mock(show=mock.Mock(return_value=values)))


def run_for(root, seconds):
    """Let animations play."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        root.update()
        time.sleep(0.01)


def celebration_words(app):
    canvas = app._celebration
    return [canvas.itemcget(item, "text") for item in canvas.find_withtag("words")]


class AppTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"no display available: {exc}")
        self.root.withdraw()
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "commissions.json"
        patcher = mock.patch("lemur_tracker.app.messagebox")
        self.messagebox = patcher.start()
        self.messagebox.askyesno.return_value = True
        self.addCleanup(patcher.stop)
        # A real warning box would wait forever for a click.
        patcher = mock.patch("lemur_tracker.dialogs.messagebox")
        self.dialog_messagebox = patcher.start()
        self.addCleanup(patcher.stop)
        # Keep the tests quiet: a fake player that remembers what it was asked to play.
        patcher = mock.patch("lemur_tracker.app.SoundPlayer", side_effect=lambda enabled: mock.Mock(enabled=enabled))
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.root.destroy()
        self._tmp.cleanup()

    def make_app(self):
        app = LemurTrackerApp(self.root, self.path)
        self.root.update()
        return app

    def test_full_commission_lifecycle(self):
        app = self.make_app()
        self.assertEqual(app.empty_title.cget("text"), "Welcome to Lemur Tracker")

        with mock.patch("lemur_tracker.app.ProjectDialog", dialog_returning(PROJECT_VALUES)):
            app.new_project()
        project = app.selected_project
        self.assertEqual(project.name, "Lemur Legion")

        with mock.patch("lemur_tracker.app.UnitDialog", dialog_returning(UNIT_VALUES)):
            app.add_unit()
        unit = project.units[0]
        self.assertEqual(app.tree.selection(), (unit.id,))
        self.assertIn("disabled", app.back_button.state())

        app.next_step()
        self.assertEqual(unit.current_step, DEFAULT_PAINT_STEPS[0])
        self.assertEqual(app.d_tail._value, project.progress)
        self.assertNotIn("disabled", app.back_button.state())
        app.sound.play_step.assert_called_once()
        self.assertEqual(app._celebration.level, "step")
        self.assertEqual(celebration_words(app)[:2], ["Built!", "Captain · 1 model"])

        for _ in DEFAULT_PAINT_STEPS:
            app.next_step()
        self.assertTrue(project.is_complete)
        self.assertEqual(app.d_percent.cget("text"), "88%")  # counts up from the last step...
        run_for(self.root, 0.9)
        self.assertEqual(app.d_percent.cget("text"), "100%")  # ...and lands on the real figure
        self.assertEqual(app.d_tail._shown, 1.0)
        self.assertIn("disabled", app.next_button.state())
        app.sound.play_commission_done.assert_called_once()
        app.sound.play_unit_done.assert_not_called()  # the bigger party replaces it
        self.assertEqual(app._celebration.level, "commission")
        self.assertEqual(celebration_words(app)[:2], ["Tail complete!", "Lemur Legion"])
        self.messagebox.showinfo.assert_not_called()

        app._celebration.close()
        self.assertIsNone(app._celebration)

        app.toggle_delivered()
        self.assertTrue(project.delivered)
        self.assertNotIn(project, app._visible_projects())
        app.show_delivered_var.set(True)
        self.assertIn(project, app._visible_projects())

        self.assertEqual(load_data(self.path)[0], app.projects)

        app.remove_units()
        self.assertEqual(project.units, [])
        app.delete_project()
        self.assertEqual(app.projects, [])
        self.assertEqual(load_data(self.path)[0], [])

    def test_next_step_moves_each_selected_unit_as_a_batch(self):
        app = self.make_app()
        with mock.patch("lemur_tracker.app.ProjectDialog", dialog_returning(PROJECT_VALUES)):
            app.new_project()
        squads = [
            {**UNIT_VALUES, "name": "Squad A", "model_count": 10},
            {**UNIT_VALUES, "name": "Squad B", "model_count": 10, "needs_building": False, "step": "Wash"},
            {**UNIT_VALUES, "name": "Captain"},
        ]
        for values in squads:
            with mock.patch("lemur_tracker.app.UnitDialog", dialog_returning(values)):
                app.add_unit()
        squad_a, squad_b, captain = app.selected_project.units
        app.tree.selection_set(squad_a.id, squad_b.id)
        app.root.update()

        app.next_step()
        self.assertEqual(squad_a.current_step, "Prime")
        self.assertEqual(squad_b.current_step, "Highlights")
        self.assertEqual(captain.current_step, BUILD_STEP)
        self.assertEqual(app.tree.selection(), (squad_a.id, squad_b.id))
        self.assertEqual(app.status.cget("text"), "2 units are now on their next steps.")
        self.assertEqual(celebration_words(app)[:2], ["Steps done!", "2 units · 20 models"])
        self.assertEqual(celebration_words(app)[3], "2 steps this session")
        # The chime pitches to whichever unit is furthest along.
        app.sound.play_step.assert_called_once_with(squad_b.steps_done / len(squad_b.steps))

        counts = {step: label.cget("text") for step, (_, _, label) in app.d_steps.items()}
        self.assertEqual(counts[BUILD_STEP], "1")
        self.assertEqual(counts["Prime"], "10")
        self.assertEqual(counts["Highlights"], "10")
        self.assertEqual(counts[DONE], "–")

    def test_finishing_a_unit_gets_a_bigger_reward_and_step_back_gets_none(self):
        app = self.make_app()
        with mock.patch("lemur_tracker.app.ProjectDialog", dialog_returning(PROJECT_VALUES)):
            app.new_project()
        for values in ({**UNIT_VALUES, "step": DEFAULT_PAINT_STEPS[-1]}, {**UNIT_VALUES, "name": "Squad"}):
            with mock.patch("lemur_tracker.app.UnitDialog", dialog_returning(values)):
                app.add_unit()
        captain = app.selected_project.units[0]
        app.tree.selection_set(captain.id)
        app.root.update()

        app.next_step()
        self.assertTrue(captain.is_done)
        app.sound.play_unit_done.assert_called_once()
        self.assertEqual(app._celebration.level, "unit")
        self.assertEqual(celebration_words(app)[0], "Unit finished!")

        app._celebration.close()
        app.step_back()
        self.assertIsNone(app._celebration)
        app.sound.play_step.assert_not_called()

    def test_sound_setting_is_remembered(self):
        app = self.make_app()
        self.assertTrue(app.sound_var.get())
        app.sound_var.set(False)
        app._toggle_sound()
        self.assertFalse(app.sound.enabled)
        self.assertEqual(load_settings(settings_path(self.path)), {"sound": False})

        other_root = tk.Tk()
        other_root.withdraw()
        self.addCleanup(other_root.destroy)
        self.assertFalse(LemurTrackerApp(other_root, self.path).sound_var.get())

    def test_editing_steps_moves_units_and_rebuilds_the_strip(self):
        app = self.make_app()
        with mock.patch("lemur_tracker.app.ProjectDialog", dialog_returning(PROJECT_VALUES)):
            app.new_project()
        for values in ({**UNIT_VALUES, "name": "On wash", "model_count": 5, "step": "Wash"},
                       {**UNIT_VALUES, "name": "On metallics", "step": "Metallics"}):
            with mock.patch("lemur_tracker.app.UnitDialog", dialog_returning(values)):
                app.add_unit()
        on_wash, on_metallics = app.selected_project.units

        # Drop Wash, rename Metallics, and add a Glaze step after Highlights.
        rows = []
        for step in DEFAULT_PAINT_STEPS:
            if step == "Wash":
                continue
            rows.append((step, "Metals" if step == "Metallics" else step))
            if step == "Highlights":
                rows.append((None, "Glaze"))
        with mock.patch("lemur_tracker.app.StepsDialog", dialog_returning({"rows": rows})):
            app.edit_steps()

        question = self.messagebox.askyesno.call_args.args[1]
        self.assertIn("5 models on Wash will move on to Highlights", question)
        self.assertEqual(on_wash.current_step, "Highlights")
        self.assertEqual(on_metallics.current_step, "Metals")
        self.assertEqual(list(app.d_steps), all_steps())
        self.assertIn("Glaze", app.d_steps)
        self.assertEqual(load_data(self.path)[1], paint_steps())

    def test_cancelling_the_move_warning_changes_nothing(self):
        app = self.make_app()
        with mock.patch("lemur_tracker.app.ProjectDialog", dialog_returning(PROJECT_VALUES)):
            app.new_project()
        with mock.patch("lemur_tracker.app.UnitDialog", dialog_returning({**UNIT_VALUES, "step": "Wash"})):
            app.add_unit()
        self.messagebox.askyesno.return_value = False
        rows = [(step, step) for step in DEFAULT_PAINT_STEPS if step != "Wash"]
        with mock.patch("lemur_tracker.app.StepsDialog", dialog_returning({"rows": rows})):
            app.edit_steps()
        self.assertEqual(paint_steps(), list(DEFAULT_PAINT_STEPS))
        self.assertEqual(app.selected_project.units[0].step, "Wash")

    def test_steps_dialog_edits(self):
        app = self.make_app()
        with mock.patch("lemur_tracker.dialogs.messagebox") as dialog_messages:
            dialog = StepsDialog(self.root, app.fonts, {"Wash": 12})
            self.assertIn("Wash   ·   12 models here", dialog.listbox.get(0, "end"))

            def pick(index):
                dialog.listbox.selection_clear(0, "end")
                dialog.listbox.selection_set(index)
                dialog._on_select(None)

            pick(0)
            self.assertEqual(dialog.name_var.get(), "Prime")
            dialog.name_var.set("Undercoat")
            dialog._rename()
            dialog.name_var.set("Contrast")
            dialog._add()  # goes in after the selected step
            dialog._move_down()
            pick(len(dialog.rows) - 1)
            dialog._remove()
            names = [name for _old, name in dialog.rows]
            self.assertEqual(names[:3], ["Undercoat", "Base coat", "Contrast"])
            self.assertNotIn("Varnish", names)
            self.assertEqual(dialog.rows[0], ("Prime", "Undercoat"))
            self.assertEqual(dialog.rows[2], (None, "Contrast"))

            dialog.name_var.set("Done")
            dialog._add()
            dialog_messages.showwarning.assert_called_once()
            self.assertNotIn("Done", [name for _old, name in dialog.rows])

            dialog._reset()
            self.assertEqual(dialog._collect(), {"rows": [(s, s) for s in DEFAULT_PAINT_STEPS]})

    def test_new_unit_count_follows_its_type_until_changed_by_hand(self):
        app = self.make_app()
        dialog = UnitDialog(self.root, app.fonts)
        dialog.name_var.set("Custodian Guard")
        self.assertEqual(dialog.count_var.get(), "10")  # a new unit starts as a Squad
        self.assertEqual(dialog.count_hint.cget("text"), "usual size for this type")
        dialog.type_var.set("HQ")
        self.assertEqual(dialog.count_var.get(), "1")
        for partial in ("K", "Kn", "Knight"):  # typing a custom type changes nothing
            dialog.type_var.set(partial)
        self.assertEqual(dialog.count_var.get(), "1")
        self.assertEqual(dialog.count_hint.cget("text"), "")
        dialog.type_var.set("Elites")
        self.assertEqual(dialog.count_var.get(), "5")

        dialog.count_var.set("7")
        self.assertEqual(dialog.count_hint.cget("text"), "")
        dialog.type_var.set("Battleline")
        self.assertEqual(dialog.count_var.get(), "7")
        self.assertEqual(dialog._collect()["model_count"], 7)
        self.dialog_messagebox.showwarning.assert_not_called()

    def test_editing_a_unit_never_changes_its_count(self):
        from lemur_tracker.models import Unit

        app = self.make_app()
        dialog = UnitDialog(self.root, app.fonts, Unit(name="Rhino", unit_type="Squad", model_count=10))
        dialog.type_var.set("Vehicle")
        self.assertEqual(dialog.count_var.get(), "10")
        self.assertEqual(dialog.count_hint.cget("text"), "")

    def test_unreadable_file_is_kept_and_app_starts_empty(self):
        self.path.write_text("{oops", encoding="utf-8")
        app = self.make_app()
        self.assertEqual(app.projects, [])
        self.messagebox.showwarning.assert_called_once()
        kept = list(self.path.parent.glob("commissions.json.unreadable-*"))
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].read_text(encoding="utf-8"), "{oops")

    def test_search_filters_by_project_or_client(self):
        self.path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "projects": [
                        {"name": "Ork Warboss", "client_name": "Jordan", "accepted_on": "2026-10-01"},
                        {"name": "Necron Patrol", "client_name": "Alex", "accepted_on": "2026-09-01"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        app = self.make_app()
        self.assertEqual([p.name for p in app._visible_projects()], ["Necron Patrol", "Ork Warboss"])
        app.search_var.set("jordan")
        self.assertEqual([p.name for p in app._visible_projects()], ["Ork Warboss"])


if __name__ == "__main__":
    unittest.main()
