'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { createWindow } = require('./harness');

function boot() {
  const calls = [];
  const w = createWindow(undefined, {
    fetch: (url, init) => {
      const u = String(url), method = (init && init.method) || 'GET';
      calls.push({ url: u, method, body: init && init.body });
      if (u.includes('/api/ping')) return Promise.resolve({ ok: true, json: async () => ({ ok: true }) });
      if (u.includes('/api/scan/import')) {
        const b = JSON.parse(init.body);
        return Promise.resolve({ ok: true, json: async () => ({ record: {
          id: 'mv-' + Math.random().toString(16).slice(2, 8), title: b.title, fav: 0,
          studio_id: '', duration_min: 0, director: '', desc: '', file_path: b.path,
          created_at: '', actor_ids: [], category_ids: [], year: null, scenes: 0,
          poster_f: '', poster_b: '',
        } }) });
      }
      if (method === 'DELETE' || u.includes('/api/scan/undone'))
        return Promise.resolve({ ok: true, json: async () => ({ ok: true }) });
      return Promise.resolve({ ok: false, json: async () => ({}) });
    },
  });
  return { w, calls };
}

const cands = (n, imported) => Array.from({ length: n }, (_, i) => ({
  path: '/lib/f' + i + '.mp4', name: 'f' + i + '.mp4', size: 1000, dir: '/lib',
  imported: !!imported, guess_title: 'F ' + i, guess_kind: 'movie',
  duration_min: 60, posters: [],
}));

test('Import All reports only once every file is imported', async () => {
  const { w, calls } = boot();
  await new Promise(r => setTimeout(r, 60));
  w.eval('openImportModal(' + JSON.stringify(cands(3, false)) + ')');
  w.document.querySelector('[data-action="imp-all"]').click();
  await new Promise(r => setTimeout(r, 150));
  assert.strictEqual(calls.filter(c => c.url.includes('/api/scan/import')).length, 3,
    'every file must be POSTed, not just the first');
  const toast = [...w.document.querySelectorAll('#toast-root .toast')].map(t => t.textContent).join(' ');
  assert.match(toast, /3 Imported/,
    'the count must cover the whole queue — it used to fire after the first import');
  w.close();
});

test('Import All pauses every still-pending card Import button while it runs', async () => {
  // The second import stalls: during that stall cards 2+3 must not be startable
  // (a manual Import mid-queue would create a duplicate record).
  let n = 0, release;
  const gate = new Promise(res => { release = res; });
  const w0 = createWindow(undefined, {
    fetch: (url, init) => {
      const u = String(url);
      if (u.includes('/api/ping')) return Promise.resolve({ ok: true, json: async () => ({ ok: true }) });
      if (u.includes('/api/scan/import')) {
        n++;
        if (n === 1) return gate.then(() => ({ ok: true, json: async () => ({ record: {
          id: 'mv-g', title: 'G', fav: 0, studio_id: '', duration_min: 0, director: '',
          desc: '', file_path: JSON.parse(init.body).path, created_at: '',
          actor_ids: [], category_ids: [], year: null, scenes: 0,
          poster_f: '', poster_b: '',
        } }) }));
        return Promise.resolve({ ok: true, json: async () => ({ record: {
          id: 'mv-' + n, title: 'F' + n, fav: 0, studio_id: '', duration_min: 0,
          director: '', desc: '', file_path: JSON.parse(init.body).path,
          created_at: '', actor_ids: [], category_ids: [], year: null, scenes: 0,
          poster_f: '', poster_b: '',
        } }) });
      }
      return Promise.resolve({ ok: false, json: async () => ({}) });
    },
  });
  const w = w0;
  await new Promise(r => setTimeout(r, 60));
  w.eval('openImportModal(' + JSON.stringify(cands(3, false)) + ')');
  w.document.querySelector('[data-action="imp-all"]').click();
  await new Promise(r => setTimeout(r, 60));
  assert.strictEqual(n, 1, 'the first import is still in flight');
  const pending = [...w.document.querySelectorAll('.impcard:not(.imp-done)')];
  assert.ok(pending.length === 3, 'cards still pending');
  assert.ok(pending.every(c => !c.querySelector('[data-action="imp-do"]') ||
    c.querySelector('[data-action="imp-do"]').disabled),
    'pending Import buttons are disabled mid-queue');
  release();
  await new Promise(r => setTimeout(r, 150));
  assert.strictEqual(n, 3, 'the queue resumes and completes');
  w.close();
});

test('Mark Unimported on a freshly imported card restores it in place', async () => {
  const { w } = boot();
  await new Promise(r => setTimeout(r, 60));
  w.eval('openImportModal(' + JSON.stringify(cands(1, false)) + ')');
  w.document.querySelector('.impcard [data-action="imp-do"]').click();
  await new Promise(r => setTimeout(r, 60));
  assert.ok(w.document.querySelector('.impcard.imp-done'), 'the card flips to done');
  // imported with the wrong kind — undo straight from that card
  w.document.querySelector('.impcard.imp-done [data-action="imp-undone"]').click();
  await new Promise(r => setTimeout(r, 90));
  const card = w.document.querySelector('#m-body .impcard:not(.imp-done)');
  assert.ok(card, 'the card is editable again, in place');
  assert.strictEqual(card.dataset.kind, 'movie', 'and keeps the data needed to flip the kind');
  assert.ok(card.querySelector('[data-action="imp-do"]'), 'with its Import button back');
  w.close();
});

test('Mark Unimported deletes the record and puts the card back editable', async () => {
  const { w, calls } = boot();
  await new Promise(r => setTimeout(r, 60));
  w.eval("DB.movies.push({id:'mv-x',title:'X',filePath:'/lib/f0.mp4',fav:0})");
  w.eval('openImportModal(' + JSON.stringify(cands(1, true)) + ')');
  w.document.querySelector('.srcrow [data-action="imp-undone"]').click();
  await new Promise(r => setTimeout(r, 100));
  assert.ok(calls.some(c => c.method === 'DELETE' && c.url.includes('/api/movies/mv-x')),
    'the imported record must be deleted, or re-importing duplicates it');
  assert.ok(calls.some(c => c.url.includes('/api/scan/undone')), 'the scan state must be cleared');
  assert.strictEqual(w.eval('DB.movies.length'), 0, 'the local copy is dropped too');
  const card = w.document.querySelector('#m-body .impcard[data-path="/lib/f0.mp4"]');
  assert.ok(card, 'the file comes straight back as an editable card — no rescan needed');
  assert.ok(card.querySelector('[data-action="imp-do"]'), 'and it still has its Import button');
  assert.ok(!w.document.querySelector('#m-body .srcrow'), 'and leaves the Already Imported list');
  w.close();
});
