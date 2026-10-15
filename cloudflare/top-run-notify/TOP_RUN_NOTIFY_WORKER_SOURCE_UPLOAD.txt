/**
 * TOP RUN Web Push STAGE 2 transport verification — NOT production notifications.
 * Existing Worker: top-run-notify; existing D1 binding: DB.
 * Existing D1 schema: subs(id TEXT PRIMARY KEY, raw TEXT NOT NULL, updated_at INTEGER NOT NULL).
 * No Firebase/Auth/Profile/actual unread source is connected.
 * No secret values belong in this file or the public repository.
 */
const ALLOWED_ORIGIN = 'https://nuritakug-cpu.github.io';
const TE = new TextEncoder();

function json(data, status = 200, extra = {}) {
  return new Response(JSON.stringify(data), {
    status, headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff',
      ...extra,
    },
  });
}
function cors(request) {
  return request.headers.get('Origin') === ALLOWED_ORIGIN
    ? {
        'Access-Control-Allow-Origin': ALLOWED_ORIGIN,
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, X-TR-Push-Invite, X-TR-Push-Admin',
        'Vary': 'Origin',
      }
    : {};
}
function concat(...parts) {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let offset = 0;
  for (const part of parts) { out.set(part, offset); offset += part.length; }
  return out;
}
function base64url(bytes) {
  let s = '';
  for (const n of bytes) s += String.fromCharCode(n);
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}
function unbase64url(s, expectedLength) {
  if (typeof s !== 'string' || !/^[A-Za-z0-9_-]+$/.test(s)) throw new Error('Invalid key encoding');
  const value = atob(s.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - s.length % 4) % 4));
  const bytes = Uint8Array.from(value, c => c.charCodeAt(0));
  if (expectedLength !== undefined && bytes.length !== expectedLength) throw new Error('Invalid key length');
  return bytes;
}
function validEndpoint(endpoint) {
  if (typeof endpoint !== 'string' || endpoint.length > 2000) return false;
  try {
    const u = new URL(endpoint);
    if (u.protocol !== 'https:' || u.port || u.username || u.password || u.hash) return false;
    return u.hostname === 'fcm.googleapis.com'
      || u.hostname === 'updates.push.services.mozilla.com'
      || u.hostname === 'web.push.apple.com'
      || u.hostname.endsWith('.push.apple.com');
  } catch { return false; }
}
function subscriptionFrom(data) {
  const sub = data && (data.subscription || data);
  if (!sub || !validEndpoint(sub.endpoint) || !sub.keys || typeof sub.keys !== 'object') {
    throw new Error('Invalid Web Push subscription endpoint');
  }
  const p256dh = unbase64url(sub.keys.p256dh, 65);
  if (p256dh[0] !== 4) throw new Error('Invalid subscription public key');
  unbase64url(sub.keys.auth, 16);
  return { endpoint: sub.endpoint, keys: { p256dh: sub.keys.p256dh, auth: sub.keys.auth } };
}
async function hashId(endpoint) {
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', TE.encode(endpoint))))
    .map(x => x.toString(16).padStart(2, '0')).join('');
}
function authorized(presented, expected) {
  if (typeof presented !== 'string' || !expected || presented.length !== expected.length) return false;
  // Constant amount of comparison work for matching-length strings.
  let diff = 0;
  for (let i = 0; i < expected.length; i++) diff |= presented.charCodeAt(i) ^ expected.charCodeAt(i);
  return diff === 0;
}
async function parseJson(request) {
  const size = request.headers.get('content-length');
  if (size && +size > 8192) throw new Error('Request too large');
  const text = await request.text();
  if (text.length > 8192) throw new Error('Request too large');
  return JSON.parse(text);
}
async function hkdf(salt, key, info, length) {
  const ikm = await crypto.subtle.importKey('raw', key, 'HKDF', false, ['deriveBits']);
  return new Uint8Array(await crypto.subtle.deriveBits({ name: 'HKDF', hash: 'SHA-256', salt, info }, ikm, length * 8));
}
async function encryptWebPush(plaintext, subscription) {
  const uaPub = unbase64url(subscription.keys.p256dh, 65);
  const auth = unbase64url(subscription.keys.auth, 16);
  const ephemeral = await crypto.subtle.generateKey({ name: 'ECDH', namedCurve: 'P-256' }, true, ['deriveBits']);
  const uaKey = await crypto.subtle.importKey('raw', uaPub, { name: 'ECDH', namedCurve: 'P-256' }, false, []);
  const serverPub = new Uint8Array(await crypto.subtle.exportKey('raw', ephemeral.publicKey));
  const shared = new Uint8Array(await crypto.subtle.deriveBits({ name: 'ECDH', public: uaKey }, ephemeral.privateKey, 256));
  const ikm = await hkdf(auth, shared, concat(TE.encode('WebPush: info\0'), uaPub, serverPub), 32);
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const cek = await hkdf(salt, ikm, TE.encode('Content-Encoding: aes128gcm\0'), 16);
  const nonce = await hkdf(salt, ikm, TE.encode('Content-Encoding: nonce\0'), 12);
  const key = await crypto.subtle.importKey('raw', cek, 'AES-GCM', false, ['encrypt']);
  const encrypted = new Uint8Array(await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv: nonce }, key, concat(TE.encode(plaintext), new Uint8Array([2]))
  ));
  const rs = new Uint8Array([0, 0, 16, 0]); // 4096 bytes/record (RFC 8188)
  if (encrypted.length > 4096) throw new Error('Payload exceeds single record');
  return concat(salt, rs, new Uint8Array([65]), serverPub, encrypted);
}
async function vapidJwt(endpoint, env) {
  const pub = unbase64url(env.VAPID_PUBLIC_KEY, 65);
  const priv = unbase64url(env.VAPID_PRIVATE_KEY, 32);
  if (pub[0] !== 4) throw new Error('Invalid VAPID public key');
  if (!/^mailto:[^\s@]+@[^\s@]+$|^https:\/\/[^\s]+$/.test(env.VAPID_SUBJECT || '')) {
    throw new Error('Invalid VAPID subject');
  }
  const key = await crypto.subtle.importKey('jwk', {
    kty: 'EC', crv: 'P-256', x: base64url(pub.slice(1, 33)),
    y: base64url(pub.slice(33, 65)), d: base64url(priv), ext: false,
  }, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign']);
  const jwtHeader = base64url(TE.encode(JSON.stringify({ typ: 'JWT', alg: 'ES256' })));
  const jwtPayload = base64url(TE.encode(JSON.stringify({
    aud: new URL(endpoint).origin, exp: Math.floor(Date.now() / 1000) + 3600,
    sub: env.VAPID_SUBJECT,
  })));
  const unsigned = jwtHeader + '.' + jwtPayload;
  const signature = new Uint8Array(await crypto.subtle.sign(
    { name: 'ECDSA', hash: 'SHA-256' }, key, TE.encode(unsigned)
  ));
  if (signature.length !== 64) throw new Error('Unexpected VAPID signature format');
  return unsigned + '.' + base64url(signature);
}
async function sendWebPush(subscription, env, fetcher = fetch) {
  // Transport-only test; do not fabricate a production unread badge number.
  const payload = JSON.stringify({
    type: 'notice', tag: 'top-run-stage2-test',
    title: 'TOP RUN 通知テスト', body: '通知の接続確認です。',
    url: 'https://nuritakug-cpu.github.io/tabirun-bgm/TOP_RUN_PORTAL.html',
    isTest: true,
  });
  const [encrypted, jwt] = await Promise.all([
    encryptWebPush(payload, subscription), vapidJwt(subscription.endpoint, env),
  ]);
  const response = await fetcher(subscription.endpoint, {
    method: 'POST',
    headers: {
      'Authorization': 'vapid t=' + jwt + ', k=' + env.VAPID_PUBLIC_KEY,
      'Content-Encoding': 'aes128gcm',
      'Content-Type': 'application/octet-stream',
      'TTL': '60',
      'Urgency': 'normal',
    },
    body: encrypted,
    redirect: 'error',
  });
  return response.status;
}
async function handle(request, env) {
  const path = new URL(request.url).pathname;
  const c = cors(request);
  if (request.method === 'OPTIONS') {
    return request.headers.get('Origin') === ALLOWED_ORIGIN
      ? new Response(null, { status: 204, headers: c })
      : json({ ok: false, error: 'Forbidden origin' }, 403);
  }
  if (request.method === 'GET' && path === '/health') {
    return json({ ok: true, service: 'top-run-notify', mode: 'stage2-transport-only' }, 200, c);
  }
  if (request.method === 'GET' && path === '/api/stage2/config') {
    if (!env.VAPID_PUBLIC_KEY) return json({ ok: false, error: 'VAPID not configured' }, 503, c);
    return json({ ok: true, vapidPublicKey: env.VAPID_PUBLIC_KEY, productionReady: false }, 200, c);
  }
  if (request.method === 'POST' && path === '/api/stage2/subscribe') {
    if (!env.DB || !env.TR_PUSH_INVITE_CODE) return json({ ok: false, error: 'Service not configured' }, 503, c);
    let data;
    try { data = await parseJson(request); } catch { return json({ ok: false, error: 'Invalid JSON' }, 400, c); }
    if (!authorized(request.headers.get('X-TR-Push-Invite') || data.pairCode || data.inviteCode,
      env.TR_PUSH_INVITE_CODE)) return json({ ok: false, error: 'Unauthorized' }, 401, c);
    let sub;
    try { sub = subscriptionFrom(data); } catch { return json({ ok: false, error: 'Invalid subscription' }, 400, c); }
    const id = await hashId(sub.endpoint);
    await env.DB.prepare('INSERT INTO subs(id,raw,updated_at) VALUES (?1,?2,?3) ON CONFLICT(id) DO UPDATE SET raw=excluded.raw, updated_at=excluded.updated_at')
      .bind(id, JSON.stringify(sub), Date.now()).run();
    return json({ ok: true, id, stage: 'test-only' }, 200, c);
  }
  if (request.method === 'POST' && path === '/api/stage2/send-test') {
    if (!env.DB || !env.TR_PUSH_ADMIN_TOKEN || !env.VAPID_PUBLIC_KEY || !env.VAPID_PRIVATE_KEY || !env.VAPID_SUBJECT) {
      return json({ ok: false, error: 'Service not configured' }, 503, c);
    }
    let data;
    try { data = await parseJson(request); } catch { return json({ ok: false, error: 'Invalid JSON' }, 400, c); }
    if (!authorized(request.headers.get('X-TR-Push-Admin') || data.adminToken,
      env.TR_PUSH_ADMIN_TOKEN)) return json({ ok: false, error: 'Unauthorized' }, 401, c);
    // One explicit subscription if an id is supplied; otherwise the most recent one.
    let row;
    if (typeof data.id === 'string' && /^[0-9a-f]{64}$/.test(data.id)) {
      row = await env.DB.prepare('SELECT id,raw FROM subs WHERE id=?1').bind(data.id).first();
    } else if (data.id !== undefined && data.id !== null && data.id !== '') {
      return json({ ok: false, error: 'Invalid subscription id' }, 400, c);
    } else {
      row = await env.DB.prepare('SELECT id,raw FROM subs ORDER BY updated_at DESC LIMIT 1').first();
    }
    if (!row) return json({ ok: false, error: 'No subscription found' }, 404, c);
    let sub;
    try { sub = subscriptionFrom(JSON.parse(row.raw)); }
    catch { return json({ ok: false, error: 'Stored subscription invalid' }, 422, c); }
    let pushStatus;
    try { pushStatus = await sendWebPush(sub, env); }
    catch { return json({ ok: false, error: 'Web Push transport failed' }, 502, c); }
    if (pushStatus === 404 || pushStatus === 410) {
      await env.DB.prepare('DELETE FROM subs WHERE id=?1').bind(row.id).run();
    }
    const accepted = pushStatus === 201 || pushStatus === 202;
    return json({ ok: accepted, pushStatus, acceptedByPushService: accepted,
      deliveredToDevice: 'unverified', sentToDevices: 1 }, accepted ? 200 : 502, c);
  }
  return json({ ok: false, error: 'Not found' }, 404, c);
}
export default {
  async fetch(request, env) {
    try { return await handle(request, env); }
    catch { return json({ ok: false, error: 'Internal server error' }, 500, cors(request)); }
  },
};

// Export pure helpers only for offline tests. No additional HTTP routes are exposed.
export { encryptWebPush, vapidJwt, subscriptionFrom, validEndpoint, sendWebPush, hashId };
