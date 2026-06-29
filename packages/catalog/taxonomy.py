from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TAXONOMY_PATH = ROOT / "data" / "taxonomy" / "category_keywords.json"


def normalize_category_path(path: str) -> str:
    return " > ".join(part.strip() for part in path.replace("/", ">").split(">") if part.strip())


def split_category_path(path: str) -> list[str]:
    return normalize_category_path(path).split(" > ") if normalize_category_path(path) else []


def load_category_keywords(path: str | Path | None = None) -> list[dict[str, Any]]:
    source = Path(path) if path is not None else DEFAULT_TAXONOMY_PATH
    with source.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("category keyword taxonomy must be a list")
    return [dict(item) for item in data]


@lru_cache(maxsize=1)
def get_taxonomy_tree() -> list[dict[str, Any]]:
    return load_category_keywords()


def find_category_by_path(category_path: str, taxonomy_tree: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    normalized = normalize_category_path(category_path)
    for item in taxonomy_tree or get_taxonomy_tree():
        if normalize_category_path(str(item.get("category_path", ""))) == normalized:
            return item
    return None


def find_category_by_id(category_id: str, taxonomy_tree: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    for item in taxonomy_tree or get_taxonomy_tree():
        if str(item.get("category_id", "")) == category_id:
            return item
    return None


def is_parent_child_path(left: str, right: str) -> bool:
    left_parts = split_category_path(left)
    right_parts = split_category_path(right)
    if not left_parts or not right_parts or left_parts == right_parts:
        return False
    shorter, longer = (left_parts, right_parts) if len(left_parts) < len(right_parts) else (right_parts, left_parts)
    return longer[: len(shorter)] == shorter

