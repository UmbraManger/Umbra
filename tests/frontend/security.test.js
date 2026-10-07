'use strict';
/* Lint-style guard: every src="…"/href="…" attribute interpolation in the
   detail renderer must pass through esc(). This locks in the fix for the XSS
   class PHASE0.md flagged at detail.js:422 and keeps it from regressing. */
const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const path = require('node:path');
const { ROOT } = require('./harness');

const src = fs.readFileSync(path.join(ROOT, 'frontend', 'js', 'detail.js'), 'utf8');

test('detail.js: no unquoted src/href interpolation', () => {
  const bad = src.match(/(?:src|href)=\$\{/g) || [];
  assert.deepStrictEqual(bad, [], 'attribute interpolation must be quoted and esc()ed');
});

test('detail.js: every src="…" / href="…" interpolation starts with esc(', () => {
  const offenders = [];
  let m;
  const attr = /(?:src|href)="([^"]*)"/g;
  while ((m = attr.exec(src)) !== null) {
    for (const im of m[1].matchAll(/\$\{([^}]*)\}/g)) {
      const expr = im[1].trim();
      if (!expr.startsWith('esc(')) offenders.push(expr);
    }
  }
  assert.deepStrictEqual(offenders, []);
});

test('detail.js: the guard actually inspects interpolations (regex-rot check)', () => {
  const count = [...src.matchAll(/(?:src|href)="([^"]*\$\{[^"]*)"/g)].length;
  assert.ok(count >= 10, `expected >=10 src/href interpolations, found ${count}`);
});
