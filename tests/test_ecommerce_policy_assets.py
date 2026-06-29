from __future__ import annotations

import json
from pathlib import Path

from packages.rag_policy.ingestion.chunker import chunk_policy_document
from packages.rag_policy.ingestion.loader import load_policy_document


ROOT = Path(__file__).resolve().parents[1]
TAXONOMY_DIR = ROOT / "data" / "taxonomy"
POLICY_DIR = ROOT / "data" / "policy_docs"


def test_ecommerce_taxonomy_and_required_attributes_cover_three_domains() -> None:
    keywords = json.loads((TAXONOMY_DIR / "category_keywords.json").read_text(encoding="utf-8"))
    catalog = json.loads((TAXONOMY_DIR / "catalog_taxonomy.json").read_text(encoding="utf-8"))
    required = json.loads((TAXONOMY_DIR / "required_attributes.json").read_text(encoding="utf-8"))

    keyword_paths = {item["category_path"] for item in keywords}
    catalog_paths = {item["category_path"] for item in catalog}
    required_paths = set(required)
    expected = {
        "Electronics",
        "Electronics > Mobile Phones",
        "Electronics > Audio",
        "Household",
        "Household > Kitchen & Dining",
        "Household > Furniture",
        "Books",
        "Books > Fiction",
        "Books > Academic & Exam Prep",
    }

    assert expected <= keyword_paths
    assert expected <= catalog_paths
    assert expected <= required_paths
    assert required["Electronics > Mobile Phones"] == [
        "brand",
        "product_type",
        "model",
        "storage_capacity",
        "network_type",
    ]


def test_ecommerce_policy_docs_have_structured_metadata_and_chunks() -> None:
    expected_files = [
        "electronics_category_policy.md",
        "electronics_attribute_schema.md",
        "electronics_title_policy.md",
        "electronics_mismatch_cases.md",
        "electronics_prohibited_claims_policy.md",
        "household_category_policy.md",
        "household_attribute_schema.md",
        "household_title_policy.md",
        "household_mismatch_cases.md",
        "household_prohibited_claims_policy.md",
        "books_category_policy.md",
        "books_attribute_schema.md",
        "books_title_policy.md",
        "books_mismatch_cases.md",
        "books_prohibited_claims_policy.md",
    ]

    for filename in expected_files:
        document = load_policy_document(POLICY_DIR / filename)
        assert document.metadata["category"] in {"Electronics", "Household", "Books"}
        assert document.metadata["doc_type"] in {"category_policy", "attribute_schema", "title_policy"}
        assert document.metadata["effective_date"] == "2026-01-01"
        chunks = chunk_policy_document(document)
        assert chunks
        assert all(chunk.metadata["category"] == document.metadata["category"] for chunk in chunks)
