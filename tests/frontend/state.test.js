'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { createWindow, evalFile, host } = require('./harness');

test('DEF_SETTINGS lock default holds no client-side hash (P3)', () => {
  const w = createWindow(['utils.js', 'state.js']);
  const def = host(w.eval('JSON.stringify(DEF_SETTINGS)'));
  assert.deepStrictEqual(def.lock, { on: false });
  assert.ok(!('hash' in def.lock), 'the client must never hold a lock hash');
  w.close();
});

test('mergeSettings deep-merges lock with server precedence', () => {
  const w = createWindow(['utils.js', 'state.js']);
  const out = host(w.eval(`JSON.stringify(mergeSettings(
    { theme: 'dark', lock: { on: false } },
    { theme: 'light', lock: { on: true, pass_set: true } }))`));
  assert.strictEqual(out.theme, 'light');
  assert.deepStrictEqual(out.lock, { on: true, pass_set: true });
  w.close();
});

test('stored settings blob loads, normalizes and round-trips through saveSettings', () => {
  const w = createWindow([]);
  w.localStorage.setItem('obscura:v1', JSON.stringify({
    theme: 'light', lock: { on: true, pass_set: true }, perPage: { movies: 12 },
  }));
  evalFile(w, 'utils.js');
  evalFile(w, 'sync.js');
  evalFile(w, 'state.js');
  assert.strictEqual(w.eval('settings.theme'), 'light');
  assert.strictEqual(w.eval('settings.lock.on'), true);
  assert.strictEqual(w.eval('settings.lock.pass_set'), true);
  // perPage normalizes missing tabs to the default 24 (state.js load path)
  assert.strictEqual(w.eval('settings.perPage.movies'), 12);
  assert.strictEqual(w.eval('settings.perPage.scenes'), 24);
  w.eval('saveSettings()');
  const stored = JSON.parse(w.localStorage.getItem('obscura:v1'));
  assert.strictEqual(stored.theme, 'light');
  assert.deepStrictEqual(stored.lock, { on: true, pass_set: true });
  w.close();
});
