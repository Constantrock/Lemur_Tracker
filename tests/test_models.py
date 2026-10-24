import unittest
from datetime import date

from lemur_tracker.models import (
    BUILD_STEP,
    DONE,
    DEFAULT_PAINT_STEPS,
    PHASE_BUILDING,
    PHASE_DONE,
    DetailLevel,
    Project,
    Unit,
    all_steps,
    change_paint_steps,
    paint_steps,
    parse_effects,
    set_paint_steps,
    step_destinations,
    step_list_problem,
    typical_model_count,
    UNIT_TYPES,
)


class DetailLevelTests(unittest.TestCase):
    def test_levels_ordered_lowest_to_highest(self):
        self.assertEqual(
            [level.value for level in DetailLevel], ["Battle Ready", "Parade", "Showcase"]
        )
        self.assertEqual([level.rank for level in DetailLevel], [1, 2, 3])

    def test_pips(self):
        self.assertEqual(DetailLevel.BATTLE_READY.pips, "●○○")
        self.assertEqual(DetailLevel.SHOWCASE.pips, "●●●")


class UnitTests(unittest.TestCase):
    def test_new_unit_starts_at_build(self):
        unit = Unit(name="Intercessors")
        self.assertEqual(unit.current_step, BUILD_STEP)
        self.assertEqual(unit.phase, PHASE_BUILDING)
        self.assertEqual(unit.steps, [BUILD_STEP, *DEFAULT_PAINT_STEPS])

    def test_ready_built_unit_starts_at_first_paint_step(self):
        unit = Unit(name="Captain", needs_building=False)
        self.assertEqual(unit.current_step, DEFAULT_PAINT_STEPS[0])
        self.assertEqual((unit.steps_done, len(unit.steps)), (0, len(DEFAULT_PAINT_STEPS)))

    def test_advance_walks_every_step_then_stops_at_done(self):
        unit = Unit(name="Squad")
        visited = []
        for _ in range(len(unit.steps) + 2):
            visited.append(unit.current_step)
            unit.advance()
        self.assertEqual(visited, [BUILD_STEP, *DEFAULT_PAINT_STEPS, DONE, DONE])
        self.assertTrue(unit.is_done)
        self.assertEqual(unit.phase, PHASE_DONE)

    def test_step_back_stops_at_first_step(self):
        unit = Unit(name="Squad", step=DONE)
        unit.step_back()
        self.assertEqual(unit.current_step, DEFAULT_PAINT_STEPS[-1])
        unit.step = DEFAULT_PAINT_STEPS[0]
        unit.step_back()
        self.assertEqual(unit.current_step, BUILD_STEP)
        unit.step_back()
        self.assertEqual(unit.current_step, BUILD_STEP)

    def test_switching_off_building_keeps_painting_step(self):
        unit = Unit(name="Squad", step="Metallics")
        self.assertEqual(unit.steps_done, 3)
        unit.needs_building = False
        self.assertEqual(unit.current_step, "Metallics")
        self.assertEqual(unit.steps_done, 2)

    def test_round_trip(self):
        unit = Unit(
            name="Captain",
            unit_type="HQ",
            model_count=1,
            detail_level=DetailLevel.SHOWCASE,
            effects=["OSL on power sword"],
            needs_building=False,
            step="Highlights",
            notes="Gold trim",
        )
        self.assertEqual(Unit.from_dict(unit.to_dict()), unit)

    def test_from_dict_fills_defaults(self):
        unit = Unit.from_dict({"name": "Rhino"})
        self.assertEqual(unit.detail_level, DetailLevel.BATTLE_READY)
        self.assertEqual(unit.model_count, 1)
        self.assertTrue(unit.needs_building)
        self.assertEqual(unit.current_step, BUILD_STEP)
        self.assertTrue(unit.id)


class ProjectTests(unittest.TestCase):
    def test_empty_project_has_no_progress(self):
        project = Project(name="Empty")
        self.assertEqual(project.progress, 0.0)
        self.assertEqual(project.percent, 0)
        self.assertFalse(project.is_complete)

    def test_progress_weighted_by_model_count(self):
        squad = Unit(name="Squad", model_count=10, step=DEFAULT_PAINT_STEPS[0])  # built: 1 of 9 steps
        hq = Unit(name="HQ", model_count=1, needs_building=False)  # 0 of 8 steps
        project = Project(name="Army", units=[squad, hq])
        self.assertAlmostEqual(project.progress, 10 / 98)
        self.assertEqual(project.percent, 10)

    def test_percent_rounds_down_and_only_hits_100_when_done(self):
        units = [Unit(name=f"U{i}", needs_building=False, step=DONE) for i in range(199)]
        last = Unit(name="Last", needs_building=False, step=DEFAULT_PAINT_STEPS[-1])
        project = Project(name="Horde", units=[*units, last])
        self.assertEqual(project.percent, 99)
        self.assertFalse(project.is_complete)
        last.advance()
        self.assertEqual(project.percent, 100)
        self.assertTrue(project.is_complete)

    def test_percent_avoids_float_error(self):
        units = [Unit(name=f"U{i}", needs_building=False, step=DONE if i < 29 else "Prime") for i in range(100)]
        self.assertEqual(Project(name="P", units=units).percent, 29)

    def test_step_and_detail_counts(self):
        project = Project(
            name="Army",
            units=[
                Unit(name="A", model_count=5, detail_level=DetailLevel.PARADE),
                Unit(name="B", needs_building=False, step="Metallics", detail_level=DetailLevel.SHOWCASE),
                Unit(name="C", model_count=3, step=DONE),
            ],
        )
        counts = project.step_counts()
        self.assertEqual(list(counts), all_steps())
        self.assertEqual({step: n for step, n in counts.items() if n}, {BUILD_STEP: 5, "Metallics": 1, DONE: 3})
        self.assertEqual(
            project.detail_counts(),
            {DetailLevel.BATTLE_READY: 3, DetailLevel.PARADE: 5, DetailLevel.SHOWCASE: 1},
        )
        self.assertEqual(project.model_count, 9)

    def test_days_since_accepted(self):
        project = Project(name="P", accepted_on=date(2026, 10, 1))
        self.assertEqual(project.days_since_accepted(today=date(2026, 10, 23)), 22)

    def test_round_trip(self):
        project = Project(
            name="Ultramarines strike force",
            client_name="Sam Rivera",
            client_address="12 Ring Tail Lane\nAntananarivo",
            accepted_on=date(2026, 9, 14),
            notes="Wants blue to match the codex",
            delivered=True,
            units=[Unit(name="Captain", unit_type="HQ", step="Wash"), Unit(name="Rhino", unit_type="Vehicle")],
        )
        self.assertEqual(Project.from_dict(project.to_dict()), project)


class EditableStepsTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(set_paint_steps, list(DEFAULT_PAINT_STEPS))
        set_paint_steps(["Prime", "Base", "Wash", "Varnish"])

    def army(self):
        units = [Unit(name=step, step=step) for step in ["Build", "Prime", "Base", "Wash", "Varnish", "Done"]]
        return Project(name="Army", units=units), {u.name: u for u in units}

    def test_problems(self):
        self.assertIsNone(step_list_problem(["Prime", "Glaze"]))
        self.assertEqual(step_list_problem([]), "Keep at least one painting step.")
        self.assertIn("twice", step_list_problem(["Prime", "prime"]))
        self.assertIn("built in", step_list_problem(["Prime", "done"]))
        self.assertIn("blank", step_list_problem(["Prime", ""]))
        self.assertIn("blank", step_list_problem([" Prime"]))
        with self.assertRaises(ValueError):
            set_paint_steps(["Build"])
        self.assertEqual(paint_steps(), ["Prime", "Base", "Wash", "Varnish"])

    def test_units_follow_a_rename_and_keep_their_progress(self):
        project, units = self.army()
        change_paint_steps([project], [("Prime", "Prime"), ("Base", "Base coat"), ("Wash", "Wash"), ("Varnish", "Varnish")])
        self.assertEqual(units["Base"].current_step, "Base coat")
        self.assertEqual(units["Base"].steps_done, 2)
        self.assertEqual(all_steps(), ["Build", "Prime", "Base coat", "Wash", "Varnish", "Done"])

    def test_units_on_a_removed_step_move_on(self):
        project, units = self.army()
        change_paint_steps([project], [("Prime", "Prime"), ("Varnish", "Varnish")])
        self.assertEqual(units["Base"].current_step, "Varnish")
        self.assertEqual(units["Wash"].current_step, "Varnish")
        self.assertEqual(units["Prime"].current_step, "Prime")
        self.assertEqual(units["Build"].current_step, "Build")
        self.assertTrue(units["Done"].is_done)

    def test_removing_the_last_step_finishes_units_on_it(self):
        project, units = self.army()
        change_paint_steps([project], [("Prime", "Prime"), ("Base", "Base"), ("Wash", "Wash")])
        self.assertTrue(units["Varnish"].is_done)

    def test_added_steps_count_as_done_for_units_already_past_them(self):
        project, units = self.army()
        change_paint_steps(
            [project], [("Prime", "Prime"), (None, "Contrast"), ("Base", "Base"), ("Wash", "Wash"), ("Varnish", "Varnish")]
        )
        self.assertEqual(units["Wash"].steps_done, 4)  # Build, Prime, Contrast, Base
        self.assertEqual(units["Prime"].steps_done, 1)

    def test_swapping_names_and_reusing_a_removed_name(self):
        self.assertEqual(
            step_destinations([("Base", "Prime"), ("Prime", "Base"), ("Wash", "Wash"), ("Varnish", "Varnish")]),
            {"Prime": "Base", "Base": "Prime", "Wash": "Wash", "Varnish": "Varnish"},
        )
        # Wash is removed and Prime takes its name: units on the old Wash still move on, not back.
        destinations = step_destinations([("Prime", "Wash"), ("Base", "Base"), ("Varnish", "Varnish")])
        self.assertEqual(destinations["Wash"], "Varnish")
        self.assertEqual(destinations["Prime"], "Wash")

    def test_invalid_change_leaves_everything_alone(self):
        project, units = self.army()
        with self.assertRaises(ValueError):
            change_paint_steps([project], [("Prime", "Done")])
        self.assertEqual(units["Prime"].step, "Prime")
        self.assertEqual(paint_steps(), ["Prime", "Base", "Wash", "Varnish"])


class TypicalModelCountTests(unittest.TestCase):
    def test_counts_by_type(self):
        self.assertEqual(typical_model_count("HQ"), 1)
        self.assertEqual(typical_model_count(" battleline "), 10)
        self.assertEqual(typical_model_count("Elites"), 5)
        self.assertEqual(typical_model_count("Vehicle"), 1)
        self.assertIsNone(typical_model_count("Imperial Knight"))

    def test_every_suggested_type_has_a_count(self):
        for unit_type in UNIT_TYPES:
            self.assertGreaterEqual(typical_model_count(unit_type), 1)


class ParseEffectsTests(unittest.TestCase):
    def test_splits_trims_and_dedupes(self):
        self.assertEqual(
            parse_effects(" OSL on sword, , NMM armour,osl on sword ,Freehand banner"),
            ["OSL on sword", "NMM armour", "Freehand banner"],
        )

    def test_empty(self):
        self.assertEqual(parse_effects("  "), [])


if __name__ == "__main__":
    unittest.main()
