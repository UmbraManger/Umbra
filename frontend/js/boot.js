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
(function(){const re=/\s*·\s*\d+\s+Series\b/;const sweep=()=>{document.querySelectorAll('.cmeta.mono.dim').forEach(el=>{const t=el.textContent||'';const out=t.replace(re,'');if(out!==t)el.textContent=out})};sweep();new MutationObserver(sweep).observe(document.documentElement,{childList:true,subtree:true})})();
// Safety net: strip the old list item-count label (mono dim counter) wherever it appears
(function(){const isCount=el=>/^([\d]+[\u2013\-][\d]+ Of )?[\d]+ Items$/.test((el.textContent||'').trim());const sweep=()=>{document.querySelectorAll('div.mono.dim').forEach(el=>{if(el.className!=='mono dim')return;const st=el.getAttribute('style')||'';if(st.includes('margin:-10px 0 18px')||isCount(el))el.remove()})};sweep();new MutationObserver(sweep).observe(document.documentElement,{childList:true,subtree:true})})();
render();
if(settings.imgProt&&settings.imgProt.on)hydrateEncImages(document);
if(settings.lock.on)lockApp();
document.body.dataset.booted='1';
Sync.init();
