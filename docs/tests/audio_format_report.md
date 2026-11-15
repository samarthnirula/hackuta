# Audio format test report — FixLens × Chert

**Date:** 2026-11-14 · **Tester:** Person 2 (automated) · **LiveKit:** own Cloud project (US Central) · **Agent SDK:** @livekit/agents 1.8.0, rtc-node 0.13.35

## Purpose
FaceTime calls through Chert line +1 206-465-5399 connect with video both ways, but **no audio in either direction**.
This test isolates which link is broken by sending real Gemini speech through LiveKit in every format we could plausibly use, then recording and transcribing what a separate receiver gets.

## Method
1. **Source:** Gemini Live (`gemini-3.8-live`, voice Puck) greeting, recorded in-room from the FixLens agent (24 kHz mono, 5.3 s of speech).
2. **Sender:** a LiveKit participant publishes it as one microphone track per variant (sample rate × channels × RED × DTX), plus two controls: 4× gain (clipping) and pure digital silence.
3. **Receiver:** a second participant subscribes, decodes to 48 kHz mono PCM, saves a WAV, and measures RMS/peak.
4. **Judge:** Gemini (`gemini-3.5-flash`) transcribes each WAV and rates quality; word error rate (WER) vs. the known sentence ("Fix Lens" normalised to "FixLens").

Scripts: [`scripts/matrix.mjs`](../../scripts/matrix.mjs) · raw data: [`audio_format_results.json`](audio_format_results.json)

## Results
| Variant | Rate | Ch | Codec | Wire mime | Sent / recv (s) | RMS | Peak | Gemini quality | WER | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| 16k_mono_opus | 16 kHz | mono | Opus | `audio/opus` | 5.32 / 6.99 | 2813 | 26290 | CLEAN | 0.0 | ✅ |
| 16k_mono_red | 16 kHz | mono | RED | `audio/red` | 5.32 / 7.06 | 2793 | 26035 | CLEAN | 0.0 | ✅ |
| 16k_stereo_opus | 16 kHz | stereo | Opus | `audio/opus` | 5.32 / 7.05 | 2798 | 25424 | CLEAN | 0.0 | ✅ |
| 16k_stereo_red | 16 kHz | stereo | RED | `audio/red` | 5.32 / 7.06 | 2795 | 25207 | CLEAN | 0.0 | ✅ |
| 24k_mono_opus | 24 kHz | mono | Opus | `audio/opus` | 5.32 / 7.06 | 2810 | 26423 | CLEAN | 0.0 | ✅ |
| 24k_mono_red | 24 kHz | mono | RED | `audio/red` | 5.32 / 7.05 | 2811 | 26104 | CLEAN | 0.0 | ✅ |
| 24k_stereo_opus | 24 kHz | stereo | Opus | `audio/opus` | 5.32 / 7.05 | 2816 | 26122 | CLEAN | 0.0 | ✅ |
| 24k_stereo_red | 24 kHz | stereo | RED | `audio/red` | 5.32 / 7.04 | 2802 | 26122 | CLEAN | 0.0 | ✅ |
| 48k_mono_opus | 48 kHz | mono | Opus | `audio/opus` | 5.32 / 7.05 | 2803 | 25730 | CLEAN | 0.0 | ✅ |
| 48k_mono_red | 48 kHz | mono | RED | `audio/red` | 5.32 / 7.06 | 2799 | 25730 | CLEAN | 0.0 | ✅ |
| 48k_stereo_opus | 48 kHz | stereo | Opus | `audio/opus` | 5.32 / 7.05 | 2803 | 25730 | CLEAN | 0.0 | ✅ |
| 48k_stereo_red | 48 kHz | stereo | RED | `audio/red` | 5.32 / 7.05 | 2802 | 25631 | CLEAN | 0.0 | ✅ |
| 48k_mono_opus_dtx | 48 kHz | mono | Opus +DTX | `audio/opus` | 5.32 / 7.03 | 2810 | 25730 | CLEAN | 0.0 | ✅ |
| clipping (4x gain) | 24 kHz | mono | Opus | `audio/opus` | 5.32 / 7.04 | 9065 | 32768 | CLEAN | 0.0 | ✅ |
| digital silence | 24 kHz | mono | Opus | `audio/opus` | 5.32 / 7.01 | 0 | 1 | CLEAN | — | ⚠️ expected silence |

*Received duration is ~1.7 s longer than sent because recording includes join/teardown padding; identical across variants.*

## Findings
1. **Every speech format works through LiveKit.** 16/24/48 kHz, mono/stereo, Opus/RED, DTX: all arrive with full level (RMS ≈ 2800) and transcribe with 0 WER. **Format is not the cause of the silent calls.** Disabling RED in the agent was harmless but not the fix.
2. **The real-call caller track matches the "digital silence" control exactly** (RMS 0). Our agent's meter on the live FaceTime call read `peak rms 0` for every 2-second window while the caller spoke (calls 20:09:55, 20:21:05). The silence is therefore present **before** our code — it is what Chert's bridge publishes as `facetime-remote-audio`.
3. **Our agent's outbound audio is real speech** (recorded in-room and transcribed verbatim earlier: "Hi there. I'm FixLens…"), and Chert's own media check reported `Video and audio are coming from "agent-…"` on every call. The caller still heard nothing ⇒ the room→FaceTime audio leg on the Mac is also not producing sound.
4. **Clipping survives transport** (peak 32768) and still transcribes, so loud output degrades quality before it breaks intelligibility. We keep agent peaks below ~−2 dBFS today; a limiter at −6 dBFS is recommended.
5. **⚠️ Safety finding: Gemini hallucinates speech on silence.** Given the pure-silence file, Gemini returned *"Do you have to buy a return ticket?"* instead of `[NO SPEECH]`. If a silent or broken caller track ever reaches the model, it may invent user requests. **Mitigation (to build):** gate transcription/tool calls on measured input energy; ignore utterances when caller RMS ≈ 0.

## Conclusion (revised 2026-11-14, 20:40)
Our original conclusion blamed Chert's bridge for the silent caller track. **That was premature.** Chert's own CLI guide documents a
**LiveKit Agents 1.8.0 late-input attachment bug**: when RoomIO is bound to a participant whose audio track is published *after*
the session starts, input audio is lost. The Chert bridge joins with no tracks and publishes `facetime-remote-audio` ~6 s later — exactly that case.

**Fix applied** (same as Chert's Muse worker): start the session unassigned, then `roomIO.setParticipant(bridge)` once its audio track is subscribed.

**Verified in a bridge-like simulation** (caller joins with no tracks, publishes audio 3 s later, speaks Gemini-generated question):
- Before fix: caller audio RMS 0, nothing heard.
- After fix: `HEARD: "Can you fix this laptop? The screen is cracked."` → brain answered in 113 ms → agent replied.

**Still unverified on a real FaceTime call:** caller hears the agent (room → FaceTime leg). Format is ruled out (all formats pass above).

## Additional safety finding from the same test
With **no caller video**, Gemini still reported `object=laptop` and said "I can see the cracked screen" — a fabricated observation.
Fixed with a hard guard in the agent: camera claims are dropped unless a caller video track is actually live; the brain then requests a view.
Verified: `DROPPED visual claims: no caller video` → `request_view`.

## Not covered by this test
- The Mac's FaceTime↔LiveKit audio leg itself (only reachable through a real call).
- An in-room capture of a live call by an independent listener (`scripts/spy.mjs` is ready).
