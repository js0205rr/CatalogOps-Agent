from __future__ import annotations

import re
from typing import Any

from packages.catalog.schemas import CategoryCandidate, CategoryPrediction, ProductInput


BRAND = "\u54c1\u724c"
MATERIAL = "\u6750\u8d28"
SIZE = "\u5c3a\u7801"
COLOR = "\u989c\u8272"
MODEL = "\u578b\u53f7"
STORAGE = "\u5b58\u50a8\u5bb9\u91cf"
NETWORK = "\u7f51\u7edc\u5236\u5f0f"
COMPATIBLE_MODEL = "\u9002\u7528\u673a\u578b"
CONNECTION = "\u8fde\u63a5\u65b9\u5f0f"
BATTERY_LIFE = "\u7eed\u822a\u65f6\u95f4"
NET_WEIGHT = "\u51c0\u542b\u91cf"
SHELF_LIFE = "\u4fdd\u8d28\u671f"
PRODUCTION_DATE = "\u751f\u4ea7\u65e5\u671f"
EN_BRAND = "brand"
EN_PRODUCT_TYPE = "product_type"
EN_GENDER = "gender"
EN_SIZE = "size"
EN_COLOR = "color"
EN_MATERIAL = "material"
EN_PIECES_IN_SET = "pieces_in_set"
EN_MODEL = "model"
EN_KEY_SPECIFICATION = "key_specification"
EN_STORAGE_CAPACITY = "storage_capacity"
EN_NETWORK_TYPE = "network_type"
EN_CONNECTIVITY = "connectivity"
EN_PROCESSOR_OR_CAPACITY = "processor_or_capacity"
EN_RESOLUTION_OR_MOUNT = "resolution_or_mount"
EN_INTERFACE = "interface"
EN_CONNECTOR_TYPE = "connector_type"
EN_POWER_RATING = "power_rating"
EN_USE_CASE = "use_case"
EN_DIMENSIONS = "dimensions"
EN_CAPACITY_OR_SIZE = "capacity_or_size"
EN_ASSEMBLY_REQUIRED = "assembly_required"
EN_COLOR_OR_FINISH = "color_or_finish"
EN_BOOK_TITLE = "book_title"
EN_AUTHOR = "author"
EN_FORMAT = "format"
EN_LANGUAGE = "language"
EN_AUTHOR_OR_EDITOR = "author_or_editor"
EN_EDITION = "edition"
EN_EXAM_OR_SUBJECT = "exam_or_subject"
EN_AGE_RANGE = "age_range"


TAXONOMY: list[dict[str, Any]] = [
    {
        "category_id": "1001",
        "category_path": "\u670d\u9970\u978b\u5305/\u5973\u88c5/T\u6064",
        "terms": ["t\u6064", "\u77ed\u8896", "\u7eaf\u68c9", "\u5973\u88c5", "\u4e0a\u8863"],
        "required": [BRAND, MATERIAL, SIZE, COLOR],
    },
    {
        "category_id": "2001",
        "category_path": (
            "\u6570\u7801\u5bb6\u7535/\u624b\u673a\u901a\u8baf/"
            "\u667a\u80fd\u624b\u673a"
        ),
        "terms": ["\u667a\u80fd\u624b\u673a", "5g", "\u5185\u5b58", "\u5c4f\u5e55"],
        "required": [BRAND, MODEL, STORAGE, NETWORK],
    },
    {
        "category_id": "2002",
        "category_path": "\u6570\u7801\u914d\u4ef6/\u624b\u673a\u914d\u4ef6/\u624b\u673a\u58f3",
        "terms": [
            "\u624b\u673a\u58f3",
            "\u4fdd\u62a4\u58f3",
            "\u4fdd\u62a4\u5957",
            "\u900f\u660e\u58f3",
        ],
        "required": [BRAND, COMPATIBLE_MODEL, MATERIAL, COLOR],
    },
    {
        "category_id": "2003",
        "category_path": (
            "\u6570\u7801\u914d\u4ef6/\u97f3\u9891\u8bbe\u5907/"
            "\u84dd\u7259\u8033\u673a"
        ),
        "terms": ["\u84dd\u7259\u8033\u673a", "\u8033\u673a", "\u964d\u566a", "\u5165\u8033\u5f0f"],
        "required": [BRAND, MODEL, CONNECTION, BATTERY_LIFE],
    },
    {
        "category_id": "3001",
        "category_path": "\u98df\u54c1\u996e\u6599/\u4f11\u95f2\u98df\u54c1/\u575a\u679c",
        "terms": [
            "\u575a\u679c",
            "\u8170\u679c",
            "\u674f\u4ec1",
            "\u96f6\u98df",
            "\u51c0\u542b\u91cf",
        ],
        "required": [BRAND, NET_WEIGHT, SHELF_LIFE, PRODUCTION_DATE],
    },
    {
        "category_id": "CLO-APPAREL",
        "category_path": "Clothing & Accessories > Apparel",
        "terms": ["apparel", "clothing", "wear", "garment", "outfit"],
        "required": [EN_BRAND, EN_PRODUCT_TYPE, EN_GENDER, EN_SIZE, EN_COLOR, EN_MATERIAL],
    },
    {
        "category_id": "CLO-TOPS",
        "category_path": "Clothing & Accessories > Tops",
        "terms": ["t-shirt", "tshirt", "tee", "shirt", "top", "blouse", "hoodie", "sweatshirt", "jacket", "coat"],
        "required": [EN_BRAND, EN_PRODUCT_TYPE, EN_GENDER, EN_SIZE, EN_COLOR, EN_MATERIAL],
    },
    {
        "category_id": "CLO-BOTTOMS",
        "category_path": "Clothing & Accessories > Bottoms",
        "terms": ["jeans", "trouser", "trousers", "pants", "leggings", "shorts", "jogger"],
        "required": [EN_BRAND, EN_PRODUCT_TYPE, EN_GENDER, EN_SIZE, EN_COLOR, EN_MATERIAL],
    },
    {
        "category_id": "CLO-DRESSES",
        "category_path": "Clothing & Accessories > Dresses",
        "terms": ["dress", "dresses", "gown", "saree", "kurta", "kurti", "lehenga", "skirt", "romper", "jumpsuit", "swimwear"],
        "required": [EN_BRAND, EN_PRODUCT_TYPE, EN_GENDER, EN_SIZE, EN_COLOR, EN_MATERIAL],
    },
    {
        "category_id": "CLO-SETS",
        "category_path": "Clothing & Accessories > Clothing Sets",
        "terms": ["sets", "outfit", "outfits", "suit", "tracksuit", "night suit", "sleep suit"],
        "required": [EN_BRAND, EN_PRODUCT_TYPE, EN_GENDER, EN_SIZE, EN_COLOR, EN_MATERIAL, EN_PIECES_IN_SET],
    },
    {
        "category_id": "CLO-INNERWEAR",
        "category_path": "Clothing & Accessories > Innerwear",
        "terms": ["bra", "brief", "underwear", "innerwear", "panty", "lingerie", "vest", "socks"],
        "required": [EN_BRAND, EN_PRODUCT_TYPE, EN_GENDER, EN_SIZE, EN_COLOR, EN_MATERIAL],
    },
    {
        "category_id": "CLO-SHOES",
        "category_path": "Clothing & Accessories > Shoes",
        "terms": ["shoe", "shoes", "sneaker", "sandal", "slipper", "boot", "loafer", "heel", "footwear"],
        "required": [EN_BRAND, EN_PRODUCT_TYPE, EN_GENDER, EN_SIZE, EN_COLOR, EN_MATERIAL],
    },
    {
        "category_id": "CLO-BAGS",
        "category_path": "Clothing & Accessories > Bags",
        "terms": ["bag", "wallet", "backpack", "purse", "handbag", "clutch", "tote"],
        "required": [EN_BRAND, EN_PRODUCT_TYPE, EN_COLOR, EN_MATERIAL],
    },
    {
        "category_id": "CLO-ACCESSORIES",
        "category_path": "Clothing & Accessories > Accessories",
        "terms": ["sunglasses", "belt", "watch", "jewelry", "jewellery", "necklace", "bracelet", "cap", "hat", "scarf", "tie", "hairband", "headband", "glasses"],
        "required": [EN_BRAND, EN_PRODUCT_TYPE, EN_COLOR, EN_MATERIAL],
    },
    {
        "category_id": "ELEC-MOBILE",
        "category_path": "Electronics > Mobile Phones",
        "terms": ["mobile", "phone", "smartphone", "cell phone", "android", "iphone", "handset"],
        "required": [EN_BRAND, EN_PRODUCT_TYPE, EN_MODEL, EN_STORAGE_CAPACITY, EN_NETWORK_TYPE],
    },
    {
        "category_id": "ELEC",
        "category_path": "Electronics",
        "terms": [
            "electronics",
            "electronic",
            "device",
            "gadget",
            "digital",
        ],
        "required": [EN_BRAND, EN_PRODUCT_TYPE, EN_MODEL],
    },
    {
        "category_id": "ELEC-AUDIO",
        "category_path": "Electronics > Audio",
        "terms": ["headphone", "headphones", "earphone", "earphones", "earbud", "earbuds", "speaker", "bluetooth", "wireless", "soundbar"],
        "required": [EN_BRAND, EN_PRODUCT_TYPE, EN_MODEL, EN_CONNECTIVITY],
    },
    {
        "category_id": "ELEC-COMPUTERS",
        "category_path": "Electronics > Computers & Accessories",
        "terms": ["laptop", "computer", "keyboard", "mouse", "monitor", "processor", "ram", "hard disk", "ssd", "router"],
        "required": [EN_BRAND, EN_PRODUCT_TYPE, EN_MODEL, EN_PROCESSOR_OR_CAPACITY],
    },
    {
        "category_id": "ELEC-CAMERA",
        "category_path": "Electronics > Cameras",
        "terms": ["camera", "dslr", "lens", "webcam", "camcorder", "tripod", "cctv"],
        "required": [EN_BRAND, EN_PRODUCT_TYPE, EN_MODEL, EN_RESOLUTION_OR_MOUNT],
    },
    {
        "category_id": "ELEC-STORAGE",
        "category_path": "Electronics > Storage & Memory",
        "terms": ["memory card", "microsd", "sd card", "pendrive", "pen drive", "flash drive", "hard drive", "ssd"],
        "required": [EN_BRAND, EN_PRODUCT_TYPE, EN_STORAGE_CAPACITY, EN_INTERFACE],
    },
    {
        "category_id": "ELEC-POWER",
        "category_path": "Electronics > Chargers & Cables",
        "terms": ["charger", "charging", "cable", "adapter", "power bank", "usb", "type-c", "lightning"],
        "required": [EN_BRAND, EN_PRODUCT_TYPE, EN_CONNECTOR_TYPE, EN_POWER_RATING],
    },
    {
        "category_id": "HOME-DECOR",
        "category_path": "Household > Home Decor",
        "terms": ["decor", "painting", "wall art", "frame", "vase", "clock", "showpiece", "poster"],
        "required": [EN_BRAND, EN_PRODUCT_TYPE, EN_MATERIAL, EN_DIMENSIONS, EN_COLOR],
    },
    {
        "category_id": "HOME",
        "category_path": "Household",
        "terms": [
            "household",
            "home",
            "homeware",
            "houseware",
        ],
        "required": [EN_BRAND, EN_PRODUCT_TYPE, EN_MATERIAL],
    },
    {
        "category_id": "HOME-KITCHEN",
        "category_path": "Household > Kitchen & Dining",
        "terms": ["kitchen", "cookware", "bottle", "container", "dinner set", "plate", "pan", "knife", "jar"],
        "required": [EN_BRAND, EN_PRODUCT_TYPE, EN_MATERIAL, EN_CAPACITY_OR_SIZE],
    },
    {
        "category_id": "HOME-FURNITURE",
        "category_path": "Household > Furniture",
        "terms": ["furniture", "chair", "table", "desk", "rack", "shelf", "wardrobe", "cabinet", "sofa"],
        "required": [EN_BRAND, EN_PRODUCT_TYPE, EN_MATERIAL, EN_DIMENSIONS, EN_ASSEMBLY_REQUIRED],
    },
    {
        "category_id": "HOME-BEDDING",
        "category_path": "Household > Bedding & Bath",
        "terms": ["bedsheet", "bed sheet", "blanket", "pillow", "towel", "bath", "mattress", "curtain"],
        "required": [EN_BRAND, EN_PRODUCT_TYPE, EN_MATERIAL, EN_SIZE, EN_COLOR],
    },
    {
        "category_id": "HOME-STORAGE",
        "category_path": "Household > Storage & Organization",
        "terms": ["storage", "organizer", "box", "basket", "hanger", "holder", "stand", "rack"],
        "required": [EN_BRAND, EN_PRODUCT_TYPE, EN_MATERIAL, EN_DIMENSIONS],
    },
    {
        "category_id": "HOME-CLEANING",
        "category_path": "Household > Cleaning Supplies",
        "terms": ["cleaning", "mop", "broom", "brush", "duster", "scrub", "wipe", "trash bag"],
        "required": [EN_BRAND, EN_PRODUCT_TYPE, EN_MATERIAL, EN_USE_CASE],
    },
    {
        "category_id": "HOME-LIGHTING",
        "category_path": "Household > Lighting",
        "terms": ["lamp", "light", "lighting", "bulb", "led", "lantern", "night light"],
        "required": [EN_BRAND, EN_PRODUCT_TYPE, EN_POWER_RATING, EN_COLOR_OR_FINISH],
    },
    {
        "category_id": "BOOKS-FICTION",
        "category_path": "Books > Fiction",
        "terms": ["novel", "fiction", "story", "stories", "literature", "thriller", "romance", "fantasy"],
        "required": [EN_BOOK_TITLE, EN_AUTHOR, EN_FORMAT, EN_LANGUAGE],
    },
    {
        "category_id": "BOOKS",
        "category_path": "Books",
        "terms": ["book", "books", "paperback", "hardcover", "author", "publisher", "edition"],
        "required": [EN_BOOK_TITLE, EN_AUTHOR, EN_FORMAT, EN_LANGUAGE],
    },
    {
        "category_id": "BOOKS-NONFICTION",
        "category_path": "Books > Non-Fiction",
        "terms": ["non-fiction", "nonfiction", "biography", "memoir", "history", "business", "self help", "psychology"],
        "required": [EN_BOOK_TITLE, EN_AUTHOR, EN_FORMAT, EN_LANGUAGE],
    },
    {
        "category_id": "BOOKS-ACADEMIC",
        "category_path": "Books > Academic & Exam Prep",
        "terms": ["exam", "guide", "textbook", "study", "solved papers", "question bank", "engineering", "medical"],
        "required": [EN_BOOK_TITLE, EN_AUTHOR_OR_EDITOR, EN_FORMAT, EN_EDITION, EN_EXAM_OR_SUBJECT],
    },
    {
        "category_id": "BOOKS-CHILDREN",
        "category_path": "Books > Children Books",
        "terms": ["children", "kids", "picture book", "activity book", "coloring", "storybook", "nursery"],
        "required": [EN_BOOK_TITLE, EN_AUTHOR_OR_EDITOR, EN_FORMAT, EN_AGE_RANGE],
    },
    {
        "category_id": "BOOKS-REFERENCE",
        "category_path": "Books > Reference",
        "terms": ["dictionary", "encyclopedia", "reference", "manual", "handbook", "atlas"],
        "required": [EN_BOOK_TITLE, EN_AUTHOR_OR_EDITOR, EN_FORMAT, EN_LANGUAGE],
    },
    {
        "category_id": "BOOKS-RELIGION",
        "category_path": "Books > Religion & Spirituality",
        "terms": ["religion", "spirituality", "bible", "gita", "quran", "devotional", "meditation"],
        "required": [EN_BOOK_TITLE, EN_AUTHOR_OR_EDITOR, EN_FORMAT, EN_LANGUAGE],
    },
]


def _term_in_text(term: str, text: str) -> bool:
    normalized = term.strip().lower()
    if not normalized:
        return False
    if normalized.isascii():
        return re.search(
            rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])",
            text,
            re.IGNORECASE,
        ) is not None
    return normalized in text


def predict_category_rule(product: ProductInput) -> CategoryPrediction:
    attribute_text = " ".join(
        f"{key} {value}" for key, value in product.attributes.items() if value not in (None, "")
    )
    listing_text = f"{product.title} {product.description} {attribute_text}".lower()
    declared_category_text = f"{product.merchant_category} {product.seller_category}".lower()
    merchant_exact_path = product.merchant_category.replace("/", ">").strip().lower()
    seller_exact_path = product.seller_category.replace("/", ">").strip().lower()
    candidates: list[CategoryCandidate] = []
    for item in TAXONOMY:
        item_path = str(item["category_path"]).replace("/", ">").strip().lower()
        listing_matched = [term for term in item["terms"] if _term_in_text(term, listing_text)]
        declared_matched = [
            term for term in item["terms"] if _term_in_text(term, declared_category_text)
        ]
        score = len(listing_matched)
        declared_exact_match = bool(
            merchant_exact_path
            and not seller_exact_path
            and merchant_exact_path == item_path
            and score > 0
        )
        if declared_exact_match:
            confidence = 0.93
            matched = list(dict.fromkeys([*declared_matched, *listing_matched]))
            rationale = "matched explicit merchant category path"
        elif score:
            confidence = min(0.98, 0.48 + score * 0.15 + min(score, 3) * 0.04)
            matched = listing_matched
            rationale = f"matched {score} listing taxonomy terms"
        elif declared_matched:
            confidence = min(0.62, 0.35 + len(declared_matched) * 0.06)
            matched = declared_matched
            rationale = "matched declared category terms only"
        else:
            confidence = 0.05
            matched = []
            rationale = "no taxonomy terms matched"
        candidates.append(
            CategoryCandidate(
                category_id=item["category_id"],
                category_path=item["category_path"],
                confidence=confidence,
                matched_terms=matched,
                rationale=rationale,
                evidence_ids=["taxonomy:catalog-v1"],
            )
        )
    best = max(candidates, key=lambda item: (item.confidence, len(item.matched_terms)))
    return CategoryPrediction(
        category_id=best.category_id,
        category_path=best.category_path,
        confidence=best.confidence,
        matched_terms=best.matched_terms,
        candidates=sorted(candidates, key=lambda item: item.confidence, reverse=True)[:3],
        evidence_ids=["taxonomy:catalog-v1"],
    )


def required_attributes(category_id: str) -> list[str]:
    item = next((entry for entry in TAXONOMY if entry["category_id"] == category_id), None)
    return list(item["required"]) if item else []


def extract_attributes_rule(product: ProductInput) -> dict[str, str]:
    attrs = {
        str(key): str(value)
        for key, value in product.attributes.items()
        if value not in (None, "")
    }
    text = f"{product.title} {product.description}"
    patterns = {
        NET_WEIGHT: r"(\d+(?:\.\d+)?\s*(?:g|kg|\u514b|\u5343\u514b))",
        STORAGE: r"(\d+\s*(?:GB|TB))",
        NETWORK: r"(5G|4G)",
        MATERIAL: (
            r"(\u7eaf\u68c9|\u68c9|\u7845\u80f6|TPU|\u76ae\u9769|"
            r"\u6da4\u7eb6|\u7f8a\u6bdb|\u771f\u4e1d)"
        ),
        COLOR: (
            r"(\u9ed1\u8272|\u767d\u8272|\u7ea2\u8272|\u84dd\u8272|"
            r"\u7eff\u8272|\u7070\u8272|\u900f\u660e)"
        ),
        SIZE: r"(?:\u5c3a\u7801|\u7801\u6570)[:\uff1a]?\s*([SMLX]{1,4}|\d{2,3})",
        SHELF_LIFE: r"\u4fdd\u8d28\u671f[:\uff1a]?\s*(\d+\s*(?:\u5929|\u4e2a\u6708|\u6708|\u5e74))",
        COMPATIBLE_MODEL: r"(iPhone\s?\d{1,2}|Mate\s?\d{2,3}|Galaxy\s?S\d{1,2})",
        CONNECTION: r"(\u84dd\u7259|Bluetooth)",
        BATTERY_LIFE: r"(?:\u7eed\u822a|battery life)[:\uff1a]?\s*(\d+\s*(?:\u5c0f\u65f6|h|H))",
    }
    for name, pattern in patterns.items():
        if name in attrs:
            continue
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            attrs[name] = match.group(1)

    for brand in (
        "Apple",
        "\u82f9\u679c",
        "\u534e\u4e3a",
        "\u5c0f\u7c73",
        "Sony",
        "JBL",
        "Nike",
        "\u8010\u514b",
        "\u826f\u54c1\u94fa\u5b50",
    ):
        if brand.lower() in text.lower():
            attrs.setdefault(BRAND, brand)
    return attrs


def sanitize_title(title: str) -> str:
    cleaned = re.sub(r"[!\uff01]{2,}", "\uff01", title)
    cleaned = re.sub(
        r"(\u5168\u7f51\u6700\u4f4e|\u7edd\u5bf9|100%\u6b63\u54c1|\u7b2c\u4e00|\u9876\u7ea7)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", cleaned).strip(" -")
