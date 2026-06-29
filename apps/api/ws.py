from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from apps.api.store import api_store

router = APIRouter()
TERMINAL_EVENTS = {"error", "final_result"}


@router.websocket("/api/runs/{run_id}/events")
async def run_events(websocket: WebSocket, run_id: str) -> None:
    await websocket.accept()
    cursor = 0
    idle_cycles = 0
    try:
        while idle_cycles < 300:
            events = api_store.get_events(run_id, cursor)
            if not events:
                idle_cycles += 1
                await asyncio.sleep(0.1)
                continue
            idle_cycles = 0
            for event in events:
                await websocket.send_json(event.model_dump(mode="json"))
                cursor += 1
                if event.event in TERMINAL_EVENTS:
                    await websocket.close()
                    return
    except WebSocketDisconnect:
        return
    await websocket.close()
