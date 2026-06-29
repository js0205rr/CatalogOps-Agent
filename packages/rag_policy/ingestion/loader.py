from __future__ import annotations

from pathlib import Path
from typing import Any

from packages.rag_policy.schemas import PolicyDocument


def _parse_scalar(value: str) -> str | list[str]:
    stripped = value.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        return [item.strip().strip("\"'") for item in stripped[1:-1].split(",") if item.strip()]
    return stripped.strip("\"'")


def parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    marker = text.find("\n---\n", 4)
    if marker < 0:
        return {}, text
    metadata: dict[str, Any] = {}
    for line in text[4:marker].splitlines():
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = _parse_scalar(value)
    return metadata, text[marker + 5 :].strip()


def load_policy_document(path: str | Path) -> PolicyDocument:
    source = Path(path)
    metadata, text = parse_front_matter(source.read_text(encoding="utf-8"))
    inferred_doc_type = "qa"
    if "attribute" in source.stem or "schema" in source.stem:
        inferred_doc_type = "attribute_schema"
    elif "title" in source.stem or "claim" in source.stem:
        inferred_doc_type = "title_policy"
    elif "category" in source.stem:
        inferred_doc_type = "category_policy"
    metadata.setdefault("doc_type", inferred_doc_type)
    metadata.setdefault("category", "all")
    metadata.setdefault("effective_date", "unknown")
    metadata["file_path"] = str(source)
    return PolicyDocument(doc_id=source.stem, path=str(source), text=text, metadata=metadata)


def load_policy_documents(policy_dir: str | Path) -> list[PolicyDocument]:
    root = Path(policy_dir)
    return [load_policy_document(path) for path in sorted(root.glob("*.md"))]
