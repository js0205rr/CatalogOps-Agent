from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "dataset" / "Clothing.xlsx"
DEFAULT_OUTPUT_DIR = ROOT / "dataset" / "processed"

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Clothing & Accessories > Shoes": (
        "shoe",
        "shoes",
        "sneaker",
        "sneakers",
        "sandal",
        "sandals",
        "slipper",
        "slippers",
        "boot",
        "boots",
        "loafer",
        "loafers",
        "heel",
        "heels",
        "footwear",
        "flip flop",
    ),
    "Clothing & Accessories > Tops": (
        "t-shirt",
        "tshirt",
        "tee",
        "shirt",
        "shirts",
        "top",
        "tops",
        "blouse",
        "blouses",
        "sweatshirt",
        "hoodie",
        "jacket",
        "coat",
    ),
    "Clothing & Accessories > Dresses": (
        "dress",
        "dresses",
        "gown",
        "saree",
        "kurta",
        "kurti",
        "lehenga",
        "skirt",
        "swimwear",
        "romper",
        "frock",
        "jumpsuit",
    ),
    "Clothing & Accessories > Bottoms": (
        "jeans",
        "trouser",
        "trousers",
        "pant",
        "pants",
        "leggings",
        "shorts",
        "palazzo",
        "jogger",
        "joggers",
    ),
    "Clothing & Accessories > Bags": (
        "bag",
        "bags",
        "wallet",
        "wallets",
        "backpack",
        "backpacks",
        "purse",
        "handbag",
        "handbags",
        "clutch",
        "tote",
    ),
    "Clothing & Accessories > Accessories": (
        "sunglasses",
        "belt",
        "belts",
        "watch",
        "watches",
        "jewellery",
        "jewelry",
        "necklace",
        "bracelet",
        "cap",
        "hat",
        "scarf",
        "tie",
        "hairband",
        "headband",
        "glasses",
    ),
    "Clothing & Accessories > Innerwear": (
        "bra",
        "brief",
        "briefs",
        "underwear",
        "innerwear",
        "panty",
        "panties",
        "lingerie",
        "vest",
        "sock",
        "socks",
    ),
    "Clothing & Accessories > Clothing Sets": (
        "set",
        "sets",
        "outfit",
        "outfits",
        "suit",
        "suits",
        "tracksuit",
        "night suit",
        "sleep suit",
    ),
}

FALLBACK_CATEGORY = "Clothing & Accessories > Apparel"
REQUIRED_COLUMNS = [
    "product_id",
    "title",
    "description",
    "seller_category",
    "attributes",
    "seller_id",
    "price",
]

COLORS = (
    "black",
    "white",
    "red",
    "blue",
    "green",
    "yellow",
    "pink",
    "purple",
    "grey",
    "gray",
    "brown",
    "beige",
    "orange",
    "gold",
    "silver",
    "multicolor",
    "multi-color",
    "navy",
    "maroon",
)
MATERIALS = (
    "cotton",
    "polyester",
    "leather",
    "denim",
    "silk",
    "wool",
    "synthetic",
    "nylon",
    "spandex",
    "rayon",
    "chiffon",
    "satin",
    "canvas",
    "rubber",
    "plastic",
    "metal",
    "linen",
)
GENDER_TERMS = {
    "women": "women",
    "woman": "women",
    "girls": "girls",
    "girl": "girls",
    "men": "men",
    "man": "men",
    "boys": "boys",
    "boy": "boys",
    "baby": "baby",
    "kids": "kids",
    "children": "kids",
    "unisex": "unisex",
}


def clean_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def read_clothing_rows(input_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    workbook = pd.ExcelFile(input_path)
    rows: list[dict[str, Any]] = []
    sheet_shapes: dict[str, list[int]] = {}
    for sheet in workbook.sheet_names:
        frame = pd.read_excel(input_path, sheet_name=sheet, header=None)
        sheet_shapes[sheet] = [int(frame.shape[0]), int(frame.shape[1])]
        if frame.empty or frame.shape[1] < 2:
            continue
        for row_index, row in frame.iterrows():
            source_category = clean_text(row.iloc[0])
            text_parts = [
                clean_text(item)
                for item in row.iloc[1:].tolist()
                if clean_text(item) and clean_text(item).lower() != "nan"
            ]
            text = clean_text(" ".join(text_parts))
            rows.append(
                {
                    "source_sheet": sheet,
                    "source_row": int(row_index) + 1,
                    "source_category": source_category,
                    "raw_text": text,
                }
            )
    return rows, {"sheets": workbook.sheet_names, "sheet_shapes": sheet_shapes}


def infer_category(text: str) -> tuple[str, str]:
    lowered = f" {text.lower()} "
    scores: list[tuple[int, str, str]] = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        matches = [keyword for keyword in keywords if f" {keyword} " in lowered or keyword in lowered]
        if matches:
            scores.append((len(matches), category, matches[0]))
    if not scores:
        return FALLBACK_CATEGORY, ""
    scores.sort(key=lambda item: (item[0], len(item[2])), reverse=True)
    _, category, matched = scores[0]
    return category, matched


def title_from_text(text: str) -> str:
    markers = (
        " description ",
        " color:",
        " colour:",
        " size:",
        " size name",
        " material:",
        " made of ",
        " made from ",
    )
    lowered = f" {text.lower()} "
    cut_at = 0
    for marker in markers:
        index = lowered.find(marker)
        if index > 25:
            cut_at = index
            break
    candidate = text[:cut_at].strip() if cut_at else text
    words = candidate.split()
    if len(words) > 18:
        candidate = " ".join(words[:18])
    if len(candidate) > 140:
        candidate = candidate[:140].rsplit(" ", 1)[0]
    return candidate.strip(" -,:;") or text[:120].strip()


def find_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    return [term for term in terms if re.search(rf"\b{re.escape(term)}\b", lowered)]


def infer_brand(title: str) -> str:
    words = re.findall(r"[A-Za-z][A-Za-z'&.-]*", title)
    blocked = {
        "for",
        "with",
        "and",
        "the",
        "new",
        "baby",
        "girl",
        "girls",
        "boy",
        "boys",
        "women",
        "men",
        "kids",
        "cotton",
    }
    brand: list[str] = []
    for word in words[:4]:
        if word.lower() in blocked or word.isupper() and len(word) <= 2:
            break
        if word[:1].isupper():
            brand.append(word.strip("."))
        elif brand:
            break
    return " ".join(brand[:2])


def infer_attributes(text: str, title: str, category: str) -> dict[str, str]:
    lowered = text.lower()
    attributes: dict[str, str] = {
        "source_category": "Clothing & Accessories",
        "product_type": category.rsplit(" > ", 1)[-1],
    }
    brand = infer_brand(title)
    if brand:
        attributes["brand"] = brand
    colors = find_terms(text, COLORS)
    if colors:
        attributes["color"] = ", ".join(dict.fromkeys(colors))
    materials = find_terms(text, MATERIALS)
    if materials:
        attributes["material"] = ", ".join(dict.fromkeys(materials))
    for term, value in GENDER_TERMS.items():
        if re.search(rf"\b{re.escape(term)}\b", lowered):
            attributes["gender"] = value
            break
    sizes = re.findall(
        r"\b(?:XS|S|M|L|XL|XXL|XXXL|[0-9]{1,2}\s*(?:M|Y|years?|months?)|[0-9]{1,2})\b",
        text,
        flags=re.IGNORECASE,
    )
    if sizes:
        attributes["size"] = ", ".join(dict.fromkeys(size.upper().replace(" ", "") for size in sizes[:5]))
    return attributes


def wrong_category_for(category: str) -> str:
    categories = [*CATEGORY_KEYWORDS.keys(), FALLBACK_CATEGORY]
    if category not in categories:
        return "Clothing & Accessories > Accessories"
    return categories[(categories.index(category) + 3) % len(categories)]


def clean_dataset(input_path: Path, output_dir: Path, sample_size: int) -> dict[str, Any]:
    raw_rows, workbook_info = read_clothing_rows(input_path)
    seen: set[str] = set()
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
        text_key = re.sub(r"\W+", "", text.lower())
        digest = hashlib.sha1(text_key.encode("utf-8")).hexdigest()
        if digest in seen:
            dropped_duplicate += 1
            continue
        seen.add(digest)
        gold_category, matched_keyword = infer_category(text)
        title = title_from_text(text)
        attributes = infer_attributes(text, title, gold_category)
        product_index = len(clean_rows) + 1
        product_id = f"CLOTH-{product_index:05d}"
        synthetic_mismatch = product_index % 5 == 0
        mismatch_seller_category = gold_category
        if synthetic_mismatch:
            mismatch_seller_category = wrong_category_for(gold_category)
        clean_rows.append(
            {
                "product_id": product_id,
                "title": title,
                "description": text,
                "seller_category": gold_category,
                "attributes": json.dumps(attributes, ensure_ascii=False, sort_keys=True),
                "seller_id": f"seller_{product_index % 50:03d}",
                "price": "",
            }
        )
        labels.append(
            {
                "product_id": product_id,
                "source_sheet": raw["source_sheet"],
                "source_row": raw["source_row"],
                "source_category": raw["source_category"],
                "gold_category": gold_category,
                "clean_seller_category": gold_category,
                "mismatch_seller_category": mismatch_seller_category,
                "synthetic_mismatch": synthetic_mismatch,
                "matched_keyword": matched_keyword,
                "text_sha1": digest,
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    clean_path = output_dir / "clothing_catalogops_clean.csv"
    mismatch_path = output_dir / "clothing_catalogops_mismatch_20pct.csv"
    sample_path = output_dir / f"clothing_catalogops_mismatch_sample_{sample_size}.csv"
    labels_path = output_dir / "clothing_labels.csv"
    report_path = output_dir / "clothing_cleaning_report.json"

    def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)

    mismatch_rows = [dict(row) for row in clean_rows]
    mismatch_by_id = {
        item["product_id"]: item["mismatch_seller_category"]
        for item in labels
        if item["synthetic_mismatch"]
    }
    for row in mismatch_rows:
        if row["product_id"] in mismatch_by_id:
            row["seller_category"] = mismatch_by_id[row["product_id"]]

    write_csv(clean_path, clean_rows, REQUIRED_COLUMNS)
    write_csv(mismatch_path, mismatch_rows, REQUIRED_COLUMNS)
    write_csv(sample_path, mismatch_rows[:sample_size], REQUIRED_COLUMNS)
    write_csv(labels_path, labels, list(labels[0].keys()) if labels else [])

    category_counts: dict[str, int] = {}
    mismatch_count = 0
    for item in labels:
        category_counts[item["gold_category"]] = category_counts.get(item["gold_category"], 0) + 1
        mismatch_count += int(bool(item["synthetic_mismatch"]))

    report = {
        "input_path": str(input_path),
        "outputs": {
            "catalogops_clean_csv": str(clean_path),
            "catalogops_mismatch_csv": str(mismatch_path),
            "mismatch_sample_csv": str(sample_path),
            "labels_csv": str(labels_path),
        },
        "workbook": workbook_info,
        "raw_rows": len(raw_rows),
        "clean_rows": len(clean_rows),
        "dropped_empty": dropped_empty,
        "dropped_short": dropped_short,
        "dropped_duplicate": dropped_duplicate,
        "synthetic_mismatch_rows": mismatch_count,
        "synthetic_mismatch_rate": round(mismatch_count / len(clean_rows), 4)
        if clean_rows
        else 0.0,
        "gold_category_distribution": category_counts,
        "columns": REQUIRED_COLUMNS,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Clothing & Accessories data for CatalogOps.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--sample-size", type=int, default=1000)
    args = parser.parse_args()
    report = clean_dataset(Path(args.input), Path(args.output_dir), args.sample_size)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
