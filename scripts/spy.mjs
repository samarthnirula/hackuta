// Hidden listener: joins the real call room (publishes nothing, hidden), measures RMS of every audio track
// directly from the LiveKit server, independent of our agent's code.
import { AccessToken, RoomServiceClient } from 'livekit-server-sdk';
import { AudioStream, Room, RoomEvent } from '@livekit/rtc-node';
const { LIVEKIT_URL: url, LIVEKIT_API_KEY: key, LIVEKIT_API_SECRET: secret } = process.env;
const rs = new RoomServiceClient(url.replace('wss://', 'https://'), key, secret);
const stop = Date.now() + 60 * 60 * 1000;
let target;
console.log('waiting for a real call...');
while (!target && Date.now() < stop) {
  for (const room of await rs.listRooms().catch(() => [])) {
    const ps = await rs.listParticipants(room.name).catch(() => []);
    if (ps.some(p => p.identity.startsWith('chert-bridge'))) { target = room.name; break; }
  }
  if (!target) await new Promise(s => setTimeout(s, 700));
}
if (!target) { console.log('no call'); process.exit(0); }
const at = new AccessToken(key, secret, { identity: 'spy-listener' });
at.addGrant({ room: target, roomJoin: true, canSubscribe: true, canPublish: false, canPublishData: false, hidden: true });
const r = new Room();
const stats = {};
r.on(RoomEvent.TrackSubscribed, (track, pub, p) => {
  if (track.kind !== 1) return;
  const id = `${p.identity.slice(0, 22)}/${pub.name}`;
  stats[id] = { frames: 0, peak: 0, nonzero: 0 };
  console.log('listening to', id, 'mime', pub.mimeType, 'muted', pub.muted);
  (async () => { for await (const f of new AudioStream(track, 16000, 1)) { const s = stats[id]; s.frames++; let sum = 0; for (const v of f.data) { sum += v * v; if (v !== 0) s.nonzero++; } s.peak = Math.max(s.peak, Math.sqrt(sum / f.data.length)); } })();
});
await r.connect(url, await at.toJwt(), { autoSubscribe: true });
console.log('joined', target);
const t = setInterval(() => { for (const [id, s] of Object.entries(stats)) console.log(new Date().toISOString().slice(11, 19), id, `frames=${s.frames} peakRMS=${s.peak.toFixed(0)} nonzeroSamples=${s.nonzero}`); for (const s of Object.values(stats)) { s.peak = 0; s.nonzero = 0; } }, 3000);
r.on(RoomEvent.Disconnected, () => { clearInterval(t); process.exit(0); });
r.on(RoomEvent.ParticipantDisconnected, p => { if (p.identity.startsWith('chert-bridge')) { console.log('call ended'); clearInterval(t); r.disconnect().then(() => process.exit(0)); } });
