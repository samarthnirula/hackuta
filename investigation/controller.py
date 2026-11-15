"""Investigation controller: decide(ObservationEvent) -> ActionPlan.

Deterministic gates (safety, contradiction, quality, identity). No LLM here yet,
so behaviour is predictable and testable. Device-agnostic via device_hints.
"""
from __future__ import annotations

import re
import uuid
from typing import Any

from investigation import device_hints, safety
from investigation.evidence_tracker import TRACKER, SessionState
from shared.schemas import (
    Action, ActionPlan, Certainty, Claim, Observation, ObservationEvent,
    RequestedView, Safety, SafetyClass,
)

MAX_VIEW_ATTEMPTS = 2
_AFFIRM = re.compile(r"\b(yes|yeah|yep|yup|correct|right|sure|that one|exactly)\b", re.I)
_NEEDS_ID = re.compile(r"\b(model|part|replace|replacement|buy|order|price|cost|which (screen|battery)|year|serial)\b", re.I)


def _plan(event: ObservationEvent, action: Action, message: str, **kw: Any) -> ActionPlan:
    return ActionPlan(
        event_id=f"evt_{uuid.uuid4().hex[:12]}", session_id=event.session_id,
        in_reply_to=event.event_id, action=action, message=message, **kw,
    )


def _main_object(event: ObservationEvent) -> Observation | None:
    objs = [o for o in event.observations if o.kind == "object_class" and o.value]
    return max(objs, key=lambda o: o.confidence or 0.0) if objs else None


def _label(cat: str | None) -> str:
    return (cat or "object").replace("_", " ")


def decide(event: ObservationEvent | dict[str, Any]) -> ActionPlan:
    if not isinstance(event, ObservationEvent):
        event = ObservationEvent.model_validate(event)

    if (prev := TRACKER.seen(event)) is not None:  # idempotent
        return prev
    if TRACKER.is_stale(event):
        return _plan(event, Action.RECOVER_SESSION, "Hang on, I got a bit behind. Can you show me that again?")

    s = TRACKER.ingest(event)
    plan = _decide(event, s)
    TRACKER.record(event, plan)
    return plan


def _decide(event: ObservationEvent, s: SessionState) -> ActionPlan:
    obj = _main_object(event)
    observed = device_hints.canonical(obj.value) if obj else None
    mentioned = device_hints.mentioned_category(event.user_request)
    obj_ev = [obj.observation_id] if obj else []

    # 1. Safety first, always.
    texts = [event.user_request or ""] + [o.value or "" for o in event.observations]
    cls, category = safety.classify(texts)
    if cls is SafetyClass.BLOCKED:
        return _plan(
            event, Action.STOP_UNSAFE,
            "Okay, let's pause right there. That could be dangerous, so please don't open, press, "
            "puncture, or charge it. Unplug it only if that's safe, keep it away from anything flammable, "
            "and take it to a qualified repair shop.",
            needs_more_evidence=False,
            safety=Safety(classification=cls, blocked=True, reason=category),
            claims=[Claim(text=f"Possible hazard: {category.replace('_', ' ')}",
                          supporting_evidence=[o.observation_id for o in event.observations],
                          certainty=Certainty.LIKELY)],
        )

    # 2. Resolve a pending clarification ("Did you mean the fridge?" -> "yes").
    if s.pending_clarification and event.user_request and _AFFIRM.search(event.user_request):
        s.target_category, s.pending_clarification = s.pending_clarification, None
        h = device_hints.hints_for(s.target_category)
        return _plan(event, Action.ASK_USER, f"Got it, the {_label(s.target_category)} it is. {h.first_question}")

    # 3. Can we actually see anything?
    bad_frame = event.frame_quality.status in ("unusable", "unavailable") or obj is None
    if bad_frame:
        key = f"{s.target_category or 'any'}:overview"
        s.view_attempts[key] = s.view_attempts.get(key, 0) + 1
        issues = ", ".join(event.frame_quality.issues) or "not clear"
        if s.view_attempts[key] > MAX_VIEW_ATTEMPTS:
            return _plan(event, Action.ASK_USER,
                         "The camera's still struggling, no worries. Can you just tell me what it is "
                         "and what's going wrong with it?")
        return _plan(
            event, Action.REQUEST_VIEW,
            "I can't quite make it out yet. Could you hold it steady, a bit closer, with some light on it?",
            requested_view=RequestedView(target_object=_label(s.target_category or mentioned),
                                         view="steady, well-lit overview",
                                         reason=f"frame quality: {issues}",
                                         safe_alternative="describe the object and the problem out loud"),
        )

    # 4. Contradiction: user names one thing, camera shows another.
    if mentioned and observed and mentioned != observed and s.target_category != observed:
        s.pending_clarification = observed
        return _plan(
            event, Action.ASK_USER,
            f"Quick check: I can see what looks like a {_label(observed)}, not a {_label(mentioned)}. "
            f"Unless that's a very cold laptop, is the {_label(observed)} what you need help with?"
            if mentioned == "laptop" and observed == "refrigerator" else
            f"Quick check: I can see what looks like a {_label(observed)}, not a {_label(mentioned)}. "
            f"Is the {_label(observed)} what you need help with?",
            claims=[Claim(text=f"The visible object appears to be a {_label(observed)}.",
                          supporting_evidence=obj_ev, certainty=Certainty.LIKELY),
                    Claim(text=f"User described it as a {_label(mentioned)}.",
                          supporting_evidence=[f"{event.event_id}_utt"], certainty=Certainty.UNKNOWN)],
        )

    # 5. Object changed or first seen: adopt it as the target.
    new_target = observed != s.target_category
    if observed:
        s.target_category, s.pending_clarification = observed, None
    h = device_hints.hints_for(s.target_category)
    damage = [o for o in event.observations if o.kind == "visible_damage" and o.value]
    base_claims = [Claim(text=f"The visible object appears to be a {_label(observed)}.",
                         supporting_evidence=obj_ev, certainty=Certainty.LIKELY)]

    # 6. Text on a label: report as a candidate, never as verified identity.
    if event.visible_text_candidates:
        c = max(event.visible_text_candidates, key=lambda t: t.confidence or 0.0)
        if c.ambiguity_notes or (c.confidence is not None and c.confidence < 0.6) or len(event.visible_text_candidates) > 1:
            return _plan(event, Action.ASK_USER,
                         f"I think the label says {c.text}, but I'm not certain about every character. "
                         "Can you read it out to me, or hold it a little closer?",
                         claims=base_claims + [Claim(text=f"Label text candidate: {c.text}",
                                                     supporting_evidence=[c.candidate_id], certainty=Certainty.UNKNOWN)])
        return _plan(event, Action.SEARCH,
                     f"Nice, I can read {c.text} on the label. Let me look that up to confirm the exact model.",
                     claims=base_claims + [Claim(text=f"Label text candidate: {c.text}",
                                                 supporting_evidence=[c.candidate_id], certainty=Certainty.LIKELY)])

    # 7. User wants something model-specific (part, price, year): get an identifier first.
    if event.user_request and _NEEDS_ID.search(event.user_request):
        key = f"{s.target_category}:label"
        s.view_attempts[key] = s.view_attempts.get(key, 0) + 1
        if event.user_constraints.cannot_move_object or s.view_attempts[key] > MAX_VIEW_ATTEMPTS or h.heavy:
            return _plan(event, Action.REQUEST_VIEW,
                         f"To get the exact part right I need the model. Easiest way is {h.label_alternative}, "
                         f"or {h.label_location} if you can reach it without moving anything heavy.",
                         requested_view=RequestedView(target_object=_label(s.target_category), view="model identifier",
                                                      reason="exact model required before part/price advice",
                                                      safe_alternative=h.label_alternative),
                         claims=base_claims)
        return _plan(event, Action.REQUEST_VIEW,
                     f"I won't guess the exact model from looks alone. Can you show me {h.label_location}?",
                     requested_view=RequestedView(target_object=_label(s.target_category), view=h.label_location,
                                                  reason="exact model required before part/price advice",
                                                  safe_alternative=h.label_alternative),
                     claims=base_claims)

    # 8. Visible damage: describe what's seen, not a root cause.
    if damage:
        d = damage[0]
        return _plan(event, Action.ASK_USER,
                     f"I can see {d.value}. When did that happen, and is it still working otherwise? "
                     "Also, could you show me "
                     f"{h.label_location} so I know exactly which model this is?",
                     claims=base_claims + [Claim(text=f"Visible damage: {d.value}",
                                                 supporting_evidence=[d.observation_id], certainty=Certainty.LIKELY)])

    # 9. Default: one useful question.
    msg = (f"Okay, I can see the {_label(s.target_category)}. {h.first_question}" if new_target
           else h.first_question)
    return _plan(event, Action.ASK_USER, msg, claims=base_claims)
