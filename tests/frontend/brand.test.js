'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { createWindow } = require('./harness');

test('the sidebar brand shows the Umbra logo and name', () => {
  const w = createWindow();               // boots the app, which renders the sidebar
  const img = w.document.querySelector('#sidebar .bmark img');
  assert.ok(img, 'the brand slot holds the logo image');
  assert.match(img.getAttribute('src'), /img\/umbra\.png$/);
  assert.strictEqual(w.document.querySelector('#sidebar .bname').textContent, 'Umbra');
  w.close();
});

test('the page declares a favicon', () => {
  const w = createWindow();
  const link = w.document.querySelector('link[rel="icon"]');
  assert.ok(link, 'a favicon link is declared');
  assert.match(link.getAttribute('href'), /img\/favicon\.png$/);
  w.close();
});
