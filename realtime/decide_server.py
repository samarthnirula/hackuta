"""Local HTTP bridge so the Node LiveKit agent can call Person 2's decide() as a tool.

Run: python -m uvicorn realtime.decide_server:app --port 8787
Listens on 127.0.0.1 only. Logs redact user text beyond 80 chars.
"""
import logging
import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from investigation.controller import decide
from shared.schemas import ObservationEvent

log = logging.getLogger("fixlens.decide")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
app = FastAPI(title="FixLens decide bridge")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/decide")
def decide_endpoint(payload: dict):
    t0 = time.perf_counter()
    try:
        event = ObservationEvent.model_validate(payload)
    except ValidationError as e:
        log.warning("contract_error %s", e.errors()[:3])
        return JSONResponse(status_code=422, content={"error": "contract_error", "detail": e.errors()[:5]})
    plan = decide(event)
    ms = (time.perf_counter() - t0) * 1000
    log.info("session=%s event=%s action=%s %.0fms", event.session_id, event.event_id, plan.action.value, ms)
    return plan.model_dump(mode="json")
