'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { createWindow } = require('./harness');

test('buildScraperYAML maps the checked kinds across all three content types', () => {
  const w = createWindow();
  // the field schema carries a set for every assignable kind
  for (const k of ['movie', 'scene', 'performer'])
    assert.ok(w.eval(`STRUCT_FIELDS.${k}.length > 0`), `${k} needs its field set`);
  const rows = [
    { key: 'title', selector: 'meta[property="og:title"]', attr: 'content', transform: 'text' },
    { key: 'year', selector: ' span.year ', attr: 'text', transform: 'int' },
    { key: 'poster_f', selector: '', attr: 'src' }, // cleared → skipped
  ];
  const out = w.eval(`buildScraperYAML("https://x.test/a", ["scene","performer"], ${JSON.stringify(rows)})`);
  assert.ok(out.includes('# kinds: scene, performer'), out);
  assert.ok(out.includes('sample: https://x.test/a'), out);
  assert.ok(out.includes('title: {selector: "meta[property=\\"og:title\\"]", attr: content}'), out);
  assert.ok(out.includes('year: {selector: "span.year", attr: text, transform: int}'), out);
  assert.ok(!out.includes('poster_f'), 'cleared selectors must not leak into the yaml');
});

test('name falls back to the <title> tag (and its selector) when og:/h1 are missing', () => {
  const w = createWindow();
  const rows = w.eval(`prefillStructureRows(["performer"], ${JSON.stringify({
    title: 'Angela - Site Name', titleSel: 'title', titleAttr: 'text'})})`);
  const name = rows.find(r => r.key === 'name');
  assert.strictEqual(name.selector, 'title');
  assert.strictEqual(name.attr, 'text');
  assert.strictEqual(name.hint, 'Angela - Site Name');
});

test('toSearchPattern converts a pasted search link into a {title} pattern', () => {
  const w = createWindow();
  const t = exp => w.eval(`toSearchPattern(${exp})`);
  assert.strictEqual(t("'https://s.test/search?q=Angela+White'"),
                     'https://s.test/search?q={title}');
  assert.strictEqual(t("'https://s.test/?search_query=thing&page=2'"),
                     'https://s.test/?search_query={title}&page=2');
  assert.strictEqual(t("'https://s.test/files?cat=abc'"),    // first valued param wins
                     'https://s.test/files?cat={title}');
  assert.strictEqual(t("'https://s.test/browse'"), '');      // nothing parameterized
  assert.strictEqual(t("'https://s.test/search?q={title}'"), // already fine
                     'https://s.test/search?q={title}');
});

test('prefillStructureRows maps duration + category selectors the page exposes', () => {
  const w = createWindow();
  const rows = w.eval(`prefillStructureRows(["scene"], ${JSON.stringify({
    hasTag: true, hasDuration: true,
    html: '<time datetime="2024-05-01"></time><span class="tag">X</span>PT13M'})})`);
  const dur = rows.find(r => r.key === 'durationMin');
  assert.strictEqual(dur.transform, 'duration');
  assert.ok(dur.selector, 'duration gets a selector when the page carries one');
  const cats = rows.find(r => r.key === 'catNames');
  assert.ok(cats.selector, 'categories get a selector when tag links exist');
  const cast = rows.find(r => r.key === 'performers');
  assert.ok(cast, 'scene rows carry the cast field');
});

test('buildScraperYAML with nothing mapped still yields parseable yaml', () => {
  const w = createWindow();
  const out = w.eval('buildScraperYAML("", [], [])');
  assert.ok(out.includes('fields:'), out);
  assert.ok(out.includes('edit before running'), out);
});

test('buildScraperYAML only emits search template when it carries {title}', () => {
  const w = createWindow();
  const good = w.eval('buildScraperYAML("", ["scene"], [], "https://s.test/search?q={title}")');
  assert.ok(good.includes('search:'), good);
  assert.ok(good.includes('url: "https://s.test/search?q={title}"'), good);
  const bad = w.eval('buildScraperYAML("", ["scene"], [], "https://s.test/search?q=")');
  assert.ok(!bad.includes('search:'), bad);
});

test('prefillStructureRows seeds selectors from og: meta and h1', () => {
  const w = createWindow();
  const det = { title: 'Angela White', h1: 'Angela White', poster: 'http://p/1.jpg', desc: 'Bio' };
  const rows = w.eval(`prefillStructureRows(["performer"], ${JSON.stringify(det)})`);
  const name = rows.find(r => r.key === 'name');
  assert.strictEqual(name.selector, 'h1');           // h1 beats og:title for names
  const photo = rows.find(r => r.key === 'photo');
  assert.strictEqual(photo.selector, 'meta[property="og:image"]');
  assert.strictEqual(photo.attr, 'content');
  // movie rows have no performer-only fields
  const mv = w.eval('prefillStructureRows(["movie"], {})');
  assert.ok(!mv.some(r => r.key === 'name' || r.key === 'photo'), mv.map(r => r.key).join(','));
  assert.ok(mv.some(r => r.key === 'poster_f') && mv.some(r => r.key === 'year'));
});

test('Build Scraper From HTML: footer buttons bind in the real modal flow', async () => {
  const calls = [];
  const w = createWindow(undefined, {
    fetch: (url, init) => {
      const u = String(url), method = (init && init.method) || 'GET';
      calls.push({ url: u, method });
      const ok = (body) => Promise.resolve({ ok: true, json: async () => body });
      if (u.includes('/api/ping')) return ok({ ok: true });
      if (u.includes('/api/library')) return ok({ movies: [], scenes: [], performers: [], studios: [], categories: [] });
      if (u.includes('/api/scrapers/file')) return ok({ id: ' scraped1'.trim(), kinds: ['scene'] });
      if (u.includes('/api/scrapers')) return ok([]);
      return Promise.resolve({ ok: true, json: async () => ({ ok: true }) });
    },
  });
  await new Promise(r => setTimeout(r, 60));          // boot + Sync.init
  w.eval('renderSettings()');
  w.document.querySelector('[data-action="scr-html"]').click();
  let parse = w.document.querySelector('#hs-parse');
  assert.ok(parse, 'the Build Mapping footer button exists');
  const html = '<html><head><meta property="og:title" content="Angela White">' +
    '<meta property="og:image" content="http://p/1.jpg"><meta property="og:description" content="Bio">' +
    '</head><body><h1>Angela White</h1></body></html>';
  w.document.querySelector('#hs-html').value = html;
  w.document.querySelector('#hs-url').value = 'https://brazzers.com/pornstar/4685/x';
  w.document.querySelector('#hs-k-performer').click();   // multi-kind build
  parse.click();                                     // used to throw: footer button outside m-body
  await new Promise(r => setTimeout(r, 30));
  const rows = [...w.document.querySelectorAll('#m-body input[data-mf="sel"]')];
  assert.ok(rows.length >= 4, 'the mapping table renders one row per field');
  const save = w.document.querySelector('#hs-save');
  assert.ok(save, 'the Save As Scraper footer button exists');
  save.click();                                      // used to throw the same way
  await new Promise(r => setTimeout(r, 120));
  const post = calls.find(c => c.method === 'POST' && c.url.includes('/api/scrapers/file'));
  assert.ok(post, 'the built yaml is uploaded');
  assert.match(post.url, /kind=scene/, 'the checked kind rides along as a query param');
  assert.match(post.url, /kind=performer/, 'performer was checked off too');
  assert.ok(calls.some(c => c.url.includes('/api/scrapers/' ) &&
    c.url.includes('/structure')), 'the detected structure is saved with the entry');
  const toast = [...w.document.querySelectorAll('#toast-root .toast')].map(t => t.textContent).join(' ');
  assert.match(toast, /Scraper Built/, 'and the flow completes with a toast');
  w.close();
});
