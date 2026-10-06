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
render();
if(settings.imgProt&&settings.imgProt.on)hydrateEncImages(document);
lockApp();
document.body.dataset.booted='1';
async function lockApp(){
  const root=$('#lock-root');
  const r=await fetch('/api/images/status').catch(()=>null);
  if(!r||!r.ok)return;
  const j=await r.json();
  // Server truth, not the client flag: while locked every data fetch 423s, so
  // a stale localStorage copy must not be able to skip this dialog. When the
  // app is NOT locked, hand off to the image-vault prompt (it was deferred
  // behind this screen) so entry never stacks two password prompts at once.
  if(!j.app_locked){Sync.checkImageLock();return;}
  root.classList.add('show');
  const panel=`<div class="lockcard">
   <div class="bmark"><i data-lucide="lock"></i></div>
   <h1>App Locked</h1>
   <div class="mono">Passphrase required to continue</div>
   <input id="lock-pass" class="field" type="password" placeholder="Passphrase" autocomplete="off" style="width:100%;box-sizing:border-box;margin-top:14px;padding:10px 12px;font-size:14px">
   <div class="lockerr" id="lock-err"></div>
   <button id="lock-unlock" class="btn primary" style="margin-top:18px;width:100%">Unlock</button>
  </div>`;
  root.innerHTML=panel;
  $('#lock-pass').addEventListener('keydown',e=>{if(e.key==='Enter')document.getElementById('lock-unlock').click()});
  $('#lock-unlock').addEventListener('click',async()=>{
   const pass=$('#lock-pass').value;
   const r=await fetch('/api/unlock',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({passphrase:pass})});
   const j=await r.json().catch(()=>({}));
   if(r.ok&&!j.locked){root.classList.remove('show');toast('Unlocked - app resumed','lock-open');location.reload();}
   else if(j.locked){$('#lock-err').textContent='Set a passphrase in Settings first';}
   else{$('#lock-err').textContent=j.detail||'Wrong passphrase';}
   $('#lock-pass').value='';$('#lock-pass').focus();$('#lock-root').classList.add('shake');
  });
  $('#lock-pass').focus();
}


Sync.init();
