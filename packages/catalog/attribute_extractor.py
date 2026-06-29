from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from packages.catalog.schemas import ExtractedAttributes, ProductInput
from packages.catalog.taxonomy import normalize_category_path


ROOT = Path(__file__).resolve().parents[2]
REQUIRED_ATTRIBUTES_PATH = ROOT / "data" / "taxonomy" / "required_attributes.json"

ATTRIBUTE_ALIASES = {
    "brand": "品牌",
    "品牌名称": "品牌",
    "适配品牌": "适用品牌",
    "compatible_brand": "适用品牌",
    "compatible_model": "适用型号",
    "适配型号": "适用型号",
    "适用机型": "适用型号",
    "model": "型号",
    "material": "材质",
    "color": "颜色",
    "colour": "颜色",
    "feature": "功能",
    "features": "功能",
    "battery_life": "续航时间",
    "续航": "续航时间",
    "connection": "连接方式",
    "connectivity": "连接方式",
}

ENGLISH_ATTRIBUTE_NAMES = {
    "brand",
    "product_type",
    "gender",
    "size",
    "color",
    "colour",
    "material",
    "pieces_in_set",
}
ATTRIBUTE_EQUIVALENTS = {
    "brand": {"brand", "???"},
    "product_type": {"product_type"},
    "gender": {"gender"},
    "size": {"size", "???"},
    "color": {"color", "colour", "???"},
    "material": {"material", "???"},
    "pieces_in_set": {"pieces_in_set"},
}

KNOWN_BRANDS = (
    "Apple",
    "苹果",
    "华为",
    "Huawei",
    "小米",
    "Xiaomi",
    "Samsung",
    "三星",
    "Sony",
    "索尼",
    "JBL",
    "Nike",
    "耐克",
    "Puma",
    "Adidas",
    "Mothercare",
    "Kuchipoo",
    "Vaenait",
    "Amour",
    "Woopower",
)

MATERIALS = (
    "液态硅胶",
    "硅胶",
    "TPU",
    "PC",
    "ABS",
    "皮革",
    "真皮",
    "纯棉",
    "棉",
    "涤纶",
    "羊毛",
    "不锈钢",
    "玻璃",
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

COLORS = (
    "透明",
    "黑色",
    "白色",
    "红色",
    "蓝色",
    "绿色",
    "灰色",
    "粉色",
    "紫色",
    "金色",
    "银色",
    "深空灰",
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

FEATURES = (
    "主动降噪",
    "降噪",
    "防摔",
    "磁吸",
    "无线充电",
    "快充",
    "防水",
    "防尘",
    "通话降噪",
    "触控",
)

MODEL_PATTERNS = (
    r"iPhone\s*(?:SE\s*)?\d{1,2}(?:\s*(?:Pro(?:\s*Max)?|Plus|Mini|Max))?",
    r"(?:Huawei\s*)?Mate\s*\d{2,3}(?:\s*Pro)?",
    r"(?:Samsung\s*)?Galaxy\s*[A-Z]?\d{1,3}(?:\s*(?:Ultra|Plus))?",
    r"(?:小米|Xiaomi)\s*\d{1,3}(?:\s*(?:Pro|Ultra))?",
)


def _non_empty(value: Any) -> bool:
    return value not in (None, "", [], {})


def _canonical_name(name: Any) -> str:
    text = str(name).strip()
    return ATTRIBUTE_ALIASES.get(text, ATTRIBUTE_ALIASES.get(text.lower(), text))


def _merchant_attributes(product: ProductInput) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_name, raw_value in product.attributes.items():
        if not _non_empty(raw_value):
            continue
        raw_key = str(raw_name).strip()
        name = _canonical_name(raw_name)
        value = str(raw_value).strip()
        values.setdefault(name, value)
        if raw_key.lower() in ENGLISH_ATTRIBUTE_NAMES:
            values.setdefault(raw_key.lower(), value)
    return values


def _find_first(patterns: tuple[str, ...], text: str) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return re.sub(r"\s+", " ", match.group(0)).strip()
    return ""


def _find_terms(terms: tuple[str, ...], text: str) -> list[str]:
    lowered = text.lower()
    return [term for term in terms if term.lower() in lowered]


def _extract_labelled_value(text: str, labels: tuple[str, ...]) -> str:
    labels_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(
        rf"(?:{labels_pattern})\s*[:：]\s*([^\s,，;；。]{{1,40}})",
        text,
        re.IGNORECASE,
    )
    return match.group(1).strip() if match else ""


def _name_variants(name: str) -> set[str]:
    canonical = _canonical_name(name)
    variants = {name, name.lower(), canonical, canonical.lower()}
    for group in ATTRIBUTE_EQUIVALENTS.values():
        lowered_group = {item.lower() for item in group}
        if name.lower() in lowered_group or canonical.lower() in lowered_group:
            variants.update(group)
            variants.update(item.lower() for item in group)
    return variants


def _applicable_brand(model: str) -> str:
    lowered = model.lower()
    if "iphone" in lowered:
        return "Apple"
    if "mate" in lowered:
        return "华为"
    if "galaxy" in lowered:
        return "Samsung"
    if "小米" in model or "xiaomi" in lowered:
        return "小米"
    return ""


def extract_product_attributes(
    product: ProductInput | dict[str, Any],
    category_path: str,
) -> ExtractedAttributes:
    validated = ProductInput.model_validate(product)
    values = _merchant_attributes(validated)
    merchant_text = " ".join(
        f"{name} {value}"
        for name, value in validated.attributes.items()
        if _non_empty(value)
    )
    text = f"{validated.title} {validated.description} {merchant_text}"
    normalized_category = normalize_category_path(category_path)
    accessory_category = any(
        marker in normalized_category for marker in ("手机壳", "保护壳", "手机配件")
    )

    model = _find_first(MODEL_PATTERNS, text)
    labelled_model = _extract_labelled_value(text, ("适用型号", "适用机型", "适配型号"))
    if labelled_model:
        model = labelled_model
    if model:
        if accessory_category or labelled_model:
            values.setdefault("适用型号", model)
            applicable_brand = _applicable_brand(model)
            if applicable_brand:
                values.setdefault("适用品牌", applicable_brand)
        else:
            values.setdefault("型号", model)

    product_model = _extract_labelled_value(text, ("型号", "产品型号"))
    if product_model:
        values.setdefault("型号", product_model)

    labelled_brand = _extract_labelled_value(text, ("品牌", "商品品牌"))
    if labelled_brand:
        values.setdefault("品牌", labelled_brand)
    else:
        matched_brands = _find_terms(KNOWN_BRANDS, text)
        if matched_brands:
            values.setdefault("品牌", matched_brands[0])

    materials = _find_terms(MATERIALS, text)
    colors = _find_terms(COLORS, text)
    features = _find_terms(FEATURES, text)
    if materials:
        values.setdefault("材质", "、".join(dict.fromkeys(materials)))
    if colors:
        values.setdefault("颜色", "、".join(dict.fromkeys(colors)))
    if features:
        values.setdefault("功能", "、".join(dict.fromkeys(features)))


    normalized_lower = normalized_category.lower()
    clothing_category = "clothing & accessories" in normalized_lower
    if clothing_category:
        if materials:
            values.setdefault("material", ", ".join(dict.fromkeys(materials)))
        if colors:
            values.setdefault("color", ", ".join(dict.fromkeys(colors)))
        for term, target in {
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
        }.items():
            if re.search(rf"\b{re.escape(term)}\b", text, re.IGNORECASE):
                values.setdefault("gender", target)
                break
        size_hits = re.findall(
            r"\b(?:XS|S|M|L|XL|XXL|XXXL|\d{1,2}\s*(?:M|Y|years?|months?)|\d{1,2})\b",
            text,
            re.IGNORECASE,
        )
        if size_hits:
            values.setdefault(
                "size",
                ", ".join(dict.fromkeys(hit.upper().replace(" ", "") for hit in size_hits[:5])),
            )
        leaf = normalized_category.rsplit(" > ", 1)[-1] if " > " in normalized_category else ""
        if leaf:
            values.setdefault("product_type", leaf)
        pieces = re.search(r"\b(?:pack of|set of)\s*(\d+)\b", text, re.IGNORECASE)
        if pieces:
            values.setdefault("pieces_in_set", pieces.group(1))
        if "brand" not in values:
            for candidate_key in ("brand", "???"):
                if candidate_key in values:
                    values["brand"] = values[candidate_key]
                    break
    connection_terms: list[str] = []
    if re.search(r"\bBluetooth\b|蓝牙", text, re.IGNORECASE):
        version = re.search(r"(?:Bluetooth|蓝牙)\s*(\d(?:\.\d)?)", text, re.IGNORECASE)
        connection_terms.append(f"蓝牙 {version.group(1)}" if version else "蓝牙")
    if re.search(r"\bUSB[- ]?C\b|Type[- ]?C", text, re.IGNORECASE):
        connection_terms.append("USB-C")
    if re.search(r"\b3\.5\s*mm\b|3\.5毫米", text, re.IGNORECASE):
        connection_terms.append("3.5mm")
    if connection_terms:
        values.setdefault("连接方式", "、".join(dict.fromkeys(connection_terms)))

    battery = re.search(
        r"(?:续航(?:时间)?|播放时间|使用时间)\s*[:：]?\s*"
        r"(\d+(?:\.\d+)?\s*(?:小时|h|H|天))",
        text,
        re.IGNORECASE,
    )
    if battery:
        values.setdefault("续航时间", battery.group(1))

    common_patterns = {
        "存储容量": r"(\d+\s*(?:GB|TB))",
        "网络制式": r"\b(5G|4G|3G)\b",
        "尺码": r"(?:尺码|码数)\s*[:：]?\s*([SMLX]{1,4}|\d{2,3})",
        "净含量": r"(\d+(?:\.\d+)?\s*(?:g|kg|克|千克|ml|毫升))",
        "保质期": r"保质期\s*[:：]?\s*(\d+\s*(?:天|个月|月|年))",
        "生产日期": r"生产日期\s*[:：]?\s*(\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}日?)",
        "容量": r"(\d+(?:\.\d+)?\s*(?:L|升|毫升|ml))",
        "功率": r"(\d+(?:\.\d+)?\s*(?:W|瓦|千瓦|kW))",
    }
    for name, pattern in common_patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            values.setdefault(name, match.group(1))

    if "适用型号" in values and "适用品牌" not in values:
        applicable_brand = _applicable_brand(values["适用型号"])
        if applicable_brand:
            values["适用品牌"] = applicable_brand

    evidence_ids = [f"product:{validated.sku_id}", "rule:attribute-extractor-v1"]
    confidence = min(0.98, 0.45 + len(values) * 0.07) if values else 0.2
    return ExtractedAttributes(
        values=values,
        confidence=confidence,
        evidence_ids=evidence_ids,
    )


@lru_cache(maxsize=1)
def load_required_attributes() -> dict[str, list[str]]:
    if not REQUIRED_ATTRIBUTES_PATH.exists():
        return {}
    payload = json.loads(REQUIRED_ATTRIBUTES_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("required_attributes.json must contain an object")
    return {
        normalize_category_path(str(path)): [str(name) for name in names]
        for path, names in payload.items()
        if isinstance(names, list)
    }


def _policy_chunk_text_and_metadata(chunk: Any) -> tuple[str, dict[str, Any]]:
    if isinstance(chunk, dict):
        return str(chunk.get("text", "")), dict(chunk.get("metadata") or {})
    return str(getattr(chunk, "text", "")), dict(getattr(chunk, "metadata", {}) or {})


def _parse_required_from_policy_chunks(policy_chunks: list[Any], category_path: str) -> list[str]:
    normalized_category = normalize_category_path(category_path)
    required: list[str] = []
    for chunk in policy_chunks:
        text, metadata = _policy_chunk_text_and_metadata(chunk)
        policy_category = normalize_category_path(str(metadata.get("category", "")))
        if policy_category not in ("", "all", normalized_category):
            continue
        patterns = (
            r"必填属性\s*[:：]\s*([^\n。；;]{2,160})",
            r"必填属性\s*(?:\n\s*)+([^\n。；;]{2,160})",
            r"必须(?:提供|填写|包含)\s*([^\n。；;]{2,160})",
        )
        for pattern in patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                phrase = re.split(r"[。；;]", match.group(1), maxsplit=1)[0]
                phrase = re.sub(r"^.*?必须(?:提供|填写|包含)\s*", "", phrase)
                phrase = re.sub(r"^(?:包括|为|是)\s*", "", phrase)
                for name in re.split(r"[、,，/]|和|及", phrase):
                    cleaned = re.sub(
                        r"(?:等.*|字段.*|属性.*|信息.*|不得.*|应.*)$",
                        "",
                        name,
                    ).strip(" -*：:。")
                    if 1 <= len(cleaned) <= 20:
                        required.append(_canonical_name(cleaned))
    return list(dict.fromkeys(required))


def check_required_attributes(
    extracted_attributes: ExtractedAttributes | dict[str, Any],
    category_path: str,
    policy_chunks: list[Any] | None = None,
) -> list[str]:
    extracted = ExtractedAttributes.model_validate(extracted_attributes)
    normalized = normalize_category_path(category_path)
    required_map = load_required_attributes()
    required = required_map.get(normalized, [])
    if not required:
        required = _parse_required_from_policy_chunks(policy_chunks or [], category_path)

    available: set[str] = set()
    for name, value in extracted.values.items():
        if not _non_empty(value):
            continue
        available.update(_name_variants(str(name)))
    return [name for name in required if not (_name_variants(name) & available)]
