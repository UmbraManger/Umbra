'use strict';
const test = require('node:test');
const assert = require('node:assert');
const { createWindow } = require('./harness');

function seed(w) {
  w.eval('Sync.on = true');
  w.eval(`
    DB.movies.push({id:'mv-1',title:'No File Movie',posterF:'/x/mv1.jpg'});
    DB.movies.push({id:'mv-2',title:'Has File Movie',filePath:'/x/m2.mp4'});
    DB.scenes.push({id:'sc-1',title:'First Scene',movieId:'mv-1',filePath:'/x/s1.mp4',covers:[],durationMin:20});
    DB.scenes.push({id:'sc-2',title:'Second Scene',movieId:'mv-1',filePath:'/x/s2.mp4',covers:[],durationMin:25});
    DB.scenes.push({id:'sc-x',title:'Lonely Scene',filePath:'/x/sx.mp4',covers:[],durationMin:99});
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

test('last scene stops the chain and playing again restarts from scene 1', () => {
  const w = createWindow();
  seed(w);
  w.eval("renderDetail('movie','mv-1')");
  assert.ok(w.document.querySelector('#pwrap .p-poster-pair'),
    'chain player shows the movie poster even with stale scene positions');
  w.eval("Positions.map['movie:mv-1']=500");
  w.eval("document.querySelector('#pwrap video').dispatchEvent(new Event('ended'))");
  w.eval("document.querySelector('#pwrap video').dispatchEvent(new Event('ended'))");
  const pos = w.document.getElementById('sc-chain-pos');
  assert.match(pos.textContent, /Scene 2 \/ 2/, 'chain must stop on the last scene');
  assert.strictEqual(w.eval("Positions.get('movie','mv-1')"), 0, 'finishing the last scene clears the movie position');
  const vid = w.document.querySelector('#pwrap video');
  assert.strictEqual(vid.getAttribute('src'), '/api/media/scene/sc-2', 'last scene must not restart');
  w.eval("document.querySelector('#pwrap video').dispatchEvent(new Event('play'))");
  const pos2 = w.document.getElementById('sc-chain-pos');
  assert.match(pos2.textContent, /Scene 1 \/ 2/, 'playing again restarts from the first scene');
  w.close();
});

test('chain playback records progress on the movie, not the scenes', () => {
  const w = createWindow();
  seed(w);
  w.eval("renderDetail('movie','mv-1')");
  w.eval("var cv=document.querySelector('#pwrap video');Object.defineProperty(cv,'duration',{value:600,configurable:true});cv.currentTime=100;cv.dispatchEvent(new Event('timeupdate'))");
  assert.strictEqual(w.eval("Positions.get('movie','mv-1')"), 100, 'chain saves the movie position');
  assert.strictEqual(w.eval("Positions.get('scene','sc-1')"), 0, 'chain never touches scene positions');
  w.eval("Object.keys(Positions._t).forEach(k=>clearTimeout(Positions._t[k]))");
  w.close();
});

test('an unfinished chain movie resumes at the right scene and offset', () => {
  const w = createWindow();
  seed(w);
  w.eval("Positions.map['movie:mv-1']=1500");
  w.eval("renderDetail('movie','mv-1')");
  const pos = w.document.getElementById('sc-chain-pos');
  assert.match(pos.textContent, /Scene 2 \/ 2/, 'resumes on the scene containing the position');
  assert.ok(!w.document.querySelector('#pwrap .p-poster-pair'),
    'no poster when resuming a half-watched chain movie');
  assert.strictEqual(w.eval("byId('movie','mv-1').durationMin"), 45, 'movie duration learned from its scenes');
  assert.ok(Math.abs(w.eval("Positions.progress('movie','mv-1')") - 1500 / 2700) < 1e-9,
    'Continue Watching progress uses the scenes total');
  w.eval("Positions.map['movie:mv-1']=2610");
  assert.ok(w.eval("continueHTML('movies')").includes('No File Movie'),
    'chain movie with minutes left stays in Continue Watching');
  w.eval("Positions.map['movie:mv-1']=4");
  assert.ok(w.eval("continueHTML('movies')").includes('No File Movie'),
    'even a short watch shows up in Continue Watching');
  w.eval("var rv=document.querySelector('#pwrap video');Object.defineProperty(rv,'duration',{value:1500,configurable:true});rv.dispatchEvent(new Event('loadedmetadata'))");
  assert.strictEqual(w.eval("document.querySelector('#pwrap video').currentTime"), 300, 'seeks inside the scene to the saved offset');
  w.eval("Sync._queue=[]");
  w.close();
});

test('a scene learns its real duration so Continue Watching can include it', () => {
  const w = createWindow();
  seed(w);
  w.eval("renderDetail('scene','sc-x')");
  w.eval("var sv=document.querySelector('#pwrap video');Object.defineProperty(sv,'duration',{value:1234,configurable:true});sv.dispatchEvent(new Event('loadedmetadata'))");
  assert.strictEqual(w.eval("byId('scene','sc-x').durationMin"), 21, 'wrong durationMin corrected from the file');
  w.eval("Sync._queue=[]");
  w.close();
});

test('watching resumes even when paused in the last seconds', () => {
  const w = createWindow();
  seed(w);
  w.eval("Positions.map['scene:sc-1']=1190");
  w.eval("renderDetail('scene','sc-1')");
  w.eval("var tv=document.querySelector('#pwrap video');Object.defineProperty(tv,'duration',{value:1200,configurable:true});tv.dispatchEvent(new Event('loadedmetadata'))");
  assert.strictEqual(w.eval("document.querySelector('#pwrap video').currentTime"), 1190,
    'a position 10s from the end still resumes');
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
