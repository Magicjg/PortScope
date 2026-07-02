from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from portscope.exporters import export_snapshot_csv_bundle, export_snapshot_json
from portscope.system_info import ModuleReadError, PortSnapshot, _run_powershell_json, collect_snapshot


class SystemInfoTests(unittest.TestCase):
    def test_run_powershell_json_raises_on_failure(self) -> None:
        with patch("portscope.system_info.subprocess.run") as mocked:
            mocked.return_value.returncode = 1
            mocked.return_value.stdout = ""
            mocked.return_value.stderr = "Get-PnpDevice unavailable"
            with self.assertRaises(ModuleReadError):
                _run_powershell_json("bad script")

    def test_collect_snapshot_surfaces_module_errors(self) -> None:
        with (
            patch("portscope.system_info.collect_usb_items", side_effect=ModuleReadError("usb caido")),
            patch("portscope.system_info.collect_net_items", return_value=[]),
            patch("portscope.system_info.collect_disk_items", return_value=[]),
        ):
            snapshot = collect_snapshot()
            self.assertTrue(snapshot.module_errors)
            self.assertEqual(snapshot.module_statuses[0]["estado"], "Error")

    def test_exporters_write_files(self) -> None:
        snapshot = PortSnapshot(
            usb_items=[{"nombre": "USB A"}],
            net_items=[{"nombre": "Ethernet"}],
            disk_items=[{"unidad": "D:\\"}],
            connected_items=[{"nombre": "Mouse"}],
            notes=["note"],
            alerts=["alert"],
            benchmark_targets=[{"label": "D", "path": "D:\\"}],
            summary_cards=[{"title": "USB", "value": "1", "caption": "ok"}],
            module_errors=[],
            module_statuses=[{"modulo": "USB", "estado": "OK", "detalle": "1 elemento"}],
        )
        with tempfile.TemporaryDirectory(prefix="portscope-export-") as tmp:
            json_path = Path(tmp) / "snapshot.json"
            export_snapshot_json(snapshot, str(json_path))
            self.assertTrue(json_path.exists())
            files = export_snapshot_csv_bundle(snapshot, tmp)
            self.assertTrue(any(Path(path).name == "usb.csv" for path in files))
