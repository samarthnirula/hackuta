// Bridge-like caller: joins with no tracks, publishes mic 3 s later, signals bridge_ready, then speaks a WAV.
import { readFileSync } from 'node:fs';
import { AccessToken, AgentDispatchClient, RoomServiceClient } from 'livekit-server-sdk';
import { AudioFrame, AudioSource, LocalAudioTrack, Room, TrackPublishOptions, TrackSource } from '@livekit/rtc-node';
const { LIVEKIT_URL: url, LIVEKIT_API_KEY: key, LIVEKIT_API_SECRET: secret } = process.env;
const http = url.replace('wss://', 'https://'); const room = `fixlens-talk-${Date.now()}`;
const rs = new RoomServiceClient(http, key, secret);
await rs.createRoom({ name: room, emptyTimeout: 60 });
await new AgentDispatchClient(http, key, secret).createDispatch(room, 'fixlens-agent');
const at = new AccessToken(key, secret, { identity: 'chert-bridge-sim' }); at.addGrant({ room, roomJoin: true, canPublish: true, canSubscribe: true });
const r = new Room(); await r.connect(url, await at.toJwt(), { autoSubscribe: true });
await new Promise(s => setTimeout(s, 3000));                          // late publish, like the real bridge
const src = new AudioSource(24000, 1); const tr = LocalAudioTrack.createAudioTrack('facetime-remote-audio', src);
await r.localParticipant.publishTrack(tr, new TrackPublishOptions({ source: TrackSource.SOURCE_MICROPHONE }));
const sil = () => src.captureFrame(new AudioFrame(new Int16Array(240), 24000, 1, 240));
for (let i = 0; i < 100; i++) await sil();
await rs.updateRoomMetadata(room, JSON.stringify({ chert_call: 'talk', chert_bridge_ready: true, at: new Date().toISOString() }));
for (let i = 0; i < 800; i++) await sil();                             // let greeting play (~8 s)
const w = readFileSync(process.argv[2]); const pcm = new Int16Array(w.buffer.slice(w.byteOffset + 44, w.byteOffset + w.length));
for (let i = 0; i + 240 <= pcm.length; i += 240) await src.captureFrame(new AudioFrame(pcm.slice(i, i + 240), 24000, 1, 240));
for (let i = 0; i < 1000; i++) await sil();                            // wait for reply
await r.disconnect(); await rs.deleteRoom(room).catch(() => {}); console.log('done'); process.exit(0);
