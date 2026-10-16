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
  // Stats grid (section 1): Version/Total/Favorites/Storage/Playlists/Resume
  // Points + 5 counts. Feature grid (section 2): 6 blurbs.
  const secs = page.querySelectorAll('#cat-about .ssec');
  assert.strictEqual(secs.length, 4, 'About / Inside / System / Data sections');
  assert.strictEqual(secs[0].querySelectorAll('.cnt').length, 11);
  assert.strictEqual(secs[1].querySelectorAll('.cnt').length, 6,
    'the What\'s Inside grid carries 6 feature tiles');
  assert.ok(/Interface Engine/.test(page.textContent), 'the System section lists the engine');
  assert.strictEqual(w.document.querySelectorAll('#main .frow').length, 0,
    'the 2-column .frow must not fight the 3-column .counts grid');
  w.close();
});
