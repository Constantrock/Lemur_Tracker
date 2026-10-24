import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from lemur_tracker.models import DEFAULT_PAINT_STEPS, DetailLevel, Project, Unit
from lemur_tracker.storage import (
    DATA_ENV_VAR,
    default_data_path,
    load_data,
    quarantine,
    save_data,
)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.path = self.dir / "nested" / "commissions.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_file_means_no_projects(self):
        self.assertEqual(load_data(self.path), ([], list(DEFAULT_PAINT_STEPS)))

    def test_save_then_load(self):
        projects = [
            Project(
                name="Lemur Legion",
                client_name="Ari",
                accepted_on=date(2026, 10, 1),
                units=[Unit(name="Captain", detail_level=DetailLevel.SHOWCASE, effects=["OSL – sword"])],
            )
        ]
        save_data(self.path, projects, ["Prime", "Glaze"])
        self.assertEqual(load_data(self.path), (projects, ["Prime", "Glaze"]))
        self.assertFalse(self.path.with_name(self.path.name + ".tmp").exists())
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["version"], 1)

    def test_corrupt_file_raises(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_data(self.path)

    def test_wrong_shape_raises(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("[1, 2, 3]", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_data(self.path)

    def test_damaged_step_list_falls_back_to_defaults(self):
        self.path.parent.mkdir(parents=True)
        for steps in ([], ["Prime", "Prime"], "Prime", [1, 2], None):
            self.path.write_text(json.dumps({"paint_steps": steps, "projects": []}), encoding="utf-8")
            self.assertEqual(load_data(self.path)[1], list(DEFAULT_PAINT_STEPS))

    def test_quarantine_moves_file_aside(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("garbage", encoding="utf-8")
        moved = quarantine(self.path)
        self.assertFalse(self.path.exists())
        self.assertEqual(moved.read_text(encoding="utf-8"), "garbage")

    def test_env_var_overrides_data_path(self):
        with mock.patch.dict(os.environ, {DATA_ENV_VAR: str(self.path)}):
            self.assertEqual(default_data_path(), self.path)

    def test_default_path_on_linux(self):
        env = {k: v for k, v in os.environ.items() if k not in (DATA_ENV_VAR, "XDG_DATA_HOME")}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch("sys.platform", "linux"):
            self.assertEqual(
                default_data_path(), Path.home() / ".local" / "share" / "LemurTracker" / "commissions.json"
            )


if __name__ == "__main__":
    unittest.main()
