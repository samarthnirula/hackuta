"""Shared contract tests (BOTH). Must pass on both machines before Phase 1."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from investigation.controller import decide
from shared.schemas import Action, ActionPlan, ObservationEvent

FIXTURES = sorted((Path(__file__).parent / "fixtures").glob("*.json"))


def load(name: str) -> dict:
    return json.loads((Path(__file__).parent / "fixtures" / name).read_text())


def test_five_fixtures_exist():
    assert len(FIXTURES) == 5


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_fixture_validates_and_decide_returns_plan(path):
    event = ObservationEvent.model_validate_json(path.read_text())
    plan = decide(event)
    assert isinstance(plan, ActionPlan)
    assert plan.session_id == event.session_id
    assert plan.in_reply_to == event.event_id
    ActionPlan.model_validate_json(plan.model_dump_json(by_alias=False))  # round-trip


def test_bad_schema_version_rejected():
    data = load("fridge_vs_laptop.json") | {"schema_version": "2.0"}
    with pytest.raises(ValidationError):
        ObservationEvent.model_validate(data)


def test_unknown_field_rejected():
    data = load("fridge_vs_laptop.json") | {"surprise": 1}
    with pytest.raises(ValidationError):
        ObservationEvent.model_validate(data)


def test_unknown_action_rejected():
    with pytest.raises(ValidationError):
        ActionPlan.model_validate({"event_id": "e", "session_id": "s", "in_reply_to": "x",
                                   "action": "improvise", "message": "hi"})


def test_person1_aliases_accepted():
    data = load("fridge_vs_laptop.json")
    data["user_utterance"] = data.pop("user_request")
    assert ObservationEvent.model_validate(data).user_request == "Can you fix this laptop?"
    plan = ActionPlan.model_validate({"event_id": "e", "session_id": "s", "in_reply_to": "x",
                                      "action": "ask_user", "spoken_text": "hi"})
    assert plan.spoken_text == "hi"


def test_hazard_fixture_stops():
    plan = decide(load("swollen_battery.json"))
    assert plan.action is Action.STOP_UNSAFE and plan.safety.blocked
