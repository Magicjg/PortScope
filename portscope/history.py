from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

APP_DIR = Path.home() / ".portscope"
HISTORY_FILE = APP_DIR / "history.json"
SETTINGS_FILE = APP_DIR / "settings.json"


def ensure_app_dir() -> Path:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    return APP_DIR


def load_history() -> list[dict[str, Any]]:
    ensure_app_dir()
    if not HISTORY_FILE.exists():
        return []
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def save_history(entries: list[dict[str, Any]]) -> None:
    ensure_app_dir()
    HISTORY_FILE.write_text(
        json.dumps(entries[-25:], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def append_history(entry: dict[str, Any]) -> list[dict[str, Any]]:
    history = load_history()
    payload = entry.copy()
    payload["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    history.append(payload)
    save_history(history)
    return history


def clear_history() -> None:
    ensure_app_dir()
    HISTORY_FILE.write_text("[]", encoding="utf-8")


def export_history_csv(entries: list[dict[str, Any]], target_path: str) -> None:
    fieldnames = [
        "timestamp",
        "target",
        "requested_target",
        "source_label",
        "file_size_mb",
        "passes",
        "write_avg_mb_s",
        "read_avg_mb_s",
        "write_best_mb_s",
        "read_best_mb_s",
        "write_worst_mb_s",
        "read_worst_mb_s",
        "free_space_before",
        "free_space_after",
    ]
    with open(target_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in entries:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def load_settings() -> dict[str, Any]:
    ensure_app_dir()
    if not SETTINGS_FILE.exists():
        return {}
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(settings: dict[str, Any]) -> None:
    ensure_app_dir()
    SETTINGS_FILE.write_text(
        json.dumps(settings, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
