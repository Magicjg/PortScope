from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from portscope import history


class HistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="portscope-history-")
        self.tmp_path = Path(self.temp_dir.name)
        self.old_app_dir = history.APP_DIR
        self.old_history_file = history.HISTORY_FILE
        self.old_settings_file = history.SETTINGS_FILE
        history.APP_DIR = self.tmp_path
        history.HISTORY_FILE = self.tmp_path / "history.json"
        history.SETTINGS_FILE = self.tmp_path / "settings.json"

    def tearDown(self) -> None:
        history.APP_DIR = self.old_app_dir
        history.HISTORY_FILE = self.old_history_file
        history.SETTINGS_FILE = self.old_settings_file
        self.temp_dir.cleanup()

    def test_roundtrip_and_csv_export(self) -> None:
        entry = {
            "target": "X",
            "requested_target": "Y",
            "source_label": "USB Test",
            "file_size_mb": 64,
            "passes": 2,
            "write_avg_mb_s": 100.0,
            "read_avg_mb_s": 200.0,
            "write_best_mb_s": 110.0,
            "read_best_mb_s": 210.0,
            "write_worst_mb_s": 90.0,
            "read_worst_mb_s": 180.0,
            "free_space_before": "10 GB",
            "free_space_after": "9 GB",
        }
        history.append_history(entry)
        loaded = history.load_history()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["source_label"], "USB Test")

        csv_path = self.tmp_path / "history.csv"
        history.export_history_csv(loaded, str(csv_path))
        with csv_path.open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(rows[0]["requested_target"], "Y")

    def test_clear_history(self) -> None:
        history.append_history({"target": "X"})
        history.clear_history()
        self.assertEqual(history.load_history(), [])
