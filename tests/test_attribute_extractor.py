from __future__ import annotations

import pytest

pytest.importorskip("pydantic")

from packages.catalog.attribute_extractor import (
    check_required_attributes,
    extract_product_attributes,
)
from packages.catalog.schemas import ExtractedAttributes, ProductInput


PHONE_CASE = "数码配件/手机配件/手机壳"


def test_extract_product_attributes_prefers_merchant_attributes() -> None:
    product = ProductInput(
        sku_id="CASE-ATTR-1",
        title="iPhone 15 Pro 防摔磁吸 TPU 手机壳 白色",
        description="适用 iPhone 15 Pro，支持无线充电",
        attributes={"颜色": "黑色", "品牌": "Acme"},
    )

    result = extract_product_attributes(product, PHONE_CASE)

    assert result.values["颜色"] == "黑色"
    assert result.values["品牌"] == "Acme"
    assert result.values["适用型号"] == "iPhone 15 Pro"
    assert result.values["适用品牌"] == "Apple"
    assert "TPU" in result.values["材质"]
    assert "防摔" in result.values["功能"]


def test_extract_bluetooth_headset_attributes() -> None:
    product = ProductInput(
        title="Sony WF-1000XM5 蓝牙 5.3 主动降噪耳机",
        description="续航时间 24 小时",
        attributes={"型号": "WF-1000XM5"},
    )

    result = extract_product_attributes(product, "数码配件/音频设备/蓝牙耳机")

    assert result.values["品牌"] == "Sony"
    assert result.values["型号"] == "WF-1000XM5"
    assert result.values["连接方式"] == "蓝牙 5.3"
    assert result.values["续航时间"] == "24 小时"
    assert "主动降噪" in result.values["功能"]


def test_check_required_attributes_prefers_structured_taxonomy() -> None:
    extracted = ExtractedAttributes(
        values={"品牌": "Acme", "适用型号": "iPhone 15", "材质": "TPU"}
    )

    missing = check_required_attributes(extracted, PHONE_CASE, policy_chunks=[])

    assert missing == ["颜色"]


def test_check_required_attributes_falls_back_to_policy_chunks() -> None:
    extracted = ExtractedAttributes(values={"品牌": "Acme"})
    policy_chunks = [
        {
            "text": "该类目发布前必须提供品牌、型号、功率。",
            "metadata": {"category": "测试类目/测试叶子"},
        }
    ]

    missing = check_required_attributes(extracted, "测试类目/测试叶子", policy_chunks)

    assert missing == ["型号", "功率"]
