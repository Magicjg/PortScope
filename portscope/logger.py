from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .history import APP_DIR, ensure_app_dir

LOG_FILE = APP_DIR / "portscope.log"


def log_event(event: str, **fields: Any) -> None:
    ensure_app_dir()
    payload = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "event": event,
        "fields": fields,
    }
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def read_recent_logs(limit: int = 80) -> str:
    ensure_app_dir()
    if not LOG_FILE.exists():
        return "Aun no hay eventos registrados."
    try:
        lines = LOG_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return "No fue posible leer el archivo de logs."
    if not lines:
        return "Aun no hay eventos registrados."
    return "\n".join(lines[-max(1, int(limit)):])
