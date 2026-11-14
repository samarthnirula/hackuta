# Chert capability matrix (HackUTA free tier)

Status values: VERIFIED / UNVERIFIED / BLOCKED. Evidence = doc link or redacted test log.

| Capability | Owner | Status | Evidence | Fallback |
|---|---|---|---|---|
| Live incoming audio | P1 | UNVERIFIED | | Text fixtures (dev only) |
| Live incoming video/frame access | P1 | UNVERIFIED | | Model-native visual description; disclose limit |
| Spoken output | P1 | UNVERIFIED | | Text response |
| Outgoing annotated video | P1 | UNVERIFIED | | Verbal camera guidance |
| Interruption / reconnect | P1 | UNVERIFIED | | Restart session, `recover_session` |
| Tool / HTTP calls during a call | P2 | LIKELY — agent is our own LiveKit code (skills.md) | app.trychert.com/skills.md | Server-side orchestration |
| Allowed LLM provider/model | P2 | VERIFIED — bring your own keys (skills.md) | app.trychert.com/skills.md | Deterministic rules only |
| Quotas | Both | DOCUMENTED — free trial 50 FaceTime min, 5-min calls | app.trychert.com/skills.md | Fixtures; save calls for gates |
| Recording / data retention | Both | UNVERIFIED | | Disable recording; no persisted media |
| Search API (Tavily + iFixit) | P2 | UNVERIFIED (need key) | | Explicit research-unavailable state |

## Integration boundary (agreed v1.0, pending P1 sign-off)
- In-process call: `from investigation.controller import decide` → `decide(ObservationEvent) -> ActionPlan`.
- P1 owns timestamps, retries, 3s decision timeout. P2 owns idempotency by `event_id`.
- Aliases for P1's brief: `user_utterance` → `user_request`, `spoken_text` → `message`.
