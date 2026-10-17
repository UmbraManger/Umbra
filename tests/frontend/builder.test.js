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

test('buildScraperYAML with nothing mapped still yields parseable yaml', () => {
  const w = createWindow();
  const out = w.eval('buildScraperYAML("", [], [])');
  assert.ok(out.includes('fields:'), out);
  assert.ok(out.includes('edit before running'), out);
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
