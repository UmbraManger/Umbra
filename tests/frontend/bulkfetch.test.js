'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { createWindow } = require('./harness');

const deadFetch = () => Promise.resolve({ ok: false, status: 0, json: async () => ({}) });

function boot() {
  const w = createWindow(undefined, { fetch: deadFetch });
  // two performers + settings live in jsdom's script realm (let/const globals
  // aren't window props), so seed them through window.eval
  w.eval(`DB.performers=[
   {id:'p1',name:'Aaa',picAt:'2026-01-01'},
   {id:'p2',name:'Bbb',picAt:'2026-01-01'}];
  settings.scrapers=[
   {id:'s1',name:'Site One',kind:'performer',type:'python',enabled:true}];`);
  return w;
}

function click(w, sel) {
  const el = w.document.querySelector(sel);
  assert.ok(el, 'missing ' + sel);
  el.click();
}

test('after one bulk run, picking a scraper with everything already fetched still starts (include fallback)', () => {
  const w = boot();
  // reopening as a second pass: include already-focused items deliberately
  w.openBulkFetchMenu('performers', true, 'pic');
  // the source picker shows without the include checkbox (nothing is "skipped")
  assert.ok(w.document.querySelector('.siterow[data-bulkscr]'), 'source picker shown');
  assert.equal(w.document.getElementById('bf-inc'), null, 'include checkbox absent when nothing is skipped');
  click(w, '.siterow[data-bulkscr]');
  // regression: a missing checkbox used to read as "don't include" and bounced
  // between screens forever instead of running
  const title = w.document.getElementById('m-title-text').textContent;
  assert.match(title, /Bulk Get Picture/, 'run started, not bounced back to a menu');
});

test('ticking include then picking a scraper runs in one step (no screen ping-pong)', () => {
  const w = boot();
  w.openBulkFetchMenu('performers', false, 'pic');
  assert.ok(w.document.querySelector('.siterow[data-bulkscr]'), 'source picker shown');
  const cb = w.document.getElementById('bf-inc');
  assert.ok(cb, 'include checkbox present when items were skipped');
  cb.checked = true;
  click(w, '.siterow[data-bulkscr]');
  // the include flip re-renders the source picker (not the choose-op screen),
  // then picking again starts the run — no bounce loop
  assert.match(w.document.getElementById('m-title-text').textContent, /Bulk Picture - Source/,
    'include flip lands back on the source picker');
  click(w, '.siterow[data-bulkscr]');
  assert.match(w.document.getElementById('m-title-text').textContent, /Bulk Get Picture/, 'run started');
});

test('movies ping-pong checked too: include + pick runs without bouncing', () => {
  const w = boot();
  w.eval(`DB.movies=[{id:'m1',title:'Alpha',infoAt:'2026-01-01'}];
  settings.scrapers=[{id:'s1',name:'Site One',kind:'movie',type:'python',enabled:true}];`);
  w.openBulkFetchMenu('movies', false, 'info');
  const cb = w.document.getElementById('bf-inc');
  assert.ok(cb, 'include checkbox present');
  cb.checked = true;
  click(w, '.siterow[data-bulkscr]');
  assert.match(w.document.getElementById('m-title-text').textContent, /Bulk Information - Source/,
    'include flip lands back on the source picker');
  click(w, '.siterow[data-bulkscr]');
  assert.match(w.document.getElementById('m-title-text').textContent, /Bulk Get Information/, 'run started for movies too');
});
