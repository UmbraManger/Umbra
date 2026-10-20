'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { createWindow } = require('./harness');

function nativeWindow() {
  const w = createWindow();
  // Stand in for pywebview's bridge, then mount the bar the way boot.js does.
  w.eval(`window.pywebview={platform:'edgechromium',api:{
    minimize(){window.__c.push('min')},
    toggle_max(){window.__c.push('max')},
    close(){window.__c.push('close')},
    resize_to(a,b){window.__c.push('resize:'+a+'x'+b)}
  }};window.__c=[];`);
  w.eval('mountTitleBar()');
  return w;
}

const calls = w => JSON.parse(w.eval('JSON.stringify(window.__c)'));

test('the title bar stays hidden outside the native window', () => {
  const w = createWindow();          // no window.pywebview — like --browser mode
  assert.ok(!w.document.body.classList.contains('frameless'));
  w.close();
});

test('the bar mounts on pywebviewready — the bridge arrives after parse', () => {
  const w = createWindow();          // no bridge yet, exactly like the real app
  assert.ok(!w.document.body.classList.contains('frameless'), 'nothing to see yet');
  w.eval(`window.pywebview={platform:'edgechromium',api:{
    minimize(){window.__c.push('min')},toggle_max(){},close(){},resize_to(){}
  }};window.__c=[];`);
  w.window.dispatchEvent(new w.window.Event('pywebviewready'));
  assert.ok(w.document.body.classList.contains('frameless'),
    'pywebviewready must mount the bar (it injects after the page parses)');
  w.document.getElementById('tb-min').click();
  assert.deepStrictEqual(calls(w), ['min']);
  w.close();
});

test('the native title bar is a drag region with min/max/close', () => {
  const w = nativeWindow();
  assert.ok(w.document.body.classList.contains('frameless'));
  const tb = w.document.getElementById('titlebar');
  assert.ok(tb, 'the bar exists');
  assert.ok(tb.classList.contains('pywebview-drag-region'),
    'pywebview only drags elements carrying this class');
  // app name + version stamp in the bar
  const name = tb.querySelector('.tb-name');
  assert.ok(name && /Umbra/.test(name.textContent), 'the bar names the app');
  assert.ok(/1\.2/.test(name.textContent), 'the bar shows the app version');
  for (const id of ['tb-min', 'tb-max', 'tb-close']) {
    assert.ok(w.document.getElementById(id), id + ' button exists');
  }
  w.document.getElementById('tb-min').click();
  w.document.getElementById('tb-close').click();
  assert.deepStrictEqual(calls(w), ['min', 'close']);
  w.close();
});

test('mounting twice does not double-bind the buttons', () => {
  const w = nativeWindow();
  w.eval('mountTitleBar()');
  w.document.getElementById('tb-min').click();
  assert.deepStrictEqual(calls(w), ['min']);
  w.close();
});

test('double-clicking the bar (not the buttons) toggles maximize', () => {
  const w = nativeWindow();
  const tb = w.document.getElementById('titlebar');
  const dbl = () => tb.dispatchEvent(new w.window.MouseEvent('dblclick', { bubbles: true }));
  dbl();
  dbl();
  assert.deepStrictEqual(calls(w), ['max', 'max']);
  // clicking a button must not also fire the bar's double-click handler
  w.document.getElementById('tb-max').click();
  assert.deepStrictEqual(calls(w), ['max', 'max', 'max']);
  w.close();
});

test('the corner grip resizes to the dragged size, never below the minimum', () => {
  const w = nativeWindow();
  const grip = w.document.getElementById('tb-resize');
  grip.dispatchEvent(new w.window.MouseEvent('mousedown', { bubbles: true, cancelable: true }));
  w.window.dispatchEvent(new w.window.MouseEvent('mousemove', { screenX: 400, screenY: 300 }));
  w.window.dispatchEvent(new w.window.MouseEvent('mouseup'));
  assert.match(calls(w)[0], /^resize:\d+x\d+$/, 'a resize call was made');
  w.close();
});
