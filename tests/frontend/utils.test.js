'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { createWindow, evalFile, host } = require('./harness');

test('pure helpers behave', () => {
  const w = createWindow(['utils.js']);
  assert.strictEqual(w.eval('esc(\'<a>&"\')'), '&lt;a&gt;&amp;&quot;');
  assert.strictEqual(w.eval("esc(\"x'y\")"), 'x&#39;y');
  assert.strictEqual(w.eval('fmtBytes(999)'), '999 B');
  assert.strictEqual(w.eval('fmtBytes(1024)'), '1.0 KB');
  assert.strictEqual(w.eval('fmtBytes(2097152)'), '2.00 MB');
  assert.strictEqual(w.eval('fmtDur(0)'), '-');
  assert.strictEqual(w.eval('fmtDur(45)'), '45m');
  assert.strictEqual(w.eval('fmtDur(125)'), '2h 05m');
  assert.strictEqual(w.eval('fmtTime(65)'), '1:05');
  assert.strictEqual(w.eval('fmtTime(3661)'), '1:01:01');
  assert.strictEqual(w.eval('slug("Hello World!")'), 'hello-world');
  assert.strictEqual(w.eval('titleCase("once upon a time")'), 'Once Upon A Time');
  w.close();
});

test('corrupt obscura:encimgs recovers to {} and keeps a raw copy', () => {
  const w = createWindow([]);           // seed BEFORE utils.js evaluates
  w.localStorage.setItem('obscura:encimgs', '{not json');
  evalFile(w, 'utils.js');              // encStore IIFE runs here — must not throw
  assert.deepStrictEqual(host(w.eval('JSON.stringify(encStore)')), {});
  let corruptKey = null;
  for (let i = 0; i < w.localStorage.length; i++) {
    const k = w.localStorage.key(i);
    if (k.startsWith('obscura:encimgs.corrupt-')) corruptKey = k;
  }
  assert.ok(corruptKey, 'a corrupt-<timestamp> backup key must be written');
  assert.strictEqual(w.localStorage.getItem(corruptKey), '{not json');
  w.close();
});
test('clearImageCache prunes encStore entries no record references anymore', () => {
  const w = createWindow([]);
  // no backend, so clearImageCache skips the /api/images/prune fetch
  w.eval('Sync=null');
  evalFile(w, 'utils.js');
  w.eval(`encStore.left={iv:'00',data:'00',t:'image/jpeg'};encStore.used={iv:'00',data:'00',t:'image/jpeg'};saveEncStore()`);
  w.eval('DB=null');
  w.eval('window.DB={movies:[{id:"m1",posterF:"enc://used"}],scenes:[],performers:[]}');
  w.eval('clearImageCache(false)');
  const store = JSON.parse(w.eval('JSON.stringify(encStore)'));
  assert.ok(!('left' in store), 'unreferenced image must be pruned');
  assert.ok('used' in store, 'referenced image must survive');
  w.close();
});
test('scanProgressWatch drives the settings scan bar from the real count', async () => {
  const w = createWindow(undefined, {
    fetch: (url) => {
      const u = String(url);
      if (u.includes('/api/scan/progress')) {
        return Promise.resolve({ ok: true, json: async () => ({ active: true, done: 5, total: 10 }) });
      }
      if (u.includes('/api/ping')) return Promise.resolve({ ok: true, json: async () => ({ ok: true }) });
      return Promise.resolve({ ok: false, json: async () => ({}) });
    },
  });
  await new Promise(r => setTimeout(r, 60));
  w.eval('renderSettings()');
  const stop = w.eval('scanProgressWatch()');
  const prog = w.document.getElementById('scanprog');
  assert.ok(prog, 'the scan bar markup must be on the settings page');
  assert.strictEqual(prog.style.display, '', 'the bar becomes visible immediately');
  assert.strictEqual(w.document.getElementById('sp-fill').style.width, '0%');
  await new Promise(r => setTimeout(r, 400));          // at least one 250ms poll
  assert.strictEqual(w.document.getElementById('sp-fill').style.width, '50%');
  assert.match(w.document.getElementById('sp-txt').textContent, /5 \/ 10 Files/);
  stop('Scan Complete');
  assert.strictEqual(w.document.getElementById('sp-fill').style.width, '100%');
  assert.strictEqual(w.document.getElementById('sp-txt').textContent, 'Scan Complete');
  w.close();
});

