from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path
from statistics import mean
from typing import Any

from .logger import log_event

DEFAULT_FILE_SIZE_MB = 256
DEFAULT_PASSES = 2
CHUNK_SIZE = 4 * 1024 * 1024
BENCHMARK_FOLDER_NAME = "PortScope Benchmark"


class BenchmarkCancelled(RuntimeError):
    pass


def _prepare_benchmark_directory(target_dir: str) -> tuple[Path, str]:
    requested = Path(target_dir).resolve()
    base_name = requested.drive.rstrip(":") or requested.name or "target"

    if requested == Path(requested.anchor):
        system_drive = (os.environ.get("SystemDrive") or "").rstrip(":\\").upper()
        requested_drive = requested.drive.rstrip(":").upper()
        if requested_drive and requested_drive == system_drive:
            working = Path.home() / BENCHMARK_FOLDER_NAME / f"{requested_drive}-drive"
        else:
            working = requested / BENCHMARK_FOLDER_NAME
    else:
        working = requested / BENCHMARK_FOLDER_NAME

    working.mkdir(parents=True, exist_ok=True)
    return working, str(requested)


def _ensure_not_cancelled(cancel_check=None) -> None:
    if cancel_check and cancel_check():
        raise BenchmarkCancelled("Benchmark cancelado por el usuario.")


def validate_benchmark_target(target_dir: str) -> Path:
    target = Path(target_dir).expanduser().resolve()
    if not target.exists():
        raise RuntimeError("La ruta seleccionada no existe.")
    if not target.is_dir():
        raise RuntimeError("La ruta seleccionada no es una carpeta valida.")
    return target


def _measure_once(
    target_dir: Path,
    total_bytes: int,
    pass_index: int,
    progress_callback=None,
    cancel_check=None,
) -> dict[str, float]:
    payload = os.urandom(min(CHUNK_SIZE, total_bytes))
    transferred = 0
    temp_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            prefix=f"portscope-benchmark-{pass_index}-",
            suffix=".bin",
            dir=target_dir,
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            write_start = time.perf_counter()
            while transferred < total_bytes:
                _ensure_not_cancelled(cancel_check)
                remaining = total_bytes - transferred
                chunk = payload if remaining >= len(payload) else payload[:remaining]
                temp_file.write(chunk)
                transferred += len(chunk)
                if progress_callback:
                    progress_callback("write", pass_index, transferred / total_bytes)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            write_end = time.perf_counter()

        write_seconds = max(write_end - write_start, 0.001)
        write_speed = (total_bytes / 1024 / 1024) / write_seconds

        read_total = 0
        read_start = time.perf_counter()
        with open(temp_path, "rb") as handle:
            while True:
                _ensure_not_cancelled(cancel_check)
                chunk = handle.read(CHUNK_SIZE)
                if not chunk:
                    break
                read_total += len(chunk)
                if progress_callback:
                    progress_callback("read", pass_index, read_total / total_bytes)
        read_end = time.perf_counter()

        read_seconds = max(read_end - read_start, 0.001)
        read_speed = (read_total / 1024 / 1024) / read_seconds
        return {
            "write_seconds": round(write_seconds, 3),
            "read_seconds": round(read_seconds, 3),
            "write_speed_mb_s": round(write_speed, 2),
            "read_speed_mb_s": round(read_speed, 2),
        }
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def _free_space(path: Path) -> int:
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return 0


def _format_bytes(value: int) -> str:
    size = float(value)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return "0 B"


def _cleanup_working_directory(directory: Path) -> None:
    try:
        next(directory.iterdir())
    except StopIteration:
        try:
            directory.rmdir()
        except OSError:
            pass
    except OSError:
        pass


def run_storage_benchmark(
    target_dir: str,
    file_size_mb: int = DEFAULT_FILE_SIZE_MB,
    passes: int = DEFAULT_PASSES,
    progress_callback=None,
    cancel_check=None,
    source_label: str = "",
) -> dict[str, Any]:
    requested_path = validate_benchmark_target(target_dir)
    _ensure_not_cancelled(cancel_check)
    directory, requested_target = _prepare_benchmark_directory(target_dir)

    file_size_mb = max(16, int(file_size_mb))
    passes = max(1, int(passes))
    total_bytes = file_size_mb * 1024 * 1024
    free_before = _free_space(directory)
    required_bytes = total_bytes + (64 * 1024 * 1024)
    if free_before and free_before < required_bytes:
        raise RuntimeError("No hay espacio suficiente para ejecutar la prueba en esa ubicacion.")

    log_event(
        "benchmark_started",
        requested_target=requested_target,
        benchmark_folder=str(directory),
        source_label=source_label,
        file_size_mb=file_size_mb,
        passes=passes,
        drive=requested_path.drive,
    )

    per_pass = []
    try:
        for pass_index in range(1, passes + 1):
            _ensure_not_cancelled(cancel_check)
            per_pass.append(
                _measure_once(
                    directory,
                    total_bytes,
                    pass_index,
                    progress_callback,
                    cancel_check,
                )
            )

        free_after = _free_space(directory)
        write_values = [item["write_speed_mb_s"] for item in per_pass]
        read_values = [item["read_speed_mb_s"] for item in per_pass]
        result = {
            "target": str(directory),
            "requested_target": requested_target,
            "source_label": source_label or requested_target,
            "file_size_mb": file_size_mb,
            "passes": passes,
            "per_pass": per_pass,
            "write_avg_mb_s": round(mean(write_values), 2),
            "read_avg_mb_s": round(mean(read_values), 2),
            "write_best_mb_s": round(max(write_values), 2),
            "read_best_mb_s": round(max(read_values), 2),
            "write_worst_mb_s": round(min(write_values), 2),
            "read_worst_mb_s": round(min(read_values), 2),
            "free_space_before": _format_bytes(free_before),
            "free_space_after": _format_bytes(free_after),
        }
        log_event(
            "benchmark_completed",
            requested_target=requested_target,
            source_label=result["source_label"],
            write_avg_mb_s=result["write_avg_mb_s"],
            read_avg_mb_s=result["read_avg_mb_s"],
        )
        return result
    except BenchmarkCancelled:
        log_event(
            "benchmark_cancelled",
            requested_target=requested_target,
            source_label=source_label or requested_target,
        )
        raise
    except Exception as exc:
        log_event(
            "benchmark_failed",
            requested_target=requested_target,
            source_label=source_label or requested_target,
            error=str(exc),
        )
        raise
    finally:
        _cleanup_working_directory(directory)
