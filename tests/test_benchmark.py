from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from portscope.benchmark import BenchmarkCancelled, run_storage_benchmark, validate_benchmark_target


class BenchmarkTests(unittest.TestCase):
    def test_validate_benchmark_target_rejects_missing_path(self) -> None:
        missing = str(Path(tempfile.gettempdir()) / "portscope-missing-target-001")
        with self.assertRaises(RuntimeError):
            validate_benchmark_target(missing)

    def test_benchmark_cleans_up_after_success(self) -> None:
        with tempfile.TemporaryDirectory(prefix="portscope-bench-") as tmp:
            result = run_storage_benchmark(tmp, file_size_mb=16, passes=1, source_label="test")
            self.assertEqual(result["passes"], 1)
            self.assertFalse(Path(result["target"]).exists())

    def test_benchmark_cleans_up_after_cancel(self) -> None:
        with tempfile.TemporaryDirectory(prefix="portscope-cancel-") as tmp:
            state = {"ticks": 0}

            def progress(_stage: str, _pass_index: int, _fraction: float) -> None:
                state["ticks"] += 1

            def cancel_check() -> bool:
                return state["ticks"] >= 2

            with self.assertRaises(BenchmarkCancelled):
                run_storage_benchmark(
                    tmp,
                    file_size_mb=16,
                    passes=1,
                    progress_callback=progress,
                    cancel_check=cancel_check,
                    source_label="cancel",
                )
            self.assertFalse((Path(tmp) / "PortScope Benchmark").exists())
