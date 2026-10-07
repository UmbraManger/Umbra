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
