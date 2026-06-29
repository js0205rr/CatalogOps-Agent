from __future__ import annotations

import io

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("langgraph")
pytest.importorskip("pydantic")

from fastapi.testclient import TestClient

from apps.api.main import app


client = TestClient(app)


def _csv_upload():
    content = (
        "product_id,title,description,seller_category,attributes,seller_id,price\n"
        'P-1,iPhone 15 透明手机壳,TPU 防摔保护壳,数码配件/手机配件/手机壳,"{""材质"":""TPU""}",S-1,39.9\n'
        "P-2,,,,,S-2,9.9\n"
    )
    return {"file": ("catalog.csv", io.BytesIO(content.encode("utf-8-sig")), "text/csv")}


def test_batch_upload_run_and_report() -> None:
    uploaded = client.post("/api/batch/upload", files=_csv_upload())
    assert uploaded.status_code == 200
    batch = uploaded.json()
    assert batch["status"] == "uploaded"

    before_run = client.get(f"/api/batch/{batch['batch_id']}/report")
    assert before_run.status_code == 200
    assert before_run.json()["status"] == "uploaded"
    assert before_run.json()["report"] is None

    run = client.post(f"/api/batch/{batch['batch_id']}/run")
    assert run.status_code == 200
    result = run.json()
    assert result["status"] == "completed"
    assert result["report"]["profile"]["row_count"] == 2
    assert sum(result["report"]["metrics"]["decision_distribution"].values()) == 2

    report = client.get(f"/api/batch/{batch['batch_id']}/report")
    assert report.status_code == 200
    assert report.json()["status"] == "completed"
    assert 1 in report.json()["report"]["selected_rows"]

    events = []
    with client.websocket_connect(f"/api/runs/{result['run_id']}/events") as websocket:
        while True:
            try:
                events.append(websocket.receive_json())
            except Exception:
                break
    assert {"node_start", "node_end", "tool_start", "tool_end", "final_result"} <= {
        event["event"] for event in events
    }


def test_batch_upload_rejects_non_csv() -> None:
    response = client.post(
        "/api/batch/upload",
        files={"file": ("catalog.txt", b"not csv", "text/plain")},
    )
    assert response.status_code == 400
