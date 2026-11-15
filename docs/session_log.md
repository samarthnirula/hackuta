# Session log

## 2026-11-14 — first working live FaceTime call (23:10)
**Verified live:** call connects, caller audio reaches agent (after LiveKit 1.8.0 late-input fix), Gemini transcribes,
`decide()` answers in 10–41 ms, agent speaks and **user hears it**.

### Open issues (next session, in priority order)
1. **Object recognition is wrong — top priority.** User showed a **mouse**, said "laptop"; agent reported `obj=laptop`
   and asked about the screen. Contradiction check never fired because the live model echoed the user's word.
   Suspects: (a) Gemini Live frames not reaching the model / too low rate; (b) prompt lets the model copy the user's noun;
   (c) no independent vision check. Plan: verify frames arrive (log video frame count), add an independent
   `gemini-3.5-flash` snapshot classification of the latest frame that does NOT see the user's words, and treat
   disagreement as a contradiction.
2. Second turn too generic ("screen problems" -> repeated first question). Brain needs symptom-aware follow-ups + label request.
3. ~7 s gap between HEARD and reply (tool round-trip through Gemini). Add filler / faster path.
4. Third utterance missed (user spoke while agent speaking). Tune interruption.
5. MongoDB ledger not wired (connection verified). Phase 1 test log + sign-off pending.
6. iMessage repair-guide flow — needs `CHERT_API_KEY` from https://app.trychert.com/developer.

### Run order (all must stay up; laptop must not sleep)
1. Brain: `.venv\Scripts\python -m uvicorn realtime.decide_server:app --port 8787` (repo)
2. Agent: `npm start` in `C:\Users\samar\fixlens-agent` (outside OneDrive)
3. Line: `npx @trychert/facetime@0.1.0-beta.21 dev --agent fixlens-agent --minutes 120` (same folder)
4. If calls are declined for timing: Settings > Time & language > Sync now, then restart 2 and 3.
