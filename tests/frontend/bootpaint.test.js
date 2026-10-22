'use strict';
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');
const { createWindow, CHAIN } = require('./harness');

// The pre-paint script is stripped by the shared harness, so evaluate it the
// way a real browser does: read index.html, pull that <script> out, run it.
const HTML = fs.readFileSync(path.join(__dirname, '..', '..', 'frontend', 'index.html'), 'utf8');
const inline = HTML.match(/<script>\s*\/\* Paint the stored theme[\s\S]*?<\/script>/);
assert.ok(inline, 'pre-paint script exists in index.html');
const SRC = inline[0].replace(/^<script>/, '').replace(/<\/script>$/, '');

// colorMix straight from utils.js inside a loaded window — if someone changes
// the background math there, this test fails until the inline copy follows.
const cw = createWindow();
cw.eval('window.__cm=colorMix');
const colorMix = (h, f) => cw.__cm(h, f);

function boot(saved) {
  const dom = new JSDOM('<!doctype html><html><head></head><body></body></html>', {
    url: 'http://127.0.0.1/', runScripts: 'outside-only', pretendToBeVisual: true,
    beforeParse(window) { if (saved) window.localStorage.setItem('obscura:v1', JSON.stringify(saved)); }
  });
  dom.window.eval(SRC);
  return dom.window.document.documentElement;
}

test('saved custom background paints on documentElement before the first frame', () => {
  const r = boot({ theme: 'light', adv: { background: '#201a2b', accent: '#63c5b6' } });
  assert.equal(r.style.getPropertyValue('--bg'), '#201a2b');
  assert.equal(r.style.getPropertyValue('--bg2'), colorMix('#201a2b', -0.06), 'bg2 matches applyAdvanced math');
  assert.equal(r.style.getPropertyValue('--surface'), colorMix('#201a2b', 0.04));
  assert.equal(r.dataset.theme, 'light');
  assert.equal(r.style.getPropertyValue('--accent'), '#63c5b6');
});

test('pre-paint output is identical to what applyAdvanced later sets', () => {
  const w = createWindow();
  w.eval("settings.adv={...settings.adv,background:'#201a2b',accent:'#63c5b6'};applyAdvanced();applyTheme();saveSettings();applyAdvanced();applyTheme();");
  const real = w.document.documentElement;
  const stored = JSON.parse(w.localStorage.getItem('obscura:v1') || 'null') || {};
  const r = boot(stored);
  for (const v of ['--bg', '--bg2', '--surface', '--surface2']) {
    assert.equal(r.style.getPropertyValue(v), real.style.getPropertyValue(v), v);
  }
});

test('no stored settings leaves the stylesheet defaults untouched', () => {
  const r = boot(undefined);
  assert.equal(r.dataset.theme, undefined);
  assert.equal(r.style.getPropertyValue('--bg'), '');
});

test('paintLook is exposed for the head settings fetch (server look)', () => {
  const dom = new JSDOM('<!doctype html><html><head></head><body></body></html>', {
    url: 'http://127.0.0.1/', runScripts: 'outside-only', pretendToBeVisual: true
  });
  dom.window.eval(SRC);
  assert.equal(typeof dom.window.__paintLook, 'function');
  dom.window.__paintLook({ theme: 'light', adv: { background: '#123456', accent: '#fff000' } });
  const r = dom.window.document.documentElement;
  assert.equal(r.dataset.theme, 'light');
  assert.equal(r.style.getPropertyValue('--bg'), '#123456');
});

const settle = () => new Promise(res => setTimeout(res, 30));

test('app UI stays hidden until the lock state resolves, then un-hides', async () => {
  const w = createWindow();
  await settle();
  assert.equal(w.document.body.classList.contains('lock-boot'), false,
    'a dead backend is no lock — the app must appear');
});

test('locked backend: boot hides the app and shows the lock card', async () => {
  const j = async o => ({ ok: true, json: async () => o });
  const w = createWindow(CHAIN, { fetch: async u => {
    if (String(u).includes('/api/images/status')) return j({ app_locked: true });
    return { ok: false, status: 423, json: async () => ({}) };
  } });
  await settle();
  assert.equal(w.document.body.classList.contains('lock-boot'), true,
    'no app UI may flash behind the password dialog');
  assert.ok(w.document.querySelector('#lock-root.show .lockcard'), 'lock card rendered');
});
