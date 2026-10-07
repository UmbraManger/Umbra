'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { createWindow } = require('./harness');

function bootWithRouter() {
  const calls = [];
  const w = createWindow(undefined, {
    fetch: (url, init) => {
      calls.push({ url: String(url), method: (init && init.method) || 'GET', body: init && init.body });
      if (String(url).includes('/api/ping')) return Promise.resolve({ ok: true, json: async () => ({ ok: true }) });
      return Promise.resolve({ ok: false, json: async () => ({}) });
    },
  });
  return { w, calls };
}

test('Clear Individual Tabs opens confirm and pushes deleteAll with confirm', async () => {
  const { w, calls } = bootWithRouter();
  await new Promise(r => setTimeout(r, 60));   // let Sync.init finish its ping
  assert.strictEqual(w.eval('Sync.on'), true, 'sync must be connected first');
  w.eval('renderSettings()');
  const btn = w.document.querySelector('[data-action="clear-tab"][data-tab="movies"]');
  assert.ok(btn, 'clear-tab button rendered');
  btn.click();
  const ok = w.document.querySelector('#ctab-ok');
  assert.ok(ok, 'confirm modal must open');
  ok.click();
  await new Promise(r => setTimeout(r, 30));
  const push = calls.find(c => c.url.includes('/api/movies/deleteAll'));
  assert.ok(push, 'a POST /api/movies/deleteAll must be enqueued');
  assert.strictEqual(push.method, 'POST');
  assert.deepStrictEqual(JSON.parse(push.body), { confirm: 'DELETE' });
  assert.ok([...w.document.querySelectorAll('#toast-root .toast')]
    .some(t => t.textContent.includes('Cleared')), 'toast must confirm the clear');
  w.close();
});

test('Clear Image Cache button fires its handler', () => {
  const { w } = bootWithRouter();
  w.eval('renderSettings()');
  const cc = w.document.querySelector('[data-action="cache-clear"]');
  assert.ok(cc, 'cache-clear button rendered');
  cc.click();
  assert.ok([...w.document.querySelectorAll('#toast-root .toast')]
    .some(t => t.textContent.includes('Image Cache Cleared')));
  w.close();
});
