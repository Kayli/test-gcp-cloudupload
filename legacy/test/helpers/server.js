const { spawn } = require('child_process');
const http = require('http');
const path = require('path');

const APP_URL = process.env.APP_URL || 'http://localhost:3000';
const SERVER_PORT = parseInt(new URL(APP_URL).port || '3000', 10);
let serverProc = null;

async function isServerUp(url, timeout = 5000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    try {
      await new Promise((resolve, reject) => {
        const req = http.get(url + '/health', res => resolve(res));
        req.on('error', reject);
        req.setTimeout(500, () => { req.destroy(); reject(new Error('timeout')); });
      });
      return true;
    } catch { /* retry */ }
    await new Promise(r => setTimeout(r, 200));
  }
  return false;
}

async function ensureServer() {
  if (await isServerUp(APP_URL)) {
    console.log('App server already running.');
    return;
  }
  console.log('Starting app server...');
  serverProc = spawn('node', ['src/index.js'], {
    cwd: process.env.SERVER_CWD || path.resolve(__dirname, '..', '..'),
    env: { ...process.env, PORT: String(SERVER_PORT), NODE_ENV: 'test' },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  serverProc.stdout.on('data', d => process.stdout.write('[server] ' + d));
  serverProc.stderr.on('data', d => process.stderr.write('[server] ' + d));
  const up = await isServerUp(APP_URL, 10000);
  if (!up) throw new Error('App server did not start within 10s');
  console.log('App server ready.');
}

function stopServer() {
  if (serverProc) { serverProc.kill(); serverProc = null; }
}

module.exports = { APP_URL, SERVER_PORT, ensureServer, stopServer };
