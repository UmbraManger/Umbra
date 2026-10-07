'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { createWindow } = require('./harness');

const tick = (ms = 20) => new Promise(r => setTimeout(r, ms));

test('the full script chain boots without throwing (data-booted contract)', async () => {
  const w = createWindow();            // index.html DOM + all 14 modules
  assert.strictEqual(w.document.body.dataset.booted, '1');
  await tick(60);                      // drain queued rAF/observer sweeps first
  w.close();
});

test('lock dialog shows when the server reports app_locked', async () => {
  const w = createWindow(undefined, {
    fetch: (url) => Promise.resolve(url.includes('/api/images/status')
      ? { ok: true, json: async () => ({ app_locked: true }) }
      : { ok: false, json: async () => ({}) }),
  });
  await tick();
  const root = w.document.getElementById('lock-root');
  assert.ok(root.classList.contains('show'), 'lock overlay must be visible');
  assert.ok(w.document.getElementById('lock-pass'), 'passphrase input must render');
  await tick(60);
  w.close();
});

test('no dialog when the server reports unlocked', async () => {
  const w = createWindow(undefined, {
    fetch: (url) => Promise.resolve(url.includes('/api/images/status')
      ? { ok: true, json: async () => ({ app_locked: false, pass_set: false, unlocked: true, enc_count: 0 }) }
      : { ok: false, json: async () => ({}) }),
  });
  await tick();
  const root = w.document.getElementById('lock-root');
  assert.ok(!root.classList.contains('show'));
  await tick(60);
  w.close();
});
