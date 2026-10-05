// Smoke test for tagInput().flush() — loads the real function out of ui.js
// and runs it against a minimal DOM stub (no test framework in this repo).
const fs = require('fs');
const path = require('path');

const UI = path.join(path.dirname(__dirname), 'frontend', 'js', 'ui.js');
const src = fs.readFileSync(UI, 'utf8');
const start = src.indexOf('function tagInput(');
const end = src.indexOf('/* ===== CATEGORY PICKER');
if (start < 0 || end < 0) throw new Error('could not locate tagInput in ui.js');
const code = src.slice(start, end);

const esc = s => String(s ?? '');
const titleCase = s => String(s ?? '').replace(/\w\S*/g, w => w[0].toUpperCase() + w.slice(1).toLowerCase());
const icons = () => {};
const $$ = () => [];

function makeBox() {
  const box = { parent: { appendChild() {} }, classList: { add() {} }, handlers: {} };
  box.addEventListener = (ev, fn) => { box.handlers[ev] = fn; };
  Object.defineProperty(box, 'innerHTML', {
    set(v) {
      box._html = v;
      box._input = {
        value: '',
        handlers: {},
        addEventListener(ev, fn) { this.handlers[ev] = fn; }
      };
    },
    get() { return box._html; }
  });
  box.querySelector = sel => (sel === '.tag-in' ? box._input : null);
  return box;
}

const tagInput = new Function('esc', 'titleCase', 'icons', '$$', code + '; return tagInput;')(esc, titleCase, icons, $$);

let failed = 0;
function check(label, got, want) {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) failed++;
  console.log((ok ? 'ok   ' : 'FAIL ') + label + ' -> ' + JSON.stringify(got));
}

// 1. typed-but-uncommitted text is committed by flush()
let box = makeBox();
let t = tagInput(box, [], ['Great Movie'], { single: true });
box._input.value = 'Some Movie';
check('flush commits typed text', t.flush(), true);
check('get() now returns it', t.get(), ['Some Movie']);

// 2. flush on an empty input is a no-op
check('flush with nothing typed', t.flush(), false);
check('get() unchanged', t.get(), ['Some Movie']);

// 3. plain get() never mutates (collect() calls flush first, then get())
box = makeBox();
t = tagInput(box, [], [], { single: true });
box._input.value = 'Ignored By Get';
check('get() does not commit', t.get(), []);
check('flush() then does', (t.flush(), t.get()), ['Ignored By Get']);

// 4. Enter still commits, and title-cases
box = makeBox();
t = tagInput(box, [], [], { single: true });
box._input.value = 'untitled film';
box._input.handlers.keydown({ key: 'Enter', preventDefault() {} });
check('Enter commits title-cased', t.get(), ['Untitled Film']);

process.exit(failed ? 1 : 0);
