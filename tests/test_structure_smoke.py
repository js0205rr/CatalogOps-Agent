from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_target_project_structure_exists() -> None:
    expected = [
        "apps/api",
        "apps/web",
        "packages/agent_core",
        "packages/catalog",
        "packages/rag_policy",
        "packages/batch_analysis",
        "packages/observability",
        "packages/evaluation",
        "packages/mocks",
        "data/sample_products",
        "data/taxonomy",
        "data/policy_docs",
        "data/eval",
        "scripts",
        "tests",
        "docs",
    ]

    missing = [path for path in expected if not (ROOT / path).exists()]

    assert missing == []


def test_legacy_top_level_apps_are_removed() -> None:
    assert not (ROOT / "server").exists()
    assert not (ROOT / "web").exists()


def test_fastapi_health_route_is_declared() -> None:
    main = (ROOT / "apps" / "api" / "main.py").read_text(encoding="utf-8")
    routes = (ROOT / "apps" / "api" / "routes.py").read_text(encoding="utf-8")

    assert "FastAPI(" in main
    assert '@router.get("/health"' in routes
    assert "response_model=HealthResponse" in routes
