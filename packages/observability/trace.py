from __future__ import annotations

import time
from typing import Any


def trace_event(event: str, **payload: Any) -> dict[str, Any]:
    return {"event": event, "ts": time.time(), **payload}

