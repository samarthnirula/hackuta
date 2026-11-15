import json
from pathlib import Path

from fastapi.testclient import TestClient

from realtime.decide_server import app

client = TestClient(app)
FIX = Path(__file__).parent / "fixtures"


def test_health():
    assert client.get("/health").json() == {"ok": True}


def test_decide_roundtrip():
    r = client.post("/decide", json=json.loads((FIX / "fridge_vs_laptop.json").read_text()))
    assert r.status_code == 200 and r.json()["in_reply_to"] == "evt_0001"


def test_bad_payload_is_422_not_crash():
    assert client.post("/decide", json={"schema_version": "9"}).status_code == 422
