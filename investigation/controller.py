"""Investigation controller entry point used by Person 1.

PHASE 0 STUB: always returns a valid ask_user plan (or stop_unsafe if the safety
matrix trips). Real contradiction / next-best-action logic lands in Phase 1.
"""
from __future__ import annotations

import uuid
from typing import Any

from investigation import safety
from shared.schemas import Action, ActionPlan, ObservationEvent, Safety, SafetyClass

STUB_MODE = True  # visibly labeled per master doc §16


def decide(event: ObservationEvent | dict[str, Any]) -> ActionPlan:
    if not isinstance(event, ObservationEvent):
        event = ObservationEvent.model_validate(event)  # raises ValidationError on bad input

    texts = [event.user_request or ""] + [o.value or "" for o in event.observations]
    cls, category = safety.classify(texts)
    reply_id = f"evt_{uuid.uuid4().hex[:12]}"

    if cls is SafetyClass.BLOCKED:
        return ActionPlan(
            event_id=reply_id,
            session_id=event.session_id,
            in_reply_to=event.event_id,
            action=Action.STOP_UNSAFE,
            message="Please stop here. This may be unsafe to handle yourself; "
                    "don't open, press, or charge it. A qualified technician should look at it.",
            needs_more_evidence=False,
            safety=Safety(classification=cls, blocked=True, reason=category),
        )

    return ActionPlan(
        event_id=reply_id,
        session_id=event.session_id,
        in_reply_to=event.event_id,
        action=Action.ASK_USER,
        message="[STUB] Can you tell me a bit more about what's wrong?",
        needs_more_evidence=True,
    )
