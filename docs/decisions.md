# Locked decisions (2026-11-14) — agreed by Person 1 and Person 2

| Area | Decision | Why |
|---|---|---|
| Phone line | Chert free HackUTA line (50 FaceTime min, 5-min call cap) | Required by challenge |
| Transport | LiveKit agent run by us, connected via `chert dev` (Node 24 CLI) | This is how Chert works (skills.md) |
| Live voice + vision | Gemini Live in LiveKit Agents (Person 1) | Free key, native video, Gemini prize |
| Reasoning brain | Gemini via Interactions API, model `gemini-4-hydrogen` (per AI Studio get-started docs, 2026-11-14) (Person 2) | One provider, Gemini prize |
| Safety / evidence gates | Deterministic Python rules, never the LLM | Predictable, testable |
| Handoff | Gemini Live calls `decide()` as a **tool** each turn, in-process | Lowest latency, one process |
| Evidence storage | MongoDB Atlas free tier + automatic in-memory fallback | MongoDB prize; call never crashes offline |
| Research | Tavily (search + page text) + iFixit API (guides) | Free, AI-friendly |
| Not used | Ollama, Playwright, LangGraph, vector DB | Too slow / not needed |
| Tone | Friendly + light humor; **no jokes** on hazards, cost, or bad news | Demo personality without risk |
| Demo devices | MacBook Pro M1 (expected label A2338 — verify), phone, refrigerator (mismatch), +1 other | User-provided |
| Extra prizes | Best Use of Gemini, MongoDB Atlas, DEV Writing Challenge | Natural fit |

## Budget reality
- ~10 real calls total (50 min / 5 min). Develop against fixtures; spend live calls only on gate tests.
- Every turn must fit a 5-minute call: spoken replies 1–2 sentences.

## Demo scope (round 2)
- **Real faults:** MacBook Pro M1, cracked screen (visible to camera). iPhone 17 Pro (problem TBD, user-reported unless visible). Refrigerator for mismatch. One random home appliance.
- **Architecture rule: device-agnostic.** No laptop-specific branches in the controller. Device knowledge comes from (a) a small per-category "identifier hints" table (where the model label usually is, safe tests, hazards) with a generic default, and (b) research. Any unseen appliance must still get: identify → label request → safe test → research → answer/refer.
- **Wow moments (all four):** catches fridge-vs-laptop; reads model label live (A2338 → exact iFixit guide); refuses unsafe step (swollen battery); texts an iMessage summary after the call.
- **iMessage summary:** Person 2 composes `SessionSummary` (confirmed / likely / unknown + sources + next step); Person 1 sends via Chert `POST /api/v1/shared-messages`.
  - ⚠️ Free trial: the agent may only *reply* within 24h of the phone's last text → user must text the line once before the demo. Verify on the real line.
