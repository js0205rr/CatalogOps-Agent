from __future__ import annotations

import re
from typing import Any

from packages.catalog.schemas import (
    CategoryPrediction,
    ComplianceIssue,
    ExtractedAttributes,
    ProductInput,
    RevisionSuggestion,
)
from packages.catalog.taxonomy import normalize_category_path, split_category_path


ABSOLUTE_CLAIMS = (
    "全网第一",
    "永久不坏",
    "100%有效",
    "最强",
    "神器",
    "绝对第一",
    "全网最低",
    "顶级",
    "best",
    "no.1",
    "number one",
    "100% guaranteed",
    "guaranteed cheapest",
    "cheapest",
    "miracle",
    "ultimate",
    "unbeatable",
    "never damaged",
)
MARKETING_TERMS = ("爆款", "热卖", "清仓", "特价", "包邮"    "hot sale",
    "clearance",
    "free shipping",
    "discount",
    "best deal",
    "lowest price",
)
FORBIDDEN_REWRITE_TERMS = (
    *ABSOLUTE_CLAIMS,
    *MARKETING_TERMS,
    "全网最低",
    "绝对",
    "第一",
    "顶级",
    "100%正品",
)

CATEGORY_SIGNALS = {
    "手机壳": ("手机壳", "保护壳", "保护套"),
    "手机保护壳": ("手机壳", "保护壳", "保护套"),
    "智能手机": ("智能手机", "手机整机"),
    "蓝牙耳机": ("蓝牙耳机", "无线耳机", "TWS", "入耳式耳机"),
    "空气炸锅": ("空气炸锅", "无油炸锅"),
    "连衣裙": ("连衣裙", "长裙", "吊带裙"),
    "T恤": ("T恤", "短袖", "上衣"),
    "拖把": ("拖把", "平板拖把", "旋转拖把"),
    "坚果": ("坚果", "腰果", "杏仁"),
    "Apparel": ("apparel", "clothing", "wear", "garment"),
    "Tops": ("t-shirt", "tshirt", "shirt", "top", "blouse", "hoodie", "jacket", "coat"),
    "Bottoms": ("jeans", "trouser", "pants", "leggings", "shorts", "jogger"),
    "Dresses": ("dress", "gown", "saree", "kurta", "kurti", "skirt", "romper", "swimwear"),
    "Clothing Sets": ("sets", "outfit", "suit", "tracksuit", "night suit"),
    "Innerwear": ("bra", "brief", "underwear", "innerwear", "lingerie", "vest", "socks"),
    "Shoes": ("shoe", "shoes", "sneaker", "sandal", "slipper", "boot", "footwear"),
    "Bags": ("bag", "wallet", "backpack", "purse", "handbag", "clutch", "tote"),
    "Accessories": ("sunglasses", "belt", "watch", "jewelry", "jewellery", "necklace", "bracelet", "cap", "hat", "scarf", "tie", "hairband", "headband", "glasses"),
}

KEY_ATTRIBUTE_ORDER = (
    "品牌",
    "适用品牌",
    "适用型号",
    "型号",
    "材质",
    "颜色",
    "容量",
    "功率",
    "连接方式",
    "续航时间",
    "功能",
    "brand",
    "product_type",
    "gender",
    "size",
    "color",
    "material",
    "pieces_in_set",
)


def _prediction(value: CategoryPrediction | dict[str, Any]) -> CategoryPrediction:
    return CategoryPrediction.model_validate(value)


def _extracted(value: ExtractedAttributes | dict[str, Any]) -> ExtractedAttributes:
    return ExtractedAttributes.model_validate(value)


def _evidence_ids(product: ProductInput, evidence_ids: list[str] | None) -> list[str]:
    return list(dict.fromkeys([f"product:{product.sku_id}", *(evidence_ids or [])]))


def _issue(
    product: ProductInput,
    rule_name: str,
    message: str,
    suggested_fix: str,
    evidence_ids: list[str],
    *,
    severity: str = "warning",
    matched_span: str = "",
) -> ComplianceIssue:
    return ComplianceIssue(
        issue_id=f"{product.sku_id}:title:{rule_name}",
        issue_type="title_violation",
        severity=severity,  # type: ignore[arg-type]
        message=message,
        evidence_ids=evidence_ids,
        matched_span=matched_span,
        suggested_fix=suggested_fix,
    )


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


def _category_conflicts(title: str, predicted_path: str) -> list[str]:
    leaf = split_category_path(predicted_path)[-1] if split_category_path(predicted_path) else ""
    expected_signals = CATEGORY_SIGNALS.get(leaf, ())
    title_lower = title.lower()
    conflicting: list[str] = []
    for category, signals in CATEGORY_SIGNALS.items():
        if category == leaf or set(signals) == set(expected_signals):
            continue
        if any(_term_in_text(signal, title_lower) for signal in signals):
            conflicting.append(category)
    return conflicting


def check_product_title(
    product: ProductInput | dict[str, Any],
    predicted_category: CategoryPrediction | dict[str, Any],
    *,
    evidence_ids: list[str] | None = None,
) -> list[ComplianceIssue]:
    validated = ProductInput.model_validate(product)
    prediction = _prediction(predicted_category)
    title = re.sub(r"\s+", " ", validated.title).strip()
    issue_evidence = _evidence_ids(validated, evidence_ids)
    issues: list[ComplianceIssue] = []

    absolute_hits = [term for term in ABSOLUTE_CLAIMS if term.lower() in title.lower()]
    if absolute_hits:
        issues.append(
            _issue(
                validated,
                "absolute_claim",
                f"Title contains absolute or exaggerated claim: {', '.join(absolute_hits)}",
                "Remove unsupported absolute or exaggerated claims.",
                issue_evidence,
                severity="blocker",
                matched_span="、".join(absolute_hits),
            )
        )

    marketing_pattern = "|".join(re.escape(term) for term in MARKETING_TERMS)
    marketing_hits = re.findall(marketing_pattern, title, re.IGNORECASE)
    consecutive = re.search(
        rf"(?:{marketing_pattern})(?:[\s,，、|/·-]*(?:{marketing_pattern})){{1,}}",
        title,
        re.IGNORECASE,
    )
    if consecutive or len(marketing_hits) >= 3:
        issues.append(
            _issue(
                validated,
                "keyword_stuffing",
                f"Title contains keyword_stuffing: {', '.join(marketing_hits)}",
                "Keep at most one necessary marketing term and prioritize product information.",
                issue_evidence,
                matched_span=consecutive.group(0) if consecutive else "、".join(marketing_hits),
            )
        )

    meaningful = re.sub(
        rf"(?:{marketing_pattern}|{'|'.join(re.escape(term) for term in ABSOLUTE_CLAIMS)})",
        "",
        title,
        flags=re.IGNORECASE,
    )
    meaningful = re.sub(r"[\W_]+", "", meaningful)
    category_leaf = split_category_path(prediction.category_path)
    leaf = category_leaf[-1] if category_leaf else ""
    has_subject = any(_term_in_text(signal, title.lower()) for signal in CATEGORY_SIGNALS.get(leaf, ()))
    if len(meaningful) < 6 or (leaf and not has_subject and len(title) < 12):
        issues.append(
            _issue(
                validated,
                "insufficient_title",
                "Title is too short or lacks enough product-identifying information.",
                "Include the product subject, applicable object, and key attributes.",
                issue_evidence,
                matched_span=title,
            )
        )

    conflicts = (
        _category_conflicts(title, normalize_category_path(prediction.category_path))
        if prediction.confidence >= 0.65
        else []
    )
    if conflicts:
        issues.append(
            _issue(
                validated,
                "category_conflict",
                (
                    f"Title signals category '{conflicts[0]}' but predicted category is "
                    f"'{prediction.category_path}'."
                ),
                "Confirm the product subject and correct either the title or category.",
                issue_evidence,
                severity="blocker",
                matched_span=title,
            )
        )
    return issues


def _clean_title(title: str) -> str:
    cleaned = title
    for term in FORBIDDEN_REWRITE_TERMS:
        cleaned = re.sub(re.escape(term), " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[!！]{2,}", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip(" -|,，、")


def _product_subject(product: ProductInput, prediction: CategoryPrediction) -> str:
    parts = split_category_path(prediction.category_path)
    leaf = parts[-1] if parts else ""
    for subject, signals in CATEGORY_SIGNALS.items():
        if subject == leaf:
            return next(
                (signal for signal in signals if signal.lower() in product.title.lower()),
                leaf,
            )
    cleaned = _clean_title(product.title)
    return cleaned.split()[0] if cleaned else leaf


def rewrite_product_title(
    product: ProductInput | dict[str, Any],
    issues: list[ComplianceIssue | dict[str, Any]],
    predicted_category: CategoryPrediction | dict[str, Any],
    extracted_attributes: ExtractedAttributes | dict[str, Any],
) -> RevisionSuggestion:
    validated = ProductInput.model_validate(product)
    prediction = _prediction(predicted_category)
    extracted = _extracted(extracted_attributes)
    validated_issues = [ComplianceIssue.model_validate(issue) for issue in issues]

    subject = _product_subject(validated, prediction)
    title_parts: list[str] = []
    for name in KEY_ATTRIBUTE_ORDER:
        value = extracted.values.get(name)
        if not value:
            continue
        if name in {"品牌", "适用品牌", "适用型号", "型号"} or len(title_parts) < 6:
            title_parts.append(value)
    title_parts.insert(min(2, len(title_parts)), subject)
    rewritten = " ".join(dict.fromkeys(part.strip() for part in title_parts if part.strip()))
    if not rewritten:
        rewritten = _clean_title(validated.title)
    rewritten = _clean_title(rewritten)[:60].strip()

    feedback = [issue.suggested_fix or issue.message for issue in validated_issues]
    feedback = list(dict.fromkeys(item for item in feedback if item))
    if prediction.category_path:
        feedback.insert(0, f"Recommended category: {prediction.category_path}")
    return RevisionSuggestion(
        title=rewritten,
        category=prediction.category_path,
        attributes=dict(extracted.values),
        seller_feedback=feedback,
        evidence_ids=list(
            dict.fromkeys(
                evidence_id
                for issue in validated_issues
                for evidence_id in issue.evidence_ids
            )
        ),
    )
