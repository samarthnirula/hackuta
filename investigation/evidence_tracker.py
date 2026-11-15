"""Session evidence ledger. In-memory now; MongoDB Atlas backend plugs in behind the same API.

Rules: never overwrite conflicting claims, dedupe by event_id, ignore stale events.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime

from shared.schemas import ActionPlan, ObservationEvent


@dataclass
class SessionState:
    session_id: str
    events: dict[str, ActionPlan] = field(default_factory=dict)  # event_id -> reply (idempotency)
    latest_ts: datetime | None = None
    target_category: str | None = None  # confirmed object we're helping with
    pending_clarification: str | None = None  # category we asked the user to confirm
    view_attempts: dict[str, int] = field(default_factory=dict)
    claims: list[dict] = field(default_factory=list)
    turns: int = 0


class EvidenceTracker:
    def __init__(self) -> None:
        self._s: dict[str, SessionState] = {}
        self._lock = threading.Lock()

    def session(self, session_id: str) -> SessionState:
        with self._lock:
            return self._s.setdefault(session_id, SessionState(session_id))

    def seen(self, event: ObservationEvent) -> ActionPlan | None:
        return self.session(event.session_id).events.get(event.event_id)

    def is_stale(self, event: ObservationEvent) -> bool:
        s = self.session(event.session_id)
        return s.latest_ts is not None and event.timestamp < s.latest_ts

    def ingest(self, event: ObservationEvent) -> SessionState:
        s = self.session(event.session_id)
        s.latest_ts = max(filter(None, [s.latest_ts, event.timestamp]))
        s.turns += 1
        for o in event.observations:
            s.claims.append({
                "claim_id": o.observation_id, "field": o.kind, "value": o.value,
                "source_type": o.provenance.value, "source_id": o.source_ref,
                "status": "verified" if o.verified else "unverified",
                "observed_at": event.timestamp.isoformat(), "event_id": event.event_id,
            })
        for t in event.visible_text_candidates:
            s.claims.append({
                "claim_id": t.candidate_id, "field": "visible_text", "value": t.text,
                "source_type": "ocr_candidate", "source_id": t.source_ref, "status": "unverified",
                "observed_at": event.timestamp.isoformat(), "event_id": event.event_id,
                "notes": t.ambiguity_notes,
            })
        if event.user_request:
            s.claims.append({
                "claim_id": f"{event.event_id}_utt", "field": "user_request", "value": event.user_request,
                "source_type": "user_report", "source_id": event.event_id, "status": "unverified",
                "observed_at": event.timestamp.isoformat(), "event_id": event.event_id,
            })
        return s

    def record(self, event: ObservationEvent, plan: ActionPlan) -> None:
        self.session(event.session_id).events[event.event_id] = plan

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            self._s.pop(session_id, None)


TRACKER = EvidenceTracker()
