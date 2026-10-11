'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { createWindow } = require('./harness');

test('About renders inside the page wrapper with one balanced stat grid', () => {
  const w = createWindow();
  w.eval('renderAbout()');
  const page = w.document.querySelector('#main > .page');
  assert.ok(page, 'About must render inside the page wrapper — it used to escape it');
  assert.ok(page.querySelector('#cat-about'), 'the About card lives inside the wrapper');
  assert.strictEqual(w.document.querySelectorAll('#main .page-head').length, 1,
    'exactly one page head');
  // Version / Total / Favorites / Storage + the 5 category counts, in one grid
  assert.strictEqual(w.document.querySelectorAll('#main .cnt').length, 9);
  assert.strictEqual(w.document.querySelectorAll('#main .frow').length, 0,
    'the 2-column .frow must not fight the 3-column .counts grid');
  w.close();
});
