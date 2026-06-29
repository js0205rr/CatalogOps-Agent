from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

import httpx
import websockets


SAMPLE_PRODUCT = {
    "sku_id": "P1002",
    "title": "best 100% guaranteed cotton shirt white",
    "description": "Basic short sleeve top. Size: M.",
    "seller_category": "Clothing & Accessories > Tops",
    "merchant_category": "Clothing & Accessories > Tops",
    "attributes": {"material": "cotton", "size": "M", "color": "white"},
}

SAMPLE_CSV = """product_id,title,description,seller_category,attributes,seller_id,price
P-1,Cotton Shirt White,Basic top,Clothing & Accessories > Tops,"{""material"":""cotton""}",S-1,19.9
P-2,Wireless Headphones,Noise cancelling,Electronics > Audio,"{""brand"":""Acme""}",S-2,59.9
"""


def _ws_base(http_base: str) -> str:
    return http_base.replace("https://", "wss://").replace("http://", "ws://").rstrip("/")


async def _collect_events(ws_url: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    async with websockets.connect(ws_url) as websocket:
        while True:
            try:
                raw = await asyncio.wait_for(websocket.recv(), timeout=5)
            except Exception:
                break
            events.append(json.loads(raw))
    return events


async def run_smoke(base_url: str) -> dict[str, Any]:
    base = base_url.rstrip("/")
    async with httpx.AsyncClient(timeout=30) as client:
        health = await client.get(f"{base}/health")
        health.raise_for_status()

        single = await client.post(f"{base}/api/reviews/single", json=SAMPLE_PRODUCT)
        single.raise_for_status()
        review = single.json()
        run_id = review["trace_id"]
        events = await _collect_events(f"{_ws_base(base)}/api/runs/{run_id}/events")

        upload = await client.post(
            f"{base}/api/batch/upload",
            files={"file": ("smoke.csv", SAMPLE_CSV.encode("utf-8"), "text/csv")},
        )
        upload.raise_for_status()
        batch_id = upload.json()["batch_id"]
        batch_run = await client.post(f"{base}/api/batch/{batch_id}/run")
        batch_run.raise_for_status()
        batch_report = batch_run.json()["report"]

        policy = await client.post(
            f"{base}/api/chat/policy",
            json={"question": "Can a title say guaranteed best ever?", "top_k": 3},
        )
        policy.raise_for_status()
        policy_result = policy.json()

    event_types = sorted({event["event"] for event in events})
    required_events = {"node_start", "node_end", "tool_start", "tool_end", "final_result"}
    if not required_events <= set(event_types):
        missing = ", ".join(sorted(required_events - set(event_types)))
        raise RuntimeError(f"WebSocket trace missing events: {missing}")
    if not review.get("evidence"):
        raise RuntimeError("single review returned no evidence")
    if batch_report["profile"]["row_count"] != 2:
        raise RuntimeError("batch smoke row count mismatch")
    if not policy_result.get("hits"):
        raise RuntimeError("policy QA returned no hits")

    return {
        "health": health.json(),
        "single": {
            "trace_id": run_id,
            "decision": review["publish_decision"],
            "issues": len(review["compliance_issues"]),
            "evidence": len(review["evidence"]),
        },
        "websocket": {"events": len(events), "event_types": event_types},
        "batch": {
            "batch_id": batch_id,
            "rows": batch_report["profile"]["row_count"],
            "selected_rows": len(batch_report["selected_rows"]),
        },
        "policy": {"hits": len(policy_result["hits"])},
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Smoke test CatalogOps API, batch review, policy QA, and WebSocket trace."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    try:
        result = asyncio.run(run_smoke(args.base_url))
    except Exception as exc:
        print(f"smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
