'use strict';
/* Single-item fetch (lookup modal): a by-title scraper result must be
   title-checked before it reaches the compare step, mirroring the bulk flow. */
const test = require('node:test');
const assert = require('node:assert');
const { createWindow } = require('./harness');

const TITLE = 'Candy For The Boogeyman';

function boot(result) {
  const w = createWindow(undefined, { fetch: () => Promise.resolve({
    ok: true, status: 200, json: async () => result,
  }) });
  w.eval(`Sync.on=true;
   settings.scrapers=[{id:'s1',name:'Elegant Angel',kind:'scene',type:'python',enabled:true}];`);
  return w;
}

const chosen = () => ({ type: 'scraper', s: { id: 's1', name: 'Elegant Angel' } });
const settle = () => new Promise(r => setTimeout(r, 20));

test('single fetch by title refuses a low-match search result instead of applying it', async () => {
  const w = boot({ title: 'Performers Of The Year 2026', studioName: 'EA', covers: [] });
  const apply = () => { throw new Error('apply must not run on a low match'); };
  w.openFetchModal('scene', { title: TITLE, apply });
  w.backendFetch('scene', { title: TITLE, apply }, chosen(), '');
  await settle();
  assert.match(w.document.getElementById('m-title-text').textContent, /Get Info - Source/,
    'bounced back to the source step');
  const toasts = [...w.document.querySelectorAll('#toast-root .toast span')].map(s => s.textContent);
  assert.ok(toasts.some(t => /No Confident Match/i.test(t) && t.includes('Performers Of The Year 2026')),
    'low-match toast names the rejected result');
});

test('single fetch by title still advances when the result matches', async () => {
  const w = boot({ title: TITLE, studioName: 'EA', covers: [] });
  w.openFetchModal('scene', { title: TITLE });
  w.backendFetch('scene', { title: TITLE }, chosen(), '');
  await settle();
  assert.match(w.document.getElementById('m-title-text').textContent, /Compare/,
    'matching result reaches the compare step');
});

test('single fetch with a pasted URL skips the title coverage check', async () => {
  const w = boot({ title: 'Completely Different Page Title', covers: [] });
  w.openFetchModal('scene', { title: TITLE });
  w.backendFetch('scene', { title: TITLE }, chosen(), 'https://www.elegantangel.com/1806212/x.html');
  await settle();
  assert.match(w.document.getElementById('m-title-text').textContent, /Compare/,
    'by-URL lookup applies exactly that page');
});
