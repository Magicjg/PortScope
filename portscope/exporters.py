from __future__ import annotations

import csv
import json
from pathlib import Path

from .system_info import PortSnapshot


def export_snapshot_json(snapshot: PortSnapshot, target_path: str) -> None:
    payload = {
        "usb_items": snapshot.usb_items,
        "net_items": snapshot.net_items,
        "disk_items": snapshot.disk_items,
        "connected_items": snapshot.connected_items,
        "notes": snapshot.notes,
        "alerts": snapshot.alerts,
        "benchmark_targets": snapshot.benchmark_targets,
        "summary_cards": snapshot.summary_cards,
        "module_errors": snapshot.module_errors,
        "module_statuses": snapshot.module_statuses,
    }
    Path(target_path).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def export_snapshot_csv_bundle(snapshot: PortSnapshot, target_dir: str) -> list[str]:
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)

    exports = [
        ("usb.csv", snapshot.usb_items),
        ("red.csv", snapshot.net_items),
        ("unidades.csv", snapshot.disk_items),
        ("conectados.csv", snapshot.connected_items),
        ("estados_modulo.csv", snapshot.module_statuses),
    ]

    written_files: list[str] = []
    for filename, rows in exports:
        path = target / filename
        _write_rows_csv(path, rows)
        written_files.append(str(path))

    summary_path = target / "resumen.json"
    summary_path.write_text(
        json.dumps(
            {
                "notes": snapshot.notes,
                "alerts": snapshot.alerts,
                "summary_cards": snapshot.summary_cards,
                "module_errors": snapshot.module_errors,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    written_files.append(str(summary_path))
    return written_files


def _write_rows_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
