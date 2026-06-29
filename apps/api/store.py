from __future__ import annotations

import re
import threading
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from apps.api.schemas import RunEvent


ROOT = Path(__file__).resolve().parents[2]
UPLOAD_ROOT = ROOT / "data" / "api_uploads"
BATCH_UPLOAD_ROOT = UPLOAD_ROOT / "batches"
DOCUMENT_UPLOAD_ROOT = ROOT / "data" / "policy_docs"


def safe_filename(filename: str, fallback: str) -> str:
    name = Path(filename).name
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return cleaned or fallback


class ApiStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.batches: dict[str, dict[str, Any]] = {}
        self.events: dict[str, list[RunEvent]] = {}

    def create_batch(self, filename: str, path: Path) -> str:
        batch_id = f"batch-{uuid4().hex}"
        with self._lock:
            self.batches[batch_id] = {
                "batch_id": batch_id,
                "filename": filename,
                "path": str(path),
                "status": "uploaded",
                "run_id": "",
                "report": None,
                "error": "",
            }
        return batch_id

    def get_batch(self, batch_id: str) -> dict[str, Any] | None:
        with self._lock:
            item = self.batches.get(batch_id)
            return dict(item) if item else None

    def update_batch(self, batch_id: str, **updates: Any) -> dict[str, Any]:
        with self._lock:
            self.batches[batch_id].update(updates)
            return dict(self.batches[batch_id])

    def add_event(self, run_id: str, event: str, **payload: Any) -> RunEvent:
        item = RunEvent(event=event, run_id=run_id, ts=time.time(), **payload)
        with self._lock:
            self.events.setdefault(run_id, []).append(item)
        return item

    def get_events(self, run_id: str, after: int = 0) -> list[RunEvent]:
        with self._lock:
            return list(self.events.get(run_id, [])[after:])


api_store = ApiStore()
