'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { createWindow } = require('./harness');

function boot() {
  const calls = [];
  const w = createWindow(undefined, {
    fetch: (url, init) => {
      const u = String(url), method = (init && init.method) || 'GET';
      calls.push({ url: u, method });
      if (u.includes('/api/ping')) return Promise.resolve({ ok: true, json: async () => ({ ok: true }) });
      if (u.includes('/open')) return Promise.resolve({ ok: true, json: async () => ({ ok: true }) });
      return Promise.resolve({ ok: false, json: async () => ({}) });
    },
  });
  return { w, calls };
}

const opens = calls => calls.filter(c => c.method === 'POST' && c.url.includes('/open'));

test('the placeholder player honours OS Default Player', async () => {
  const { w, calls } = boot();
  await new Promise(r => setTimeout(r, 70));
  // no filePath -> the canvas placeholder player mounts
  w.eval("DB.movies.push({id:'mv-nf',title:'No File',filePath:'',fav:0})");
  w.eval('settings.player="external";renderDetail("movie","mv-nf")');
  assert.ok(!w.document.querySelector('#pwrap video'), 'the placeholder player mounts');
  w.document.querySelector('#pwrap .p-big').click();
  await new Promise(r => setTimeout(r, 60));
  assert.strictEqual(opens(calls).length, 1,
    'pressing play must hand the file to the OS player, not just animate');
  assert.match(opens(calls)[0].url, /\/api\/media\/movie\/mv-nf\/open/);
  w.close();
});

test('the internal player setting still does not call the OS', async () => {
  const { w, calls } = boot();
  await new Promise(r => setTimeout(r, 70));
  w.eval("DB.movies.push({id:'mv-nf',title:'No File',filePath:'',fav:0})");
  w.eval('settings.player="internal";renderDetail("movie","mv-nf")');
  w.document.querySelector('#pwrap .p-big').click();
  await new Promise(r => setTimeout(r, 60));
  assert.strictEqual(opens(calls).length, 0, 'internal mode must not open the OS player');
  w.close();
});
