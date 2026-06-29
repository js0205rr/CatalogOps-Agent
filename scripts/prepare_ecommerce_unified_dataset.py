from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ECOMMERCE_CSV = ROOT / "dataset" / "ecommerceDataset.csv"
DEFAULT_CLOTHING_CSV = ROOT / "dataset" / "processed" / "clothing_catalogops_clean.csv"
DEFAULT_OUTPUT_DIR = ROOT / "dataset" / "processed"

REQUIRED_COLUMNS = [
    "product_id",
    "title",
    "description",
    "seller_category",
    "attributes",
    "seller_id",
    "price",
]

TOP_LEVEL_CATEGORIES = [
    "Clothing & Accessories",
    "Electronics",
    "Household",
    "Books",
]
ECOMMERCE_SOURCE_CATEGORIES = {"Electronics", "Household", "Books"}

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Clothing & Accessories": (
        "apparel",
        "clothing",
        "wear",
        "shirt",
        "dress",
        "shoe",
        "saree",
        "kurta",
        "jeans",
        "sunglasses",
        "bag",
        "cotton",
        "fashion",
    ),
    "Electronics": (
        "mobile",
        "phone",
        "smartphone",
        "laptop",
        "tablet",
        "camera",
        "bluetooth",
        "wireless",
        "headphone",
        "speaker",
        "charger",
        "battery",
        "usb",
        "memory card",
        "television",
        "led tv",
    ),
    "Household": (
        "home",
        "kitchen",
        "decor",
        "wall",
        "furniture",
        "bedsheet",
        "curtain",
        "cookware",
        "bottle",
        "container",
        "cleaning",
        "storage",
        "mattress",
        "painting",
        "lamp",
    ),
    "Books": (
        "book",
        "novel",
        "author",
        "paperback",
        "hardcover",
        "edition",
        "publisher",
        "story",
        "guide",
        "exam",
        "dictionary",
        "textbook",
        "volume",
        "chapter",
        "biography",
    ),
}


def clean_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def text_digest(text: str) -> str:
    normalized = re.sub(r"\W+", "", text.lower())
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def title_from_text(text: str) -> str:
    separators = (
        " description ",
        " product description ",
        " features ",
        " specifications ",
        " about the author ",
        " from the manufacturer ",
    )
    lowered = f" {text.lower()} "
    cut_at = 0
    for marker in separators:
        index = lowered.find(marker)
        if index > 30:
            cut_at = index
            break
    candidate = text[:cut_at].strip() if cut_at else text
    words = candidate.split()
    if len(words) > 20:
        candidate = " ".join(words[:20])
    if len(candidate) > 160:
        candidate = candidate[:160].rsplit(" ", 1)[0]
    return candidate.strip(" -,:;") or text[:140].strip()


def infer_attributes(text: str, category: str) -> dict[str, str]:
    lowered = text.lower()
    attributes: dict[str, str] = {"source_category": category, "product_type": category}
    brand_match = re.match(r"([A-Z][A-Za-z0-9'&.-]+(?:\s+[A-Z][A-Za-z0-9'&.-]+)?)\b", text)
    if brand_match and category != "Books":
        attributes["brand"] = brand_match.group(1)
    if category == "Books":
        attributes["format"] = "paperback" if "paperback" in lowered else ""
        author_match = re.search(r"\bby\s+([A-Z][A-Za-z .'-]{2,60})", text)
        if author_match:
            attributes["author"] = author_match.group(1).strip()
    if category == "Electronics":
        for term in ("bluetooth", "wireless", "usb", "battery", "camera", "mobile"):
            if term in lowered:
                attributes.setdefault("features", term)
    if category == "Household":
        for term in ("kitchen", "decor", "storage", "furniture", "cleaning"):
            if term in lowered:
                attributes.setdefault("use_case", term)
    return {key: value for key, value in attributes.items() if value}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def read_ecommerce_rows(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    skipped_malformed = 0
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        for row_index, row in enumerate(csv.reader(handle), start=1):
            if not row:
                skipped_malformed += 1
                continue
            source_category = clean_text(row[0])
            if source_category not in ECOMMERCE_SOURCE_CATEGORIES:
                skipped_malformed += 1
                continue
            text = clean_text(" ".join(clean_text(item) for item in row[1:] if clean_text(item)))
            rows.append(
                {
                    "source": "ecommerceDataset.csv",
                    "source_row": row_index,
                    "source_category": source_category,
                    "gold_category": source_category,
                    "raw_text": text,
                }
            )
    return rows, {"skipped_malformed_rows": skipped_malformed}


def read_clothing_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row_index, row in enumerate(read_csv_rows(path), start=2):
        text = clean_text(f"{row.get('title', '')} {row.get('description', '')}")
        rows.append(
            {
                "source": "clothing_catalogops_clean.csv",
                "source_row": row_index,
                "source_category": row.get("seller_category", "Clothing & Accessories"),
                "gold_category": "Clothing & Accessories",
                "raw_text": text,
                "source_product_id": row.get("product_id", ""),
                "source_attributes": row.get("attributes", ""),
            }
        )
    return rows


def wrong_category_for(category: str) -> str:
    index = TOP_LEVEL_CATEGORIES.index(category)
    return TOP_LEVEL_CATEGORIES[(index + 2) % len(TOP_LEVEL_CATEGORIES)]


def split_for(category_position: int) -> str:
    return "test" if category_position % 5 == 0 else "train"


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def build_unified_dataset(
    ecommerce_csv: Path,
    clothing_csv: Path,
    output_dir: Path,
    sample_size: int,
) -> dict[str, Any]:
    ecommerce_rows, ecommerce_report = read_ecommerce_rows(ecommerce_csv)
    clothing_rows = read_clothing_rows(clothing_csv)
    raw_rows = [*clothing_rows, *ecommerce_rows]

    seen: set[str] = set()
    category_positions: Counter[str] = Counter()
    clean_rows: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = []
    dropped_empty = 0
    dropped_short = 0
    dropped_duplicate = 0

    for raw in raw_rows:
        text = clean_text(raw["raw_text"])
        if not text:
            dropped_empty += 1
            continue
        if len(text) < 20:
            dropped_short += 1
            continue
        digest = text_digest(text)
        if digest in seen:
            dropped_duplicate += 1
            continue
        seen.add(digest)
        gold_category = raw["gold_category"]
        category_positions[gold_category] += 1
        product_index = len(clean_rows) + 1
        product_id = f"ECOM-{product_index:06d}"
        title = title_from_text(text)
        source_attributes = raw.get("source_attributes") or ""
        if source_attributes:
            try:
                attributes = json.loads(source_attributes)
            except json.JSONDecodeError:
                attributes = infer_attributes(text, gold_category)
            if not isinstance(attributes, dict):
                attributes = infer_attributes(text, gold_category)
            attributes["source_category"] = gold_category
            attributes["product_type"] = gold_category
        else:
            attributes = infer_attributes(text, gold_category)

        synthetic_mismatch = int(digest[:8], 16) % 5 == 0
        mismatch_seller_category = (
            wrong_category_for(gold_category) if synthetic_mismatch else gold_category
        )
        split = split_for(category_positions[gold_category])
        clean_rows.append(
            {
                "product_id": product_id,
                "title": title,
                "description": text,
                "seller_category": gold_category,
                "attributes": json.dumps(attributes, ensure_ascii=False, sort_keys=True),
                "seller_id": f"seller_{product_index % 100:03d}",
                "price": "",
            }
        )
        labels.append(
            {
                "product_id": product_id,
                "source": raw["source"],
                "source_row": raw["source_row"],
                "source_category": raw["source_category"],
                "source_product_id": raw.get("source_product_id", ""),
                "gold_category": gold_category,
                "clean_seller_category": gold_category,
                "mismatch_seller_category": mismatch_seller_category,
                "synthetic_mismatch": synthetic_mismatch,
                "split": split,
                "text_sha1": digest,
            }
        )

    mismatch_rows = [dict(row) for row in clean_rows]
    mismatch_by_id = {
        item["product_id"]: item["mismatch_seller_category"]
        for item in labels
        if item["synthetic_mismatch"]
    }
    for row in mismatch_rows:
        if row["product_id"] in mismatch_by_id:
            row["seller_category"] = mismatch_by_id[row["product_id"]]

    taxonomy = [
        {
            "category_id": category.upper().replace(" & ", "_").replace(" ", "_"),
            "category_path": category,
            "keywords": list(CATEGORY_KEYWORDS[category]),
            "required_attributes": ["source_category", "product_type"],
        }
        for category in TOP_LEVEL_CATEGORIES
    ]

    clean_path = output_dir / "ecommerce_catalogops_clean.csv"
    mismatch_path = output_dir / "ecommerce_catalogops_mismatch_20pct.csv"
    sample_path = output_dir / f"ecommerce_catalogops_mismatch_sample_{sample_size}.csv"
    labels_path = output_dir / "ecommerce_labels.csv"
    taxonomy_path = output_dir / "ecommerce_taxonomy.json"
    report_path = output_dir / "ecommerce_cleaning_report.json"

    write_csv(clean_path, clean_rows, REQUIRED_COLUMNS)
    write_csv(mismatch_path, mismatch_rows, REQUIRED_COLUMNS)
    write_csv(sample_path, mismatch_rows[:sample_size], REQUIRED_COLUMNS)
    write_csv(labels_path, labels, list(labels[0].keys()) if labels else [])
    taxonomy_path.write_text(json.dumps(taxonomy, ensure_ascii=False, indent=2), encoding="utf-8")

    distribution = Counter(item["gold_category"] for item in labels)
    split_distribution = Counter(f"{item['gold_category']}::{item['split']}" for item in labels)
    mismatch_count = sum(1 for item in labels if item["synthetic_mismatch"])
    report = {
        "inputs": {
            "ecommerce_csv": str(ecommerce_csv),
            "clothing_csv": str(clothing_csv),
        },
        "outputs": {
            "catalogops_clean_csv": str(clean_path),
            "catalogops_mismatch_csv": str(mismatch_path),
            "mismatch_sample_csv": str(sample_path),
            "labels_csv": str(labels_path),
            "taxonomy_json": str(taxonomy_path),
        },
        "raw_rows": len(raw_rows),
        "clean_rows": len(clean_rows),
        "dropped_empty": dropped_empty,
        "dropped_short": dropped_short,
        "dropped_duplicate": dropped_duplicate,
        "ecommerce_reader": ecommerce_report,
        "synthetic_mismatch_rows": mismatch_count,
        "synthetic_mismatch_rate": round(mismatch_count / len(clean_rows), 4)
        if clean_rows
        else 0.0,
        "gold_category_distribution": dict(distribution),
        "split_distribution": dict(split_distribution),
        "columns": REQUIRED_COLUMNS,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare a unified four-class Ecommerce Text Classification eval set."
    )
    parser.add_argument("--ecommerce-csv", default=str(DEFAULT_ECOMMERCE_CSV))
    parser.add_argument("--clothing-csv", default=str(DEFAULT_CLOTHING_CSV))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--sample-size", type=int, default=2000)
    args = parser.parse_args()
    report = build_unified_dataset(
        ecommerce_csv=Path(args.ecommerce_csv),
        clothing_csv=Path(args.clothing_csv),
        output_dir=Path(args.output_dir),
        sample_size=args.sample_size,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
