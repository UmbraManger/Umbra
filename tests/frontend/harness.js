'use strict';
/* Shared jsdom loader (P6, Option A): the frontend stays classic script-tag
   globals, so tests inject the real files as <script> text into a jsdom
   window exactly as the browser gets them — no source changes. (Plain
   window.eval would NOT work: every file starts "use strict", so its
   declarations stay scoped to the eval call instead of reaching the shared
   global scope that the browser's script tags provide.) */
const fs = require('node:fs');
const path = require('node:path');
const { JSDOM, VirtualConsole } = require('jsdom');

const ROOT = path.resolve(__dirname, '..', '..');
const JS_DIR = path.join(ROOT, 'frontend', 'js');
// Script tags are stripped from the initial HTML: the harness injects the
// module chain itself, in order (external <script src> tags would not be
// fetched anyway without a resource loader).
const HTML = fs.readFileSync(path.join(ROOT, 'frontend', 'index.html'), 'utf8')
  .replace(/<script[\s\S]*?<\/script>/gi, '');

// index.html's script order — many modules reference globals from earlier ones.
const CHAIN = ['utils.js', 'sync.js', 'state.js', 'views.js', 'lists.js',
  'settings.js', 'ui.js', 'forms.js', 'lookup.js', 'player.js', 'detail.js',
  'share.js', 'events.js', 'boot.js'];

// boot.js fires fetch() during its top-level run. Tests have no server: the
// default stub answers like a dead backend so the r.ok paths take their
// "not connected" branch; pass a router for lock-state tests.
const deadFetch = () => Promise.resolve({ ok: false, status: 0, json: async () => ({}) });

function createWindow(files = CHAIN, { fetch = deadFetch } = {}) {
  const errors = [];
  const vc = new VirtualConsole();
  vc.on('jsdomError', e => errors.push(e));
  vc.sendTo(console, { omitJSDOMErrors: true });
  const dom = new JSDOM(HTML, {
    url: 'http://127.0.0.1/',
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    virtualConsole: vc,
  });
  const w = dom.window;
  w.fetch = fetch;
  // jsdom's pretendToBeVisual rAF pump survives window.close() and then reads
  // the torn-down location (TypeError in an uncaught timer). Route rAF through
  // the window's own timers instead — close() cancels those.
  w.requestAnimationFrame = cb => w.setTimeout(() => cb(Date.now()), 16);
  w.cancelAnimationFrame = id => w.clearTimeout(id);
  for (const f of files) {
    errors.length = 0;
    evalFile(w, f);
    // A script that throws stops mid-file like in a browser — fail with the
    // file name and the message instead of a confusing later ReferenceError.
    if (errors.length) throw new Error(`${f}: ${errors[0].message}`);
  }
  return w;
}

function evalFile(w, file) {
  const s = w.document.createElement('script');
  s.textContent = fs.readFileSync(path.join(JS_DIR, file), 'utf8');
  w.document.head.appendChild(s);   // classic scripts execute synchronously
}

// Objects created inside jsdom have a different realm's prototype, which
// deepStrictEqual rejects — round-trip through JSON to get host objects.
function host(value) {
  return JSON.parse(value);
}

module.exports = { createWindow, evalFile, host, CHAIN, ROOT };
