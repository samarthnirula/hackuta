"""Phase 1 Person 2 acceptance tests (master doc §12)."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from investigation.controller import decide
from investigation.evidence_tracker import TRACKER
from shared.schemas import Action

FIX = Path(__file__).parent / "fixtures"


def ev(name, **over):
    d = json.loads((FIX / name).read_text())
    d.update(over)
    TRACKER.clear_session(d["session_id"])
    return d


def test_1_fridge_vs_laptop_clarifies():
    p = decide(ev("fridge_vs_laptop.json"))
    assert p.action is Action.ASK_USER
    assert "refrigerator" in p.message and "laptop" in p.message
    assert "screen" not in p.message.lower()  # no laptop repair advice
    assert all(c.supporting_evidence for c in p.claims)


def test_1b_then_user_confirms_then_shows_laptop():
    e = ev("fridge_vs_laptop.json")
    decide(e)
    p = decide(e | {"event_id": "evt_a2", "timestamp": "2026-11-14T22:00:05Z", "user_request": "yeah the fridge"})
    assert "refrigerator it is" in p.message
    lap = json.loads((FIX / "generic_laptop.json").read_text())
    p = decide(lap | {"session_id": e["session_id"], "event_id": "evt_a3",
                      "timestamp": "2026-11-14T22:00:10Z", "user_request": "actually here's my laptop"})
    assert "crack" in p.message  # noticed the change, uses new observation


def test_2_blurry_requests_view_then_changes_strategy():
    e = ev("blurry_frame.json")
    assert decide(e).action is Action.REQUEST_VIEW
    decide(e | {"event_id": "b2", "timestamp": "2026-11-14T22:01:05Z"})
    p = decide(e | {"event_id": "b3", "timestamp": "2026-11-14T22:01:10Z"})
    assert p.action is Action.ASK_USER and "tell me" in p.message  # never repeat forever


def test_3_generic_laptop_no_brand_or_model():
    p = decide(ev("generic_laptop.json"))
    low = p.message.lower()
    for brand in ("apple", "macbook", "dell", "hp", "lenovo", "a2338"):
        assert brand not in low


def test_4_duplicate_event_is_idempotent():
    e = ev("generic_laptop.json")
    assert decide(e).event_id == decide(e).event_id
    assert len(TRACKER.session(e["session_id"]).claims) == 4  # 3 obs + 1 utterance, not doubled


def test_5_malformed_rejected():
    with pytest.raises(ValidationError):
        decide({"schema_version": "1.0", "event_id": "x"})


def test_6_provenance_kept_distinct():
    e = ev("readable_label.json")
    decide(e)
    types = {c["source_type"] for c in TRACKER.session(e["session_id"]).claims}
    assert {"camera_frame", "ocr_candidate", "user_report"} <= types


def test_label_is_candidate_not_verified():
    p = decide(ev("readable_label.json"))
    assert p.action is Action.SEARCH
    assert all(c.certainty.value != "confirmed" for c in p.claims)


def test_part_request_needs_model_first():
    p = decide(ev("generic_laptop.json", user_request="which replacement screen should I buy?"))
    assert p.action is Action.REQUEST_VIEW and "guess" in p.message


def test_heavy_appliance_never_asked_to_move():
    e = ev("fridge_vs_laptop.json", user_request="what model is my fridge?")
    p = decide(e)
    assert p.action is Action.REQUEST_VIEW and "without moving" in p.message


def test_unknown_appliance_still_works():
    e = ev("generic_laptop.json")
    e["observations"] = [{"observation_id": "o1", "kind": "object_class", "value": "dehumidifier",
                          "confidence": 0.8, "provenance": "camera_frame", "source_ref": "f1"}]
    e["user_request"] = "it stopped working"
    p = decide(e)
    assert p.action is Action.ASK_USER and "dehumidifier" in p.message


def test_stale_event_does_not_overwrite():
    e = ev("generic_laptop.json")
    decide(e)
    p = decide(e | {"event_id": "old", "timestamp": "2026-11-14T21:00:00Z"})
    assert p.action is Action.RECOVER_SESSION
