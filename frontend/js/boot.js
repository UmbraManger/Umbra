"use strict";
/* ===== INIT ===== */
// Persistent delegated pagination listener (survives refreshList DOM replacement)
$('#main').addEventListener('click',e=>{const btn=e.target.closest('[data-page]');if(!btn||state.view.name!=='tab')return;const tab=state.view.tab,Tt=T[tab];if(!Tt)return;Tt.page=+btn.dataset.page;refreshList(tab);$('#main')?.scrollTo({top:0,behavior:'smooth'})});
// Same idea for detail-page catalogues (studio/category movies + scenes): the
// section is re-rendered in place, the rest of the detail page is left alone.
$('#main').addEventListener('click',e=>{const btn=e.target.closest('[data-dpage][data-dkey]');if(!btn||btn.disabled)return;detailGoto(btn.dataset.dkey,+btn.dataset.dpage)});
// Studio/category catalogue toolbar (detail.js): search · filter · view · size · add.
// Kept delegated on #main so it survives the detail page re-rendering itself.
$('#main').addEventListener('click',e=>{detailToolbarClick(e)});
$('#main').addEventListener('input',e=>{detailToolbarInput(e)});
$('#main').addEventListener('change',e=>{detailToolbarInput(e)});
// Bulk checkbox click handler
$('#main').addEventListener('click',e=>{const chk=e.target.closest('[data-bulk-id]');if(!chk||state.view.name!=='tab')return;e.stopPropagation();const id=chk.dataset.bulkId;if(bulkSel.selected.has(id))bulkSel.selected.delete(id);else bulkSel.selected.add(id);updateBulkUI(state.view.tab);});
// Safety net: strip the "· N Series" count from studio-card meta lines
// (views.js studioCard no longer emits it, but any other renderer — or a stale
// cached copy of a js file — can still put it back). Sweeps on every DOM change,
// same pattern as the item-count sweep below, so the cards are clean however
// they were rendered.
// Safety nets (legacy-renderer artifacts): both sweeps share one
// rAF-coalesced observer — they used to run as two full-DOM scans on every
// single DOM mutation batch.
(function(){
 const re=/\s*·\s*\d+\s+Series\b/;
 const isCount=el=>/^([\d]+[\u2013\-][\d]+ Of )?[\d]+ Items$/.test((el.textContent||'').trim());
 const sweep=()=>{
  document.querySelectorAll('.cmeta.mono.dim').forEach(el=>{const t=el.textContent||'';const out=t.replace(re,'');if(out!==t)el.textContent=out});
  document.querySelectorAll('div.mono.dim').forEach(el=>{if(el.className!=='mono dim')return;const st=el.getAttribute('style')||'';if(st.includes('margin:-10px 0 18px')||isCount(el))el.remove()});
 };
 sweep();
 let queued=false;
 new MutationObserver(()=>{if(queued)return;queued=true;requestAnimationFrame(()=>{queued=false;sweep()})}).observe(document.documentElement,{childList:true,subtree:true});
})();
recoverInterruptedRekey();
// App UI stays invisible until the lock state is resolved: booting on a locked
// backend must never flash the library (or the unconnected state) behind the
// password dialog. lockApp() removes the class on the first negative status.
document.body.classList.add('lock-boot');
render();
if(settings.imgProt&&settings.imgProt.on)hydrateEncImages(document);
lockApp();
document.body.dataset.booted='1';
async function lockApp(){
  const root=$('#lock-root');
  const r=await fetch('/api/images/status').catch(()=>null);
  if(!r||!r.ok){document.body.classList.remove('lock-boot');return;}
  const j=await r.json();
  window.__bootLog&&window.__bootLog.snap('lock-status',{locked:!!j.app_locked});
  // Server truth, not the client flag: while locked every data fetch 423s, so
  // a stale localStorage copy must not be able to skip this dialog. When the
  // app is NOT locked, hand off to the image-vault prompt (it was deferred
  // behind this screen) so entry never stacks two password prompts at once.
  if(!j.app_locked){document.body.classList.remove('lock-boot');Sync.checkImageLock();return;}
  root.classList.add('show');
  window.__bootLog&&window.__bootLog.snap('lock-shown');
  const panel=`<div class="lockcard">
   <div class="bmark"><i data-lucide="lock"></i></div>
   <h1>App Locked</h1>
   <div class="mono">Passphrase required to continue</div>
   <input id="lock-pass" class="field" type="password" placeholder="Passphrase" autocomplete="off" style="width:100%;box-sizing:border-box;margin-top:14px;padding:10px 12px;font-size:14px">
   <div class="lockerr" id="lock-err"></div>
   <button id="lock-unlock" class="btn primary" style="margin-top:18px;width:100%">Unlock</button>
  </div>`;
  root.innerHTML=panel;
  icons();   // the password screen mounts before any other render call,
             // so without this the lucide <i> never becomes an SVG
  $('#lock-pass').addEventListener('keydown',e=>{if(e.key==='Enter')document.getElementById('lock-unlock').click()});
  $('#lock-unlock').addEventListener('click',async()=>{
   const pass=$('#lock-pass').value;
   const r=await fetch('/api/unlock',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({passphrase:pass})});
   const j=await r.json().catch(()=>({}));
   const btn=$('#lock-unlock');
   if(r.ok&&!j.locked){
    // One entry gets you in: the same passphrase also opens the image vault
    // when it matches; a 400 just falls back to the normal image prompt.
    btn.disabled=true;btn.textContent='Unlocking...';
    await fetch('/api/images/unlock',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({passphrase:pass})}).catch(()=>{});
    // Connect BEFORE revealing anything: the card stays on screen while the
    // library loads, so the app never shows up empty and then fills itself.
    await Sync.init();
    root.classList.remove('show');
    document.body.classList.remove('lock-boot');
    toast('Unlocked - App Resumed','lock-open');
    icons();
    return;
   }
   else if(j.locked){btn.disabled=false;btn.textContent='Unlock';$('#lock-err').textContent='Set a passphrase in Settings first';}
   else{btn.disabled=false;btn.textContent='Unlock';$('#lock-err').textContent=j.detail||'Wrong passphrase';}
   $('#lock-pass').value='';$('#lock-pass').focus();$('#lock-root').classList.add('shake');
  });
  $('#lock-pass').focus();
}


/* ===== NATIVE TITLE BAR (frameless window) ===== */
// pywebview frameless windows have no OS chrome, so the page draws the bar.
// Dragging is pywebview's: elements matching .pywebview-drag-region move the
// window (easy_drag is off — it would hijack every mousedown in the app).
// Hidden entirely in --browser debug mode, where the browser owns the chrome.
function mountTitleBar(){
 const pv=window.pywebview;
 if(!pv||!pv.platform||document.body.classList.contains('frameless'))return;
 document.body.classList.add('frameless');
 const api=()=>(window.pywebview&&window.pywebview.api)||{};
 const call=n=>{const f=api()[n];if(typeof f==='function')f()};
 $('#tb-min')&&$('#tb-min').addEventListener('click',()=>call('minimize'));
 $('#tb-close')&&$('#tb-close').addEventListener('click',()=>call('close'));
 $('#tb-max')&&$('#tb-max').addEventListener('click',()=>call('toggle_max'));
 const tb=$('#titlebar');
 // double-click anywhere but the buttons = maximize/restore, like a real bar
 tb&&tb.addEventListener('dblclick',e=>{if(e.target.closest('.tb-btns'))return;call('toggle_max')});
 // No border to drag on a frameless window: the bottom-right grip is the resize.
 const grip=$('#tb-resize');
 if(grip)grip.addEventListener('mousedown',e=>{
  e.preventDefault();
  const s={x:e.screenX,y:e.screenY,w:window.innerWidth,h:window.innerHeight};
  const mv=ev=>{const r=api().resize_to;if(typeof r==='function')r(Math.max(960,s.w+ev.screenX-s.x),Math.max(640,s.h+ev.screenY-s.y))};
  const up=()=>{window.removeEventListener('mousemove',mv);window.removeEventListener('mouseup',up)};
  window.addEventListener('mousemove',mv);window.addEventListener('mouseup',up);
 });
}
mountTitleBar();
// Belt and braces: if pywebviewready fired before this script was parsed (it
// does on some engine versions), the listener below never runs and the bar
// would stay hidden for the whole session. A few cheap retries cover that.
[0,300,1200].forEach(t=>setTimeout(mountTitleBar,t));
// pywebview injects its bridge with ExecuteScript AFTER the page has parsed, so
// window.pywebview (and api.*) do not exist yet while our scripts run — mounting
// at parse time always found nothing and the bar never appeared. 'pywebviewready'
// is dispatched by pywebview as soon as the api is usable.
window.addEventListener('pywebviewready',mountTitleBar);

Sync.init();
