// Audio format matrix: publish Gemini speech in many formats through LiveKit, record what a receiver gets.
// Usage: node --env-file=<agent .env.local> matrix.mjs <source.wav> <outdir>
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { AccessToken, RoomServiceClient } from 'livekit-server-sdk';
import { AudioFrame, AudioSource, AudioStream, LocalAudioTrack, Room, RoomEvent, TrackPublishOptions, TrackSource } from '@livekit/rtc-node';

const [src, outDir] = process.argv.slice(2);
mkdirSync(outDir, { recursive: true });
const { LIVEKIT_URL: url, LIVEKIT_API_KEY: key, LIVEKIT_API_SECRET: secret } = process.env;
const rs = new RoomServiceClient(url.replace('wss://', 'https://'), key, secret);

// --- read source wav (16-bit PCM mono) ---
const wav = readFileSync(src);
const srcRate = wav.readUInt32LE(24);
const pcm = new Int16Array(wav.buffer.slice(wav.byteOffset + 44, wav.byteOffset + wav.length));
// trim leading/trailing silence, keep first ~6 s of speech
let a = pcm.findIndex(v => Math.abs(v) > 500), b = pcm.length - 1;
while (b > a && Math.abs(pcm[b]) < 500) b--;
const speech = pcm.slice(Math.max(0, a - 2400), Math.min(b + 2400, a + srcRate * 6));

const resample = (x, from, to) => {
  if (from === to) return Int16Array.from(x);
  const n = Math.floor(x.length * to / from), y = new Int16Array(n);
  for (let i = 0; i < n; i++) { const t = i * from / to, j = Math.floor(t), f = t - j; y[i] = (x[j] ?? 0) * (1 - f) + (x[j + 1] ?? x[j] ?? 0) * f; }
  return y;
};
const rms = d => { let s = 0; for (const v of d) s += v * v; return Math.sqrt(s / Math.max(1, d.length)); };
const writeWav = (path, data, rate, ch) => {
  const body = Buffer.from(data.buffer, data.byteOffset, data.byteLength), h = Buffer.alloc(44);
  h.write('RIFF', 0); h.writeUInt32LE(36 + body.length, 4); h.write('WAVEfmt ', 8); h.writeUInt32LE(16, 16); h.writeUInt16LE(1, 20); h.writeUInt16LE(ch, 22);
  h.writeUInt32LE(rate, 24); h.writeUInt32LE(rate * ch * 2, 28); h.writeUInt16LE(ch * 2, 32); h.writeUInt16LE(16, 34); h.write('data', 36); h.writeUInt32LE(body.length, 40);
  writeFileSync(path, Buffer.concat([h, body]));
};
const token = async (room, identity, pub) => { const t = new AccessToken(key, secret, { identity }); t.addGrant({ room, roomJoin: true, canPublish: pub, canSubscribe: true }); return t.toJwt(); };

const variants = [];
for (const rate of [16000, 24000, 48000]) for (const ch of [1, 2]) for (const red of [false, true]) variants.push({ rate, ch, red, dtx: false });
variants.push({ rate: 48000, ch: 1, red: false, dtx: true });
variants.push({ rate: 24000, ch: 1, red: false, dtx: false, gain: 4.0, label: 'clipping (4x gain)' });
variants.push({ rate: 24000, ch: 1, red: false, dtx: false, gain: 0, label: 'digital silence' });

const results = [];
for (const v of variants) {
  const id = v.label ? v.label.replace(/\W+/g, '_') : `${v.rate / 1000}k_${v.ch === 1 ? 'mono' : 'stereo'}_${v.red ? 'red' : 'opus'}${v.dtx ? '_dtx' : ''}`;
  const room = `fmt-${id}-${Date.now()}`;
  await rs.createRoom({ name: room, emptyTimeout: 30 });
  const rx = new Room(), tx = new Room(), got = []; let mime = '?';
  rx.on(RoomEvent.TrackSubscribed, (track, pub) => {
    if (track.kind !== 1) return; mime = pub.mimeType;
    (async () => { for await (const f of new AudioStream(track, 48000, 1)) got.push(Int16Array.from(f.data)); })();
  });
  await rx.connect(url, await token(room, 'receiver', false), { autoSubscribe: true });
  await tx.connect(url, await token(room, 'sender', true), { autoSubscribe: false });
  const source = new AudioSource(v.rate, v.ch);
  const track = LocalAudioTrack.createAudioTrack('test', source);
  const o = new TrackPublishOptions({ source: TrackSource.SOURCE_MICROPHONE, red: v.red, dtx: v.dtx });
  await tx.localParticipant.publishTrack(track, o);
  await new Promise(s => setTimeout(s, 800));
  let mono = resample(speech, srcRate, v.rate);
  if (v.gain !== undefined) mono = mono.map(x => Math.max(-32768, Math.min(32767, x * v.gain)));
  const spf = v.rate / 100; // 10 ms frames
  const t0 = Date.now();
  for (let i = 0; i + spf <= mono.length; i += spf) {
    const frame = new Int16Array(spf * v.ch);
    for (let k = 0; k < spf; k++) for (let c = 0; c < v.ch; c++) frame[k * v.ch + c] = mono[i + k];
    await source.captureFrame(new AudioFrame(frame, v.rate, v.ch, spf));
  }
  await source.waitForPlayout?.();
  await new Promise(s => setTimeout(s, 1200));
  const sentSec = mono.length / v.rate;
  await tx.disconnect(); await rx.disconnect(); await rs.deleteRoom(room).catch(() => {});
  const all = new Int16Array(got.reduce((n, g) => n + g.length, 0)); let off = 0; for (const g of got) { all.set(g, off); off += g.length; }
  let peak = 0; for (const x of all) peak = Math.max(peak, Math.abs(x));
  const file = `${outDir}/${id}.wav`; writeWav(file, all, 48000, 1);
  const r = { id, rate: v.rate, channels: v.ch, red: v.red, dtx: v.dtx, label: v.label || '', mime, sent_s: +sentSec.toFixed(2), received_s: +(all.length / 48000).toFixed(2), rms: Math.round(rms(all)), peak, wall_ms: Date.now() - t0, file };
  results.push(r); console.log(JSON.stringify(r));
}
writeFileSync(`${outDir}/results.json`, JSON.stringify(results, null, 2));
process.exit(0);
