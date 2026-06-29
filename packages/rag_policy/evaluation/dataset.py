from __future__ import annotations

import json
from pathlib import Path

from packages.rag_policy.schemas import EvaluationItem


def load_evaluation_dataset(path: str | Path) -> list[EvaluationItem]:
    source = Path(path)
    if source.suffix.lower() == ".jsonl":
        raw_items = [
            json.loads(line)
            for line in source.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    else:
        payload = json.loads(source.read_text(encoding="utf-8"))
        raw_items = payload.get("items", []) if isinstance(payload, dict) else payload
    return [EvaluationItem.model_validate(item) for item in raw_items]
