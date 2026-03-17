const { OAuth2Client } = require('google-auth-library');

let client;
const allowDev = process.env.ALLOW_DEV_AUTH === '1' || process.env.NODE_ENV === 'test';
if (process.env.GOOGLE_CLIENT_ID && !allowDev) {
  client = new OAuth2Client(process.env.GOOGLE_CLIENT_ID);
}

async function verifyIdToken(idToken) {
  if (!client) return null;
  const ticket = await client.verifyIdToken({ idToken, audience: process.env.GOOGLE_CLIENT_ID });
  const payload = ticket.getPayload();
  return payload;
}

module.exports = async function auth(req, res, next) {
  // If GOOGLE_CLIENT_ID is set and dev auth is NOT allowed, expect Authorization: Bearer <id_token>
  if (process.env.GOOGLE_CLIENT_ID && !allowDev) {
    const auth = req.get('authorization') || '';
    const m = auth.match(/^Bearer (.+)$/);
    if (!m) return res.status(401).json({ error: 'Missing Authorization header' });
    const idToken = m[1];
    try {
      const payload = await verifyIdToken(idToken);
      if (!payload) return res.status(401).json({ error: 'Invalid token' });
      req.user = { id: payload.sub, email: payload.email, hd: payload.hd };
      return next();
    } catch (e) {
      return res.status(401).json({ error: 'Token verification failed' });
    }
  }
  // Dev fallback: allow X-DUMMY-USER header with email when dev auth is enabled
  const dev = req.get('x-dummy-user');
  if (dev && allowDev) {
    req.user = { id: 'dev:' + dev, email: dev };
    return next();
  }

  return res.status(401).json({ error: 'Unauthenticated' });
};
