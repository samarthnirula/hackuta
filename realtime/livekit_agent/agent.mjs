import { fileURLToPath } from 'node:url';
import { randomUUID } from 'node:crypto';
import { AutoSubscribe, defineAgent, llm, voice } from '@livekit/agents';
import { realtime } from '@livekit/agents-plugin-google';
import { AudioStream, LocalVideoTrack, TrackPublishOptions, TrackSource, VideoBufferType, VideoFrame, VideoSource } from '@livekit/rtc-node';
import { z } from 'zod';
import { drawFace, FPS, HEIGHT, WIDTH } from './face.mjs';
import { runAgent } from './chert-rooms.mjs';
import { greetOnBridgeReady } from './greet.mjs';

// Person 2's brain: run `python -m uvicorn realtime.decide_server:app --port 8787` in the hackuta repo.
const DECIDE_URL = process.env.DECIDE_URL || 'http://127.0.0.1:8787/decide';
const DECIDE_TIMEOUT_MS = Number(process.env.DECIDE_TIMEOUT_MS || 3000);

const instructions = `You are FixLens, a friendly, lightly funny AI repair assistant on a FaceTime video call.
You can see the caller's camera. You are the EYES and the VOICE; a separate investigation engine is the BRAIN.

Every time the caller says something or shows you something new, call the tool "investigate" FIRST, before answering.
Fill it ONLY with what you can actually see and what they actually said:
- object: the main object you see (e.g. "laptop", "refrigerator", "phone", "microwave"); leave empty if you cannot tell.
- frame_quality: "clear", "degraded" (a bit blurry, dark, glare, far away), or "unusable".
- issues: e.g. ["blur","glare","dark","too far","obstructed"].
- visible_damage: plain description of damage you can SEE, or empty.
- visible_color: color as seen, or empty.
- label_text: the exact characters you can read on a model or serial label. Never guess or correct characters.
- label_unsure: true if any label character is uncertain.
- cannot_move_object: true if the caller says they cannot move or flip it.
Never invent a brand, model, year, size, or part from appearance. Never diagnose on your own.

Then say the tool's "message" to the caller in your own natural, warm voice, keeping its meaning exactly.
Do not add facts, parts, prices, or repair steps that are not in the message.
If the action is "stop_unsafe" or "refer_professional", be calm and serious with no jokes.
Keep every reply to one or two short sentences. Say you are an AI if asked.
If the tool fails, say you are having a hiccup and ask them to describe the problem.`;

const greeting = 'Greet the caller in one short, friendly sentence: you are FixLens, an AI that helps fix things, and ask them to show you what is broken.';

const HICCUP = { action: 'ask_user', message: 'I am having a little hiccup on my end. Can you describe what is going wrong while I catch up?' };

const agent = defineAgent({
  entry: async ctx => {
    await ctx.connect(undefined, AutoSubscribe.SUBSCRIBE_ALL);
    const caller = await ctx.waitForParticipant();
    const sessionId = `call_${randomUUID().slice(0, 8)}`;
    let seq = 0;
    let lastUtterance = '';

    const source = new VideoSource(WIDTH, HEIGHT);
    const track = LocalVideoTrack.createVideoTrack('agent-video', source);
    let tick = 0, speaking = false;
    const frame = () => source.captureFrame(new VideoFrame(drawFace(tick++, speaking), WIDTH, HEIGHT, VideoBufferType.RGBA));
    frame();
    await ctx.room.localParticipant.publishTrack(track, { source: TrackSource.SOURCE_CAMERA });
    const timer = setInterval(frame, 1000 / FPS);

    const investigate = llm.tool({
      description: 'Send what you currently see and what the caller said to the FixLens investigation engine. Returns {action, message}. Always call this before replying.',
      parameters: z.object({
        user_said: z.string().describe("The caller's latest words, as close to verbatim as possible"),
        object: z.string().optional(),
        frame_quality: z.enum(['clear', 'degraded', 'unusable']).optional(),
        issues: z.array(z.string()).optional(),
        visible_damage: z.string().optional(),
        visible_color: z.string().optional(),
        label_text: z.string().optional(),
        label_unsure: z.boolean().optional(),
        cannot_move_object: z.boolean().optional(),
      }),
      execute: async args => {
        const n = ++seq;
        const ref = `frame_${n}`;
        const obs = [];
        // Hard guard: camera claims count only if the caller's video is actually arriving.
        // (Tested: with no video, Gemini still reported obj=laptop and "I can see the cracked screen".)
        const videoLive = [...caller.trackPublications.values()].some(p => p.kind === 2 && p.track && !p.muted);
        const add = (kind, value) => videoLive && value && obs.push({ observation_id: `obs_${n}_${kind}`, kind, value, provenance: 'camera_frame', source_ref: ref });
        add('object_class', args.object);
        add('visible_damage', args.visible_damage);
        add('visible_color', args.visible_color);
        if (!videoLive && (args.object || args.visible_damage || args.label_text)) dbg('DROPPED visual claims: no caller video', JSON.stringify({ object: args.object, damage: args.visible_damage, label: args.label_text }));
        if (!videoLive) { args.label_text = undefined; args.frame_quality = 'unusable'; args.issues = ['no video from caller']; }
        const event = {
          schema_version: '1.0',
          event_id: `${sessionId}_evt_${n}`,
          session_id: sessionId,
          timestamp: new Date().toISOString(),
          user_request: args.user_said || lastUtterance || null,
          observations: obs,
          frame_quality: { status: args.frame_quality || (args.object ? 'clear' : 'unusable'), issues: args.issues || [] },
          visible_text_candidates: args.label_text ? [{
            candidate_id: `txt_${n}`, text: args.label_text, source_ref: `${ref}_label`,
            ambiguity_notes: args.label_unsure ? 'live model reported uncertain characters' : null,
          }] : [],
          consent: { location_use: false, media_storage: false },
          user_constraints: { cannot_move_object: !!args.cannot_move_object },
          media_capabilities: { raw_frames: false, outgoing_video: true, messaging: null },
        };
        const t0 = Date.now();
        try {
          const r = await fetch(DECIDE_URL, {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify(event),
            signal: AbortSignal.timeout(DECIDE_TIMEOUT_MS),
          });
          const plan = await r.json();
          console.log(`[fixlens] ${event.event_id} obj=${args.object ?? '-'} q=${event.frame_quality.status} -> ${plan.action ?? r.status} (${Date.now() - t0}ms)`);
          if (!r.ok) return HICCUP;
          return { action: plan.action, message: plan.message, safety: plan.safety?.classification };
        } catch (e) {
          console.log(`[fixlens] decide failed after ${Date.now() - t0}ms: ${e.name}`);
          return HICCUP;
        }
      },
    });

    const session = new voice.AgentSession({
      llm: new realtime.RealtimeModel({
        model: process.env.GEMINI_LIVE_MODEL || 'gemini-3.8-live',
        apiKey: process.env.GEMINI_API_KEY,
        apiVersion: 'v1beta',
        voice: 'Puck',
        inputAudioTranscription: {},
        outputAudioTranscription: {},
      }),
    });
    const T = Date.now();
    const dbg = (...a) => console.log(`[fixlens +${((Date.now() - T) / 1000).toFixed(1)}s]`, ...a);
    session.on(voice.AgentSessionEventTypes.AgentStateChanged, event => { speaking = event.newState === 'speaking'; dbg('agent', event.oldState, '->', event.newState); });
    session.on(voice.AgentSessionEventTypes.UserStateChanged, ev => dbg('user', ev.oldState, '->', ev.newState));
    session.on(voice.AgentSessionEventTypes.UserInputTranscribed, ev => { if (ev.isFinal) { lastUtterance = ev.transcript; dbg('HEARD:', JSON.stringify(ev.transcript)); } });
    session.on(voice.AgentSessionEventTypes.ConversationItemAdded, ev => { const it = ev.item; dbg('ITEM', it?.role, JSON.stringify(it?.textContent ?? it?.content ?? '').slice(0, 200)); });
    session.on(voice.AgentSessionEventTypes.Error, ev => dbg('ERROR', ev.error?.message || String(ev.error)));
    ctx.addShutdownCallback(async () => {
      clearInterval(timer);
      await session.close();
      await track.close();
      await source.close();
    });
    // Debug meter: is the caller's audio actually carrying sound?
    const meter = track => {
      if (track.kind !== 1) return;
      (async () => {
        let peak = 0, n = 0, last = Date.now();
        for await (const f of new AudioStream(track, 16000, 1)) {
          let s = 0; for (const v of f.data) s += v * v;
          peak = Math.max(peak, Math.sqrt(s / f.data.length)); n++;
          if (Date.now() - last >= 2000) { dbg(`caller audio: ${n} frames, peak rms ${peak.toFixed(0)}`); peak = 0; n = 0; last = Date.now(); }
        }
      })().catch(e => dbg('meter error', e.message));
    };
    ctx.room.on('trackSubscribed', (track, _pub, p) => { if (p.identity === caller.identity) meter(track); });
    for (const pub of caller.trackPublications.values()) if (pub.track) meter(pub.track);
    await session.start({
      room: ctx.room,
      agent: new voice.Agent({ instructions, tools: { investigate } }),
      record: false,
      // No participantIdentity here: LiveKit Agents 1.8.0 has a late-input attachment bug when the
      // caller's audio track is published after the session starts (the Chert bridge does exactly that).
      // Same workaround as Chert's Muse worker: start unassigned, bind once the caller's audio exists.
      inputOptions: {
        audioEnabled: true,
        videoEnabled: true,
        textEnabled: false,
        closeOnDisconnect: true,
        deleteRoomOnClose: false,
      },
      // Plain Opus: the Chert Mac does not play LiveKit's default RED-wrapped audio.
      outputOptions: { audioEnabled: true, transcriptionEnabled: false, audioPublishOptions: new TrackPublishOptions({ source: TrackSource.SOURCE_MICROPHONE, red: false, dtx: false }) },
    });
    const roomIO = session._roomIO;
    let bound = false;
    const bind = why => {
      if (bound || !roomIO) return;
      bound = true;
      roomIO.setParticipant(caller.identity);
      dbg(`bound audio input to ${caller.identity} (${why})`);
    };
    const hasAudio = () => [...caller.trackPublications.values()].some(p => p.kind === 1 && p.track);
    if (hasAudio()) bind('audio already present');
    ctx.room.on('trackSubscribed', (track, _pub, p) => { if (p.identity === caller.identity && track.kind === 1) bind('audio track subscribed'); });
    setTimeout(() => bind('fallback after 8 s'), 8000);
    // Greet once when FaceTime is ready (chert_bridge_ready); the Mac hangs up after 10 s of silence.
    const stopGreeting = greetOnBridgeReady(ctx.room, () => session.generateReply({ instructions: greeting }));
    ctx.addShutdownCallback(async () => stopGreeting());
  },
});

export default agent;

runAgent(agent, { file: fileURLToPath(import.meta.url), agentName: process.env.AGENT_NAME || 'fixlens-agent' });
