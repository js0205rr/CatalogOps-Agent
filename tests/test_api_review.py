from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("langgraph")
pytest.importorskip("pydantic")

from fastapi.testclient import TestClient

from apps.api.main import app


client = TestClient(app)


def test_new_api_routes_have_response_schemas() -> None:
    openapi = client.get("/openapi.json").json()
    expected = {
        "/health",
        "/api/reviews/single",
        "/api/batch/upload",
        "/api/batch/{batch_id}/run",
        "/api/batch/{batch_id}/report",
        "/api/documents/upload",
        "/api/documents/ingest",
        "/api/documents",
        "/api/chat/policy",
        "/api/policy/category",
        "/api/policy/attributes",
        "/api/policy/title",
    }
    assert expected <= set(openapi["paths"])
    for path in expected:
        operation = next(iter(openapi["paths"][path].values()))
        schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
        assert schema


def test_health_endpoint_and_cors() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "catalogops-agent",
        "mock_ready": True,
    }

    preflight = client.options(
        "/api/reviews/single",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_single_review_endpoint_runs_graph_and_exposes_events() -> None:
    response = client.post(
        "/api/reviews/single",
        json={
            "sku_id": "P1002",
            "title": "best 100% guaranteed cotton shirt white",
            "description": "Basic short sleeve top. Size: M.",
            "seller_category": "Clothing & Accessories > Tops",
            "merchant_category": "Clothing & Accessories > Tops",
            "attributes": {"material": "cotton", "size": "M", "color": "white"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["trace_id"].startswith("run-")
    assert payload["publish_decision"] in {"reject", "human_review"}
    assert payload["compliance_issues"]

    events = []
    with client.websocket_connect(f"/api/runs/{payload['trace_id']}/events") as websocket:
        while True:
            try:
                events.append(websocket.receive_json())
            except Exception:
                break

    event_types = {event["event"] for event in events}
    assert {"node_start", "node_end", "tool_start", "tool_end", "final_result"} <= event_types
    assert all(event["run_id"] == payload["trace_id"] for event in events)


def test_business_routes_use_catalogops_api_prefix() -> None:
    openapi = client.get("/openapi.json").json()
    custom_paths = {
        path
        for path in openapi["paths"]
        if not path.startswith(("/docs", "/openapi", "/redoc"))
    }
    assert all(path in {"/", "/health"} or path.startswith("/api/") for path in custom_paths)
