'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { createWindow } = require('./harness');

function seed(w) {
  w.eval('Sync.on = true');
  w.eval(`
    DB.movies.push({id:'mv-1',title:'No File Movie'});
    DB.movies.push({id:'mv-2',title:'Has File Movie',filePath:'/x/m2.mp4'});
    DB.scenes.push({id:'sc-1',title:'First Scene',movieId:'mv-1',filePath:'/x/s1.mp4',covers:[]});
    DB.scenes.push({id:'sc-2',title:'Second Scene',movieId:'mv-1',filePath:'/x/s2.mp4',covers:[]});
  `);
}

test('movie without a local file plays its linked scenes as a chain', () => {
  const w = createWindow();
  seed(w);
  w.eval("renderDetail('movie','mv-1')");
  const pos = w.document.getElementById('sc-chain-pos');
  assert.ok(pos, 'chain position label must render');
  assert.match(pos.textContent, /Scene 1 \/ 2/);
  assert.match(pos.textContent, /First Scene/);
  const vid = w.document.querySelector('#pwrap video');
  assert.strictEqual(vid.getAttribute('src'), '/api/media/scene/sc-1');
  const prev = w.document.querySelector('#sc-chain-nav [data-chain="-1"]');
  const next = w.document.querySelector('#sc-chain-nav [data-chain="1"]');
  assert.ok(prev && next, 'chain nav renders');
  assert.ok(prev.hasAttribute('disabled'), 'Prev disabled on the first scene');
  assert.ok(!next.hasAttribute('disabled'), 'Next enabled while scenes remain');
  w.close();
});

test('scene chain auto-advances when a scene ends', () => {
  const w = createWindow();
  seed(w);
  w.eval("renderDetail('movie','mv-1')");
  w.eval("document.querySelector('#pwrap video').dispatchEvent(new Event('ended'))");
  const pos = w.document.getElementById('sc-chain-pos');
  assert.match(pos.textContent, /Scene 2 \/ 2/);
  assert.match(pos.textContent, /Second Scene/);
  const vid = w.document.querySelector('#pwrap video');
  assert.strictEqual(vid.getAttribute('src'), '/api/media/scene/sc-2');
  const next = w.document.querySelector('#sc-chain-nav [data-chain="1"]');
  assert.ok(next.hasAttribute('disabled'), 'Next disabled on the last scene');
  w.close();
});

test('movie with a local file keeps the normal movie player', () => {
  const w = createWindow();
  seed(w);
  w.eval("renderDetail('movie','mv-2')");
  assert.ok(!w.document.getElementById('sc-chain-pos'), 'no chain for a movie with a file');
  const vid = w.document.querySelector('#pwrap video');
  assert.strictEqual(vid.getAttribute('src'), '/api/media/movie/mv-2');
  w.close();
});

test('detail pages expose one Get Info & Images button opening the fetch dialog', () => {
  const w = createWindow();
  seed(w);
  w.eval("renderDetail('scene','sc-1')");
  w.eval("state.view={name:'detail',kind:'scene',id:'sc-1'}");
  const menu = w.document.querySelectorAll('[data-action="fetch-menu"]');
  assert.strictEqual(menu.length, 1, 'exactly one merged button');
  assert.ok(!w.document.querySelector('[data-action="fetch-info"]'),
    'the old standalone buttons are gone from the page');
  menu[0].click();
  assert.ok(w.document.querySelector('[data-action="fetch-info"]'), 'dialog has Update Information');
  assert.ok(w.document.querySelector('[data-action="fetch-posters"]'), 'dialog has Update Covers');
  assert.ok(w.document.querySelector('[data-action="fetch-gallery"]'), 'scene dialog has Fetch Gallery');
  w.eval("closeModal()");
  w.eval("renderDetail('movie','mv-1')");
  w.eval("state.view={name:'detail',kind:'movie',id:'mv-1'}");
  w.document.querySelector('[data-action="fetch-menu"]').click();
  assert.ok(w.document.querySelector('[data-action="fetch-posters"]'));
  assert.ok(!w.document.querySelector('[data-action="fetch-gallery"]'),
    'movie dialog has no Fetch Gallery');
  w.close();
});
