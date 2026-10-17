"use strict";
/* ===== GLOBAL EVENTS ===== */
document.addEventListener('click',e=>{
 const a=e.target.closest('[data-action]');
 if(!a){
  if(!e.target.closest('.fpop')&&!e.target.closest('[data-action=filter]'))$$('.fpop.open').forEach(p=>p.classList.remove('open'));
  if(!e.target.closest('.tagwrap'))$$('.sugs').forEach(s=>s.remove());
  return;
 }
 const act=a.dataset.action;
 if(act==='nav'){
  if(state.view.tab!==a.dataset.tab){bulkSel.active=false;bulkSel.selected.clear()}
  state.view={name:'tab',tab:a.dataset.tab};state.history=[];render();$('#main').scrollTop=0
 }
 else if(act==='theme-quick'){settings.theme=settings.theme==='dark'?'light':'dark';saveSettings();applyTheme();render()}
 else if(act==='set-theme'){settings.theme=a.dataset.v;saveSettings();applyTheme();renderSettings();icons();toast('Theme: '+(settings.theme==='dark'?'Dark':'Light'),'palette')}
 else if(act==='adv-accent'){
  settings.adv.accent=(settings.adv.accent===a.dataset.v)?'':a.dataset.v;
  saveSettings();applyAdvanced();renderSettings();icons();
  toast(settings.adv.accent?'Accent Color Updated':'Accent Color Reset To Default','palette');
 }
 else if(act==='adv-bg'){
  settings.adv.background=a.dataset.v||'';
  saveSettings();applyAdvanced();renderSettings();icons();
  toast(settings.adv.background?'Background Color Updated':'Background Reset To Theme Default','paintbrush');
 }
 else if(act==='adv-font'){
  settings.adv.font=a.closest('label').querySelector('input').value;
  saveSettings();applyAdvanced();
  toast('Font Updated','type');
 }
 else if(act==='adv-border'){
  settings.adv.border=a.closest('label').querySelector('input').value;
  saveSettings();applyAdvanced();
  toast('Card Border Updated','square');
 }
 else if(act==='adv-reset'){
  settings.adv={accent:'',background:'',font:'',radius:null,border:'1'};
  saveSettings();applyAdvanced();renderSettings();icons();
  toast('Theme Options Reset','rotate-ccw');
 }
 else if(act==='src-add'){
  const kind=a.dataset.kind,inp=$('#src-'+kind);
  const url=inp.value.trim();
  if(!url){inp.classList.add('err');return}
  settings.sources[kind].push({name:parseSourceName(url),url,i:++_seq});
  saveSettings();renderSettings();icons();
  toast(kindLabel(kind)+' Website Added','rss');
 }
 else if(act==='src-del'){
  const kind=a.dataset.kind,i=+a.dataset.i;
  settings.sources[kind]=settings.sources[kind].filter(s=>s.i!==i);
  saveSettings();renderSettings();icons();
 }
 else if(act==='py-toggle'){
  settings.pyScrapers=!settings.pyScrapers;saveSettings();renderSettings();icons();
  toast(settings.pyScrapers?'Python Scrapers Allowed - They Execute As Local Code':'Python Scrapers Blocked','shield-check');
 }
 else if(act==='scr-add'){
  const inp=document.createElement('input');
  inp.type='file';inp.accept='.py,.yml,.yaml';
  inp.addEventListener('change',()=>{
   const f=inp.files[0];if(!f)return;
   const ext=f.name.split('.').pop().toLowerCase();
   if(!['py','yml','yaml'].includes(ext)){toast('Only Python (.py) Or YAML (.yml/.yaml) Files','alert-triangle');return}
   if(!Sync.on){toast('Connect The App Backend To Install External Scrapers','alert-triangle');return}
   openModal([{title:'Assign Scraper',html:()=>`
    <div class="cmsg" style="margin-bottom:12px">Assign <b>${esc(f.name)}</b> To One Or More Content Types. Enabled Scrapers Appear As Sources In The "Get Information" Dialog For Those Kinds.</div>
    <div><label class="flab">Assign To</label><div style="display:flex;flex-direction:column;gap:6px;margin-top:6px">${KIND_LIST.map(k=>`<label class="ckrow"><input type="checkbox" id="scr-k-${k}" ${k==='scene'?'checked':''}>${kindLabel(k)}</label>`).join('')}</div></div>
    ${ext==='py'?`<label class="ckrow" style="margin-top:12px"><input type="checkbox" id="scr-py-ok">I Understand This Python Scraper Executes As Local Code On This Machine</label>`:''}`,
    footer:()=>`<span class="push"></span><button class="btn" data-mclose="1">Cancel</button><button class="btn primary" id="scr-add-save"><i data-lucide="check"></i>Add Scraper</button>`,
    mount(){
     $('#scr-add-save').addEventListener('click',async()=>{
      const kinds=KIND_LIST.filter(k=>$('#scr-k-'+k).checked);
      if(!kinds.length){toast('Assign It To At Least One Content Type','alert-triangle');return}
      const isPy=ext==='py',ack=$('#scr-py-ok');
      if(isPy&&ack&&!ack.checked){toast('Confirm You Understand Python Scrapers Run As Local Code','alert-triangle');return}
      const btn=$('#scr-add-save');btn.disabled=true;
      try{
       const fd=new FormData();fd.append('file',f,f.name);
       const sp=new URLSearchParams();kinds.forEach(k=>sp.append('kind',k));
       if(isPy){
        sp.append('confirm','I UNDERSTAND PYTHON SCRAPERS RUN AS LOCAL CODE');
        if(!settings.pyScrapers){settings.pyScrapers=true;saveSettings()}
       }
       const r=await fetch('/api/scrapers/file?'+sp,{method:'POST',body:fd});
       if(!r.ok){const j=await r.json().catch(()=>({}));throw new Error(j.detail||'Upload Failed')}
       const j=await r.json();
       await refreshScrapers();
       closeModal();
       renderSettings();icons();
       toast('Scraper Added - Assigned To '+((j&&j.kinds)?j.kinds.map(kindLabel).join(' · '):kinds.map(kindLabel).join(' · ')),'file-code');
      }catch(e){btn.disabled=false;toast(String(e.message||e),'alert-triangle')}
     });
    }}],0,480);
  });
  inp.click();
 }
 else if(act==='scr-html'){
  openModal([{title:'Build Scraper From HTML',html:()=>`
   <div class="cmsg" style="margin-bottom:12px">Paste The Page's HTML Below (View Source → Copy), Load A Saved <b>.html</b> File, Or Just Give Its URL. The App Reads The Structure And Builds An Editable Field Mapping That Becomes A Working YAML Scraper.</div>
   <div class="frow" style="max-width:none">
    <div><label class="flab">Page URL (Optional)</label><input class="field" id="hs-url" placeholder="https://site.com/title"></div>
    <div><label class="flab">Search URL Pattern (Optional)</label><input class="field" id="hs-search" placeholder="https://site.com/search?q={title}"><div class="dim" style="font-size:11px;margin-top:2px">Needed for title lookups — must contain <span class="mono">{title}</span>. Without it the scraper only works via "Fetch By URL".</div></div>
   </div>
   <div style="margin-top:8px"><label class="flab">Build Fields For</label><div style="display:flex;flex-direction:column;gap:6px;margin-top:6px">${KIND_LIST.map(k=>`<label class="ckrow"><input type="checkbox" id="hs-k-${k}" ${k==='scene'?'checked':''}>${kindLabel(k)}</label>`).join('')}</div></div>
   <div style="margin-top:10px"><label class="flab">Page HTML</label>
    <button class="btn sm" id="hs-file-btn" style="margin-top:4px"><i data-lucide="file-up"></i>Load HTML File</button>
    <textarea class="field mono" id="hs-html" rows="8" placeholder="<html>...</html>" style="font-size:11px;margin-top:6px"></textarea></div>`,
   footer:()=>`<span class="push"></span><button class="btn" data-mclose="1">Cancel</button><button class="btn primary" id="hs-parse"><i data-lucide="scan-text"></i>Build Mapping</button>`,
   mount(bx,fx){
    const fin=document.createElement('input');fin.type='file';fin.accept='.html,.htm';fin.style.display='none';
    fin.addEventListener('change',()=>{const fh=fin.files[0];if(!fh)return;
     const rd=new FileReader();rd.onload=()=>{$('#hs-html',bx).value=rd.result;toast('HTML Loaded - '+fh.name,'file-up')};rd.readAsText(fh)});
    $('#hs-file-btn',bx).addEventListener('click',()=>fin.click());
    $('#hs-parse',fx||bx).addEventListener('click',()=>{
     const html=$('#hs-html',bx).value;
     if(html.trim().length<30){toast('Paste The Page HTML (At Least A Few Tags)','alert-triangle');return}
     const url=$('#hs-url',bx).value.trim();
     const searchUrl=$('#hs-search',bx).value.trim();
     if(searchUrl&&!searchUrl.includes('{title}')){toast('The Search URL Pattern Needs A {title} Placeholder','alert-triangle');return}
     const kinds=KIND_LIST.filter(k=>$('#hs-k-'+k,bx).checked);
     if(!kinds.length){toast('Build Fields For At Least One Content Type','alert-triangle');return}
     const det=detectStructure(html);
     const rows=prefillStructureRows(kinds,det);
     openModal([{title:'Field Mapping',html:()=>`
      <div class="cmsg" style="margin-bottom:12px">Analysis Of The Provided HTML${det.detected.length?' - Patterns Detected: <b>'+det.detected.map(esc).join(', ')+'</b>':''}. Each Row Becomes A Field Extractor — Fill In A CSS Selector, Or Clear It To Skip That Field.</div>
      ${rows.map((r,i)=>{
       const attrs=['text','content','src','href'];
       return `<div style="margin-bottom:10px"><div class="flab">${esc(r.label)} <span class="dim mono">(${esc(r.key)}${r.transform!=='text'?' · '+r.transform:''})</span></div>
       <div style="display:flex;gap:6px;margin-top:4px"><input class="field mono" style="flex:1" data-mr="${i}" data-mf="sel" value="${esc(r.selector||'')}" placeholder="css selector">
        <select class="field" style="width:110px;flex-shrink:0" data-mr="${i}" data-mf="attr">${attrs.map(v=>`<option ${v===(r.attr||'text')?'selected':''}>${v}</option>`).join('')}</select></div>
       ${r.hint?`<div class="dim" style="font-size:11px;margin-top:2px">sample: ${esc(String(r.hint).slice(0,90))}</div>`:''}</div>`}).join('')}
      <p class="note" style="margin-top:10px">Saved As A YAML Scraper Assigned To: <b>${kinds.map(kindLabel).join(' · ')}</b>. Open Settings › Scanning Any Time To Re-Build Or Tweak Selectors.</p>`,
      footer:()=>`<span class="push"></span><button class="btn" data-mclose="1">Cancel</button><button class="btn primary" id="hs-save"><i data-lucide="check"></i>Save As Scraper</button>`,
      mount(b2,f2){
       $('#hs-save',f2||b2).addEventListener('click',async()=>{
        rows.forEach((r,i)=>{
         ['sel','attr'].forEach(v=>{
          const el=b2.querySelector('[data-mr="'+i+'"][data-mf="'+v+'"]');
          if(el)r[v]=el.value;
         });
        });
        if(!Sync.on){toast('Connect The App Backend To Install External Scrapers','alert-triangle');return}
        const btn=$('#hs-save',f2||b2);btn.disabled=true;
        const name=(url?parseSourceName(url):'html-mapping')+'-scraper.yaml';
        const yamlText=buildScraperYAML(url,kinds,rows,searchUrl);
        try{
         const fd=new FormData();fd.append('file',new Blob([yamlText],{type:'text/yaml'}),name);
         const sp=new URLSearchParams();kinds.forEach(k=>sp.append('kind',k));
         const r=await fetch('/api/scrapers/file?'+sp,{method:'POST',body:fd});
         if(!r.ok){const j=await r.json().catch(()=>({}));throw new Error(j.detail||'Upload Failed')}
         const j=await r.json();
         const mapped=rows.filter(r=>r.selector&&r.selector.trim()).length;
         if(j&&j.id)await fetch(`/api/scrapers/${j.id}/structure`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...det,kind:kinds,fields:mapped})}).then(r=>{if(!r.ok)throw new Error('HTTP '+r.status)}).catch(()=>toast('Meta Structure Could Not Be Saved','alert-triangle'));
         await refreshScrapers();
         closeModal();
         renderSettings();icons();
         toast('Scraper Built - '+mapped+' Field'+(mapped===1?'':'s')+' Mapped For '+kinds.map(kindLabel).join(' · '),'file-code');
        }catch(e){btn.disabled=false;toast(String(e.message||e),'alert-triangle')}
       });
      }}],0,660);
    });
   }}],0,660);
 }
 else if(act==='scr-toggle'){
  const sid=a.dataset.id;
  fetch(`/api/scrapers/${sid}/toggle`,{method:'POST'}).then(async r=>{if(!r.ok)throw new Error('HTTP '+r.status);await refreshScrapers();renderSettings();icons()}).catch(()=>toast('Backend Rejected The Change','alert-triangle'));
 }
else if(act==='scr-del'){
  const sid=a.dataset.id;
  fetch(`/api/scrapers/${sid}`,{method:'DELETE'}).then(async r=>{if(!r.ok)throw new Error('HTTP '+r.status);await refreshScrapers();renderSettings();icons()}).catch(()=>toast('Backend Rejected The Change','alert-triangle'));
}
else if(act==='set-player'){settings.player=a.dataset.v;saveSettings();toast('Player: '+(settings.player==='internal'?'Internal':'OS Default'),'monitor-play')}
 else if(act==='toggle-fav'){
  const kind=a.dataset.kind,id=a.dataset.id;
  const item=byId(kind,id);if(!item)return;
  item.fav=!item.fav;
  Sync.push(kind==='movie'?'movies':'scenes','update',item);
  renderSidebar();
  if(state.view.name==='detail'&&state.view.kind===kind&&state.view.id===id){renderDetail(kind,id);icons()}
  else if(state.view.name==='tab'&&state.view.tab==='profile'){renderTab('profile');icons()}
  else if(state.view.name==='tab')refreshList(state.view.tab);
  toast(item.fav?'Added To Favorites':'Removed From Favorites','heart');
 }
 else if(act==='profile-tab'){state.profileTab=a.dataset.tab;renderProfile();icons()}
 else if(act==='pl-create'){
  openModal([{title:'New Playlist',html:()=>`
   <label class="flab">Playlist Name</label><input class="field" id="pl-name" placeholder="My Playlist" autofocus>`,
   footer:()=>`<span class="push"></span><button class="btn" data-mclose="1">Cancel</button><button class="btn primary" id="pl-ok"><i data-lucide="plus"></i>Create</button>`,
   mount(bl,f){$('#pl-name',bl).focus();$('#pl-ok',f||bl)?.addEventListener('click',()=>{
    const name=$('#pl-name',bl).value.trim();if(!name){toast('Enter A Name','alert-triangle');return}
    if(!settings.playlists)settings.playlists=[];
    settings.playlists.push({id:'pl_'+Date.now(),name,movieIds:[],sceneIds:[]});
    saveSettings();closeModal();renderProfile();icons();toast('Playlist Created','list-music');
   })}}],0,420);
 }
 else if(act==='pl-rename'){
  const plid=a.dataset.plid;const pls=settings.playlists||[];const pl=pls.find(p=>p.id===plid);if(!pl)return;
  openModal([{title:'Rename Playlist',html:()=>`
   <label class="flab">New Name</label><input class="field" id="pl-rn" value="${esc(pl.name)}">`,
   footer:()=>`<span class="push"></span><button class="btn" data-mclose="1">Cancel</button><button class="btn primary" id="pl-rn-ok"><i data-lucide="check"></i>Rename</button>`,
   mount(bl,f){$('#pl-rn',bl).focus();$('#pl-rn-ok',f||bl)?.addEventListener('click',()=>{
    const name=$('#pl-rn',bl).value.trim();if(!name)return;
    pl.name=name;saveSettings();closeModal();renderProfile();icons();toast('Playlist Renamed','check-circle');
   })}}],0,420);
 }
 else if(act==='pl-delete'){
  const plid=a.dataset.plid;const pls=settings.playlists||[];const pl=pls.find(p=>p.id===plid);if(!pl)return;
  openModal([{title:'Delete Playlist',html:()=>`
   <div class="cmsg">Delete <b>"${esc(pl.name)}"</b>? Items Will Not Be Deleted From Your Library.</div>`,
   footer:()=>`<span class="push"></span><button class="btn" data-mclose="1">Cancel</button><button class="btn danger" id="pl-del-ok"><i data-lucide="trash-2"></i>Delete</button>`,
   mount(bl,f){$('#pl-del-ok',f||bl)?.addEventListener('click',()=>{
    settings.playlists=pls.filter(p=>p.id!==plid);saveSettings();closeModal();renderProfile();icons();toast('Playlist Deleted','trash-2');
   })}}],0,420);
 }
 else if(act==='add-to-pl'){
  const kind=a.dataset.kind,id=a.dataset.id;
  const item=byId(kind,id);if(!item)return;
  const pls=settings.playlists||[];
  if(!pls.length){toast('Create A Playlist First — Profile > Playlists','list-music');return}
  const label=item.title||item.name;
  const kindField=kind==='movie'?'movieIds':'sceneIds';
  openModal([{title:'Add To Playlist',html:()=>`
   <div class="cmsg" style="margin-bottom:14px">Add <b>"${esc(label)}"</b> To:</div>
   ${pls.map(pl=>{
    const inPl=(pl[kindField]||[]).includes(id);
    return `<div class="siterow ${inPl?'on':''}" data-plid="${pl.id}"><span class="dot"></span><b>${esc(pl.name)}</b><span class="mono dim">${inPl?'Already Added':'Add'}</span></div>`;
   }).join('')}`,
   footer:()=>`<span class="push"></span><button class="btn" data-mclose="1">Done</button>`,
   mount(bl){
    $$('.siterow',bl).forEach(r=>r.addEventListener('click',()=>{
     const plid=r.dataset.plid;const pl=pls.find(p=>p.id===plid);if(!pl)return;
     if(!pl[kindField])pl[kindField]=[];
     const idx=pl[kindField].indexOf(id);
     if(idx>-1)pl[kindField].splice(idx,1);else pl[kindField].push(id);
     saveSettings();
     r.classList.toggle('on');
     const mono=r.querySelector('.mono');if(mono)mono.textContent=pl[kindField].includes(id)?'Already Added':'Add';
    }))
   }}],0,460);
 }
 else if(act==='cat-limit'){
  settings.catLimit=Math.min(50,Math.max(1,(settings.catLimit||10)+(+a.dataset.d||0)));
  saveSettings();const v=$('#cl-v');v&&(v.textContent=settings.catLimit);
  if(state.view.name==='detail'){renderDetail(state.view.kind,state.view.id);icons()}
 }
 else if(act==='cw-limit'){
  settings.cwLimit=Math.min(20,Math.max(1,(settings.cwLimit||4)+(+a.dataset.d||0)));
  saveSettings();const v=$('#cw-v');v&&(v.textContent=settings.cwLimit);
  if(state.view.name==='tab'){renderTab(state.view.tab);icons()}
 }
 else if(act==='per-page'){
  const t=a.dataset.tab;if(!t)return;
  if(!settings.perPage)settings.perPage={};
  settings.perPage[t]=Math.min(100,Math.max(6,((settings.perPage&&settings.perPage[t])||24)+(+a.dataset.d||0)));
  saveSettings();const v=$('#pp-'+t);v&&(v.textContent=settings.perPage[t]);
  if(state.view.name==='tab'&&state.view.tab===t){T[t].page=1;renderTab(t);icons()}
 }
 else if(act==='cats-expand'||act==='cats-collapse'){
  const v=state.view;if(v.name!=='detail')return;
  catExpand[v.kind+':'+v.id]=act==='cats-expand';
  renderDetail(v.kind,v.id);icons();
 }
 else if(act==='cast-expand'||act==='cast-collapse'){
  const v=state.view;if(v.name!=='detail')return;
  castExpand[v.kind+':'+v.id]=act==='cast-expand';
  renderDetail(v.kind,v.id);icons();
 }
 else if(act==='desc-expand'||act==='desc-collapse'){
  const v=state.view;if(v.name!=='detail')return;
  descExpand[v.kind+':'+v.id]=act==='desc-expand';
  renderDetail(v.kind,v.id);icons();
 }
 else if(act==='info-expand'||act==='info-collapse'){
  const key=a.dataset.infoKey;if(key)infoExpand[key]=act==='info-expand';
  const v=state.view;if(v.name==='detail'){renderDetail(v.kind,v.id);icons();}
 }
 else if(act==='open'){
  if(bulkSel.active){
   const id=a.dataset.id;if(id){
    if(bulkSel.selected.has(id))bulkSel.selected.delete(id);else bulkSel.selected.add(id);
    updateBulkUI(state.view.tab);
   }
   return;
  }
  closeModal();go({name:'detail',kind:a.dataset.kind,id:a.dataset.id})
 }
 else if(act==='back'){goBack()}
 else if(act==='setview'){const tab=state.view.tab,t=T[tab];if(t){t.view=a.dataset.v;renderTab(tab);icons()}}
 else if(act==='bulk-toggle'){
  bulkSel.active=!bulkSel.active;
  if(!bulkSel.active)bulkSel.selected.clear();
  const tab=state.view.tab;renderTab(tab);icons();
 }
 else if(act==='bulk-delete'){
  const tab=state.view.tab;const ids=[...bulkSel.selected];if(!ids.length)return;
  const labels=ids.map(id=>{const item=byTabId(tab,id);return item?(item.title||item.name):''}).filter(Boolean);
  openModal([{title:`Delete ${ids.length} ${tab.charAt(0).toUpperCase()+tab.slice(1)}`,html:()=>`
   <div class="cmsg" style="margin-bottom:12px">Permanently Delete <b>${ids.length}</b> Selected Item${ids.length===1?'':'s'}?${ids.length<=5?'<br>'+labels.map(l=>'&bull; '+esc(l)).join('<br>'):''}<br><span style="color:var(--danger)">This Cannot Be Undone.</span></div>`,
   footer:()=>`<span class="push"></span><button class="btn" data-mclose="1">Cancel</button><button class="btn danger" id="bulk-del-ok"><i data-lucide="trash-2"></i>Delete ${ids.length}</button>`,
   mount(bl,f){
    $('#bulk-del-ok',f)?.addEventListener('click',async()=>{
     let deleted=0,failed=0;
     for(const id of ids){
      const item=byTabId(tab,id);if(!item)continue;
      if(Sync.on){
       try{
        const r=await fetch(`/api/${tab}/${id}`,{method:'DELETE'});
        if(!r.ok)throw new Error('HTTP '+r.status);
       }catch(e){failed++;continue}
      }
      deleted++;
      const arr=DB[tab];const i=arr.indexOf(item);if(i>-1)arr.splice(i,1);
      if(tab==='movies')DB.scenes.forEach(s=>{if(s.movieId===id)s.movieId=null});
      Positions.clear(tab.replace(/s$/,''),id);
     }
     bulkSel.selected.clear();bulkSel.active=false;
     closeModal();
     if(failed)toast(`${deleted} Deleted, ${failed} Failed`,'alert-triangle');
     else toast(`${deleted} Item${deleted===1?'':'s'} Deleted`,'trash-2');
     renderTab(tab);icons();
    });
   }}],0,520);
 }
 else if(act==='bulk-fav'){
  const tab=state.view.tab;const ids=[...bulkSel.selected];
  const target=!ids.every(id=>byTabId(tab,id)?.fav);
  ids.forEach(id=>{const item=byTabId(tab,id);if(item){item.fav=target;Sync.push(tab,'update',item)}});
  bulkSel.selected.clear();bulkSel.active=false;
  toast(`${ids.length} Item${ids.length===1?'':'s'} Updated`,'heart');renderTab(tab);icons();
 }
 else if(act==='bulk-select-all'){
  const tab=state.view.tab;const items=filtered(tab);
  const pp=(settings.perPage&&settings.perPage[tab])||24;
  const t=T[tab];const start=(t.page-1)*pp;
  const pageItems=items.slice(start,start+pp);
  pageItems.forEach(x=>bulkSel.selected.add(x.id));
  updateBulkUI(tab);
 }
 else if(act==='bulk-clear'){
  bulkSel.selected.clear();
  updateBulkUI(state.view.tab);
 }
 else if(act==='filter'){const pop=$('[data-role=fpop]');pop&&pop.classList.toggle('open')}
 else if(act==='filter-clear'){
  resetTabFilters(state.view.tab);
  renderTab(state.view.tab);icons();
 }
 else if(act==='filter-apply'){
  const tab=state.view.tab,pend=T[tab]._pend;
  if(pend){
   if(tab==='performers'){
    T.performers.f.gender=pend.gender;
    T.performers.f.nationalities=new Set(pend.nationalities);
    T.performers.f.hairColors=new Set(pend.hairColors);
    T.performers.f.ethnicities=new Set(pend.ethnicities);
    T.performers.f.boobType=pend.boobType;
    T.performers.f.piercings=pend.piercings;
    T.performers.f.tattoos=pend.tattoos;
    T.performers.f.csMin=pend.ymin||'';
    T.performers.f.csMax=pend.ymax||'';
    T.performers.f.heightMin=pend.heightMin;
    T.performers.f.heightMax=pend.heightMax;
    T.performers.f.sort=pend.sort;
   }else{
    T[tab].f.studios=new Set(pend.studios);
    T[tab].f.cats=new Set(pend.cats);
    T[tab].f.performers=new Set(pend.performers);
    T[tab].f.ymin=pend.ymin;
    T[tab].f.ymax=pend.ymax;
    T[tab].f.sort=pend.sort;
   }
  }
  T[tab].page=1;refreshList(tab);
  const pop=$('[data-role=fpop]');if(pop)pop.classList.remove('open');
  toast('Filters Applied','filter');
 }
 else if(act==='set-thumb'){
  const v=state.view;if(v.name!=='detail'||v.kind!=='scene')return;
  const item=byId('scene',v.id);if(!item||!(item.covers||[]).length)return;
  item.thumb=Math.min(+a.dataset.i||0,item.covers.length-1);
  Sync.push('scenes','update',item);
  renderDetail('scene',item.id);icons();toast('Player Thumbnail Updated','image');
 }
 else if(act==='add'){
  const tab=state.view.tab;
  if(tab==='movies')mediaForm('movie',null);
  else if(tab==='scenes')mediaForm('scene',null);
  else if(tab==='performers')performerForm(null);
  else if(tab==='studios')studioCategoryForm('studio',null);
  else if(tab==='categories')studioCategoryForm('category',null);
 }
 else if(act==='edit'){
  const v=state.view;if(v.name!=='detail')return;
  const item=byId(v.kind,v.id);if(!item)return;
  if(v.kind==='movie')mediaForm('movie',item);
  else if(v.kind==='scene')mediaForm('scene',item);
  else if(v.kind==='performer')performerForm(item);
  else if(v.kind==='studio')studioCategoryForm('studio',item);
  else if(v.kind==='category')studioCategoryForm('category',item);
 }
 else if(act==='share')openShareDialog();
 else if(act==='del'){
  const v=state.view;if(v.name!=='detail')return;
  const item=byId(v.kind,v.id);if(!item)return;
  const label=item.title||item.name;
  const hasFile=Sync.on&&(v.kind==='movie'||v.kind==='scene')&&item.filePath;
  const linked=v.kind==='movie'?DB.scenes.filter(s=>s.movieId===item.id).length:0;
  openModal([{title:'Delete '+kindLabel(v.kind),html:()=>`
   <div class="cmsg" style="margin-bottom:12px">Permanently Delete <b>"${esc(label)}"</b>?${linked?`<br><span style="color:var(--danger)">${linked} Linked Scene${linked===1?'':'s'} Will Be Unlinked (Not Deleted).</span>`:''} This Cannot Be Undone.</div>
   ${hasFile?'<label class="ckrow"><input type="checkbox" id="del-file">Also Delete The Video File From Disk</label>':''}`,
   footer:()=>`<span class="push"></span><button class="btn" data-mclose="1">Cancel</button><button class="btn danger" id="del-ok"><i data-lucide="trash-2"></i>Delete</button>`,
   mount(bl,f){
    $('#del-ok',f).addEventListener('click',async()=>{
     const delFile=$('#del-file')&&$('#del-file').checked;
     if(Sync.on){
      try{
       const r=await fetch(`/api/${kindPlural(v.kind)}/${item.id}${delFile?'?file=1&confirm=DELETE':''}`,{method:'DELETE'});
       if(!r.ok){const j=await r.json().catch(()=>({}));throw new Error(j.detail||('HTTP '+r.status))}
      }catch(err){toast('Delete Failed: '+err.message,'alert-triangle');return}
     }
     if(v.kind==='movie'){
      DB.scenes.forEach(s=>{if(s.movieId===item.id)s.movieId=null});
      const i=DB.movies.indexOf(item);if(i>-1)DB.movies.splice(i,1);
     }else if(v.kind==='scene'){
      const i=DB.scenes.indexOf(item);if(i>-1)DB.scenes.splice(i,1);
     }else{
      const arr=DB[kindPlural(v.kind)];const i=arr.indexOf(item);if(i>-1)arr.splice(i,1);
     }
     Positions.clear(v.kind,item.id);
     closeModal();
     toast(kindLabel(v.kind)+' Deleted','trash-2');
     state.history=[];state.view={name:'tab',tab:kindPlural(v.kind)};render();
    });
   }}],0,520);
 }
 else if(act==='fetch-menu'){
  const v=state.view;if(v.name!=='detail'||(v.kind!=='movie'&&v.kind!=='scene'))return;
  openModal([{title:'Get Information & Images',
   html:()=>`<div class="cmsg" style="margin-bottom:14px">Choose What To Fetch For This ${v.kind==='movie'?'Movie':'Scene'}.</div>
    <div style="display:flex;flex-direction:column;gap:8px">
     <button class="btn" data-action="fetch-info"><i data-lucide="cloud-download"></i>Update Information</button>
     <button class="btn" data-action="fetch-posters"><i data-lucide="image-plus"></i>${v.kind==='movie'?'Update Posters':'Update Covers'}</button>
     ${v.kind==='scene'?`<button class="btn" data-action="fetch-gallery"><i data-lucide="images"></i>Fetch Gallery</button>`:''}
    </div>`,
   footer:()=>`<span class="push"></span><button class="btn" data-mclose="1">Close</button>`,
   mount(){icons()}
  }],0,520);
 }
 else if(act==='fetch-info'||act==='fetch-posters'){
  const v=state.view;if(v.name!=='detail')return;
  const item=byId(v.kind,v.id);if(!item)return;
  openFetchModal(v.kind,{title:item.title,gender:item.gender,current:item,postersOnly:act==='fetch-posters',apply:u=>{
   if(u.title!=null)item.title=titleCase(u.title);
   for(const k of ['year','date','durationMin','scenes','desc','birth','height','weight','careerStart','gender','boobs','twitter','instagram','onlyfans'])if(u[k]!=null)item[k]=u[k];
   for(const k of ['director','ethnicity','nationality','hair','eyes','measurements','piercings','tattoos','aliases'])if(u[k]!=null)item[k]=titleCase(u[k]);
   if(u.catNames)item.categoryIds=u.catNames.map(resolveCategory);
   if(Array.isArray(u.performers))item.actorIds=u.performers.map(resolvePerformer);
   if(u.studioName){const sid=resolveStudio(u.studioName);if(v.kind==='movie')item.studioId=sid;else item.siteId=sid}
   if(v.kind==='scene'&&Array.isArray(u.groups))item.movieId=u.groups.length?resolveMovie(u.groups[0],item.siteId).id:null;
   if(u.posterF!=null){
    // If the existing back cover is identical to the existing front cover, it was
    // almost certainly an auto-duplicate/placeholder from before, not a genuine
    // distinct back cover - clear it rather than let it go stale against the new front.
    if(item.posterB&&item.posterB===item.posterF)item.posterB='';
    item.posterF=u.posterF;
   }
   if(u.posterB!=null)item.posterB=u.posterB;
   if(u.covers){item.covers=u.covers;item.thumb=Math.min(item.thumb||0,Math.max(0,item.covers.length-1))}
   if(u.photo!=null)item.photo=u.photo;
   if(v.kind==='scene'&&Array.isArray(u.gallery))item.gallery=u.gallery;
   Sync.push(kindPlural(v.kind),'update',item);
   toast('Information Updated','cloud-download');render();
  }});
 }
 else if(act==='fetch-gallery'){
  const v=state.view;if(v.name!=='detail'||v.kind!=='scene')return;
  const item=byId('scene',v.id);if(!item)return;
  const scrapers=settings.scrapers.filter(s=>kindHas(s.kind,'scene')&&s.enabled);
  if(!scrapers.length){toast('No Scene Scraper Enabled','alert-triangle');return}
  const glCount=(settings.gallery&&settings.gallery.count)||12;
  let chosen=null;
  const s0={title:'Fetch Gallery',html:()=>`
   <div class="cmsg" style="margin-bottom:14px">Fetch Gallery Images For <b>"${esc(item.title)}"</b></div>
   ${scrapers.map((s,i)=>`<div class="siterow scraper" data-scr="${i}"><span class="dot"></span><i data-lucide="${s.type==='python'?'file-code':'file-json'}"></i><b>${esc(s.name)}</b><span class="mono">${s.type==='python'?'Python':'YAML'}</span></div>`).join('')}
   <div style="margin-top:14px"><label class="flab">Direct URL (Optional)</label><input class="field" id="gl-url" placeholder="https://..." value="${esc(item.sourceUrl||'')}"></div>`,
   footer:()=>`<span class="push"></span><button class="btn primary" id="gl-fetch-go" disabled>Fetch<i data-lucide="images"></i></button>`,
   mount(b,f){
    $$('.siterow[data-scr]',b).forEach(r=>r.addEventListener('click',()=>{$$('.siterow',b).forEach(x=>x.classList.remove('on'));r.classList.add('on');chosen=scrapers[+r.dataset.scr];$('#gl-fetch-go',f).disabled=false}));
    $('#gl-fetch-go',f)?.addEventListener('click',async()=>{
     const url=$('#gl-url',b)?.value?.trim();
     if(!chosen)return;
     $('#gl-fetch-go',f).disabled=true;$('#gl-fetch-go',f).innerHTML='<i data-lucide="loader"></i>Fetching...';icons(f);
     let body;
     try{
      body={kind:'scene',mode:'scraper',scraper_id:chosen.id,title:item.title,url:url||'',gallery_count:glCount};
      const r=await fetch('/api/scrape',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      if(!r.ok)throw new Error('HTTP '+r.status);
      const raw=await r.json();
      const imgs=Array.isArray(raw?.gallery)?raw.gallery:[];
      if(!modalSteps||modalSteps[0]!==s0)return;
      if(!imgs.length){toast('No Gallery Found','alert-triangle');$('#gl-fetch-go',f).disabled=false;$('#gl-fetch-go',f).innerHTML='Fetch<i data-lucide="images"></i>';icons(f);return}
      // Step 2: show preview
      modalSteps=[modalSteps[0],{title:`Gallery Preview (${imgs.length} Images)`,html:()=>`
       <div class="gallery-grid" style="margin-top:8px">${imgs.map((u,i)=>`<div class="gallery-item" data-idx="${i}"><img src="${esc(u)}" alt="Image ${i+1}" loading="lazy"></div>`).join('')}</div>
       <div class="mono dim" style="font-size:11px;margin-top:10px">${imgs.length} images found. Select which to keep.</div>`,
       footer:()=>`<button class="btn" data-mclose="1"><i data-lucide="x"></i>Cancel</button><span class="push"></span><button class="btn primary" id="gl-apply"><i data-lucide="check"></i>Apply Gallery</button>`,
       mount(b2,f2){
        icons(b2);
        $('#gl-apply',f2)?.addEventListener('click',()=>{
         item.gallery=imgs;
         Sync.push('scenes','update',item);
         closeModal();toast(imgs.length+' Gallery Images Applied','images');renderDetail('scene',item.id);icons();
        });
       }}];
      modalIdx=1;renderModal();
     }catch(e){
      console.error('[fetch-gallery] failed:',e);
      toast('Gallery Fetch Failed: '+e.message,'alert-triangle');
      $('#gl-fetch-go',f).disabled=false;$('#gl-fetch-go',f).innerHTML='Fetch<i data-lucide="images"></i>';icons(f);
     }
    });
   }};
  openModal([s0],0,520);
 }
 else if(act==='ai-save'){
  settings.ai.provider=$('#ai-provider').value;
  settings.ai.endpoint=$('#ai-endpoint').value.trim();
  settings.ai.model=$('#ai-model').value.trim();
  settings.ai.key=$('#ai-key').value.trim();
  saveSettings();
  if(Sync.on&&settings.ai.key){
   fetch('/api/ai/key',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({key:settings.ai.key})})
    .then(r=>{
     if(!r.ok)throw new Error('HTTP '+r.status);
     settings.ai.key='';saveSettings();
     toast('AI Settings Saved - Key Stored In The OS Credential Store','bot');
    })
    .catch(()=>toast('AI Key Kept Locally - The Backend Did Not Accept It, So It Was NOT Moved To The OS Credential Store','alert-triangle'));
   return;
  }
  toast('AI Settings Saved - The Key Is Kept For This Session Only','bot');
 }
 else if(act==='ai-test'){
  if(Sync.on){
   a.disabled=true;
   fetch('/api/scrape',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:'movie',mode:'ai',title:'Connection Test'})})
    .then(r=>{a.disabled=false;if(r.ok)toast('Connection OK - Backend Reached The Model','plug-zap');else return r.json().then(j=>{throw new Error(j.detail||'Failed')})})
    .catch(err=>{a.disabled=false;toast('AI Test Failed: '+err.message,'alert-triangle')});
   return;
  }
  if(!settings.ai.on){toast('Enable AI First','alert-triangle');return}
  if(!settings.ai.key.trim()&&settings.ai.provider!=='custom'){toast('API Key Required For This Provider','alert-triangle');return}
  a.disabled=true;
  // Real test against the configured endpoint (the old demo path always
  // reported success without contacting anything).
  (async()=>{
   const ctrl=new AbortController();const to=setTimeout(()=>ctrl.abort(),8000);
   const ai=settings.ai,prov=ai.provider,ep=(ai.endpoint||AI_PROVIDERS[prov]?.[1]||'').replace(/\/+$/,'');
   try{
    let url=ep+'/models',init={signal:ctrl.signal};
    if(prov==='gemini')url=ep+'/models?key='+encodeURIComponent(ai.key);
    else if(prov==='anthropic')init.headers=ai.key?{'x-api-key':ai.key,'anthropic-version':'2023-06-01'}:{};
    else init.headers=ai.key?{Authorization:'Bearer '+ai.key}:{};
    const r=await fetch(url,init);
    if(!r.ok){const j=await r.json().catch(()=>({}));throw new Error((j.error&&j.error.message)||j.detail||('HTTP '+r.status))}
    toast('Connection OK - '+ep+' Responding','plug-zap');
   }catch(err){
    toast('AI Test Failed: '+(err.name==='AbortError'?'Timed Out':err.message)+' - If The Provider Blocks Browser Requests, Use Backend Mode','alert-triangle');
   }finally{clearTimeout(to);a.disabled=false}
  })();
 }
 else if(act==='cache-clear'){
  clearImageCache(true);
  renderSettings();icons();
  toast('Image Cache Cleared','eraser');
 }
 else if(act==='cache-purge'){
  const n=Object.keys(encStore).length;
  if(!n)return;
  openModal([{title:'Delete All Protected Images',html:()=>`<div class="cmsg">This Permanently Deletes ${n} Encrypted Image Cop${n===1?'y':'ies'} From Storage. This Cannot Be Undone. Continue?</div>`,
   footer:()=>`<span class="push"></span><button class="btn" data-mclose="1">Cancel</button><button class="btn danger" id="cp-purge"><i data-lucide="trash-2"></i>Delete All</button>`,
   mount(){$('#cp-purge').addEventListener('click',()=>{
    Object.keys(encStore).forEach(k=>delete encStore[k]);
    saveEncStore();
    clearImageCache(false);
    closeModal();renderSettings();icons();
    toast('Protected Images Deleted','trash-2');
   })}}],0,520);
 }
 else if(act==='bk-export'){
  const doExport=async(pass)=>{
   a.disabled=true;
   try{
    const r=await fetch('/api/backup/export'+(pass?'?passphrase='+encodeURIComponent(pass):''));
    if(!r.ok)throw new Error('HTTP '+r.status);
    const blob=await r.blob();
    const m=/filename="?([^";]+)"?/.exec(r.headers.get('Content-Disposition')||'');
    const u=URL.createObjectURL(blob);
    const link=document.createElement('a');
    link.href=u;link.download=m?m[1]:'Umbra-Backup.zip';
    document.body.appendChild(link);link.click();link.remove();
    setTimeout(()=>URL.revokeObjectURL(u),4000);
    toast(pass?'Encrypted Backup Exported':'Backup Exported','download');
   }catch(err){toast('Backup Failed: '+err.message,'alert-triangle')}
   a.disabled=false;
  };
  openModal([{title:'Export Backup',html:()=>`
   <div class="cmsg" style="margin-bottom:12px">Save A Complete Backup - Library Database, Protected Images, Scrapers And Settings. The AI API Key Is Never Included.</div>
   <label class="flab">Passphrase (Optional) - Encrypts The Backup File</label>
   <input class="field" id="bk-exp-pass" type="password" placeholder="Leave Empty For An Unencrypted .zip" autocomplete="new-password">`,
   footer:()=>`<span class="push"></span><button class="btn" data-mclose="1">Cancel</button><button class="btn primary" id="bk-exp-go"><i data-lucide="download"></i>Export</button>`,
   mount(b,f){$('#bk-exp-go',f)?.addEventListener('click',()=>{
    const pass=$('#bk-exp-pass',b)?.value||'';
    closeModal();doExport(pass);
   })}}],0,520);
 }
 else if(act==='bk-restore'){
  const askPass=(prompt)=>new Promise(res=>{
   let settled=false;
   const done=v=>{if(settled)return;settled=true;res(v);closeModal()};
   openModal([{title:'Backup Passphrase',html:()=>`
    <div class="cmsg" style="margin-bottom:12px">${prompt}</div>
    <input class="field" id="bk-pass-in" type="password" placeholder="Passphrase" autocomplete="off">`,
    footer:()=>`<span class="push"></span><button class="btn" data-mclose="1">Cancel</button><button class="btn primary" id="bk-pass-ok"><i data-lucide="unlock"></i>Continue</button>`,
    mount(b,f){
     const inp=$('#bk-pass-in',b);setTimeout(()=>inp&&inp.focus(),50);
     $('#bk-pass-ok',f)?.addEventListener('click',()=>done(inp?.value||''));
     inp?.addEventListener('keydown',e=>{if(e.key==='Enter')done(inp.value||'')});
    },
    onClose(){done(null)}}],0,460);
  });
  const inp=document.createElement('input');
  inp.type='file';inp.accept='.zip,.obk';
  inp.addEventListener('change',async()=>{
   const f=inp.files[0];if(!f)return;
   // Encrypted container (OBSCBK1 magic)? Then a passphrase is required.
   let pass='';
   try{
    const head=new Uint8Array(await f.slice(0,7).arrayBuffer());
    if(String.fromCharCode(...head)==='OBSCBK1'){
     pass=await askPass('This Backup Is Passphrase-Protected. Enter The Passphrase It Was Exported With.');
     if(pass===null)return;
    }
   }catch(e){}
   const doRestore=async(pw)=>{
    const btn=document.getElementById('bk-rst');
    const busy=(on)=>{if(!btn)return;btn.disabled=on;if(on){toast('Restoring...','wait');btn.querySelector('i').style.display='none'}};
    try{
    const fd=new FormData();fd.append('file',f);
    const r=await fetch('/api/backup/restore?confirm=RESTORE',{method:'POST',body:fd});
    if(!r.ok){const j=await r.json().catch(()=>({}));throw new Error(j.detail||('HTTP '+r.status))}
    closeModal();toast('Backup Restored - Reloading...','history');
    setTimeout(()=>location.reload(),900);
    }finally{
    busy(false);
    }
   };
   openModal([{title:'Restore Backup',html:()=>`
    <div class="cmsg" style="margin-bottom:12px">Restoring <b>"${esc(f.name)}"</b> Replaces The Current Library, Images, Scrapers And Settings With The Backup Contents. This Cannot Be Undone. Continue?</div>`,
    footer:()=>`<span class="push"></span><button class="btn" data-mclose="1">Cancel</button><button class="btn danger" id="bk-rst"><i data-lucide="upload"></i>Restore</button>`,
    mount(){$('#bk-rst').addEventListener('click',async()=>{
     try{
      await doRestore(pass);
     }catch(err){
      const msg=String(err.message||err);
      if(/passphrase/i.test(msg)){
       // wrong passphrase: retry in-place instead of restarting the flow
       pass=await askPass('Wrong Passphrase - Try Again.');
       if(pass===null)return;
       try{await doRestore(pass)}catch(e2){toast('Restore Failed: '+e2.message,'alert-triangle')}
      }else toast('Restore Failed: '+msg,'alert-triangle');
     }
    })}}],0,520);
  });
  inp.click();
 }
 else if(act==='pos-clear'){
  openModal([{title:'Clear Watch Positions',html:()=>`<div class="cmsg">This Removes All Resume Points. Movies And Scenes Will Start From The Beginning Next Time. Continue?</div>`,
   footer:()=>`<span class="push"></span><button class="btn" data-mclose="1">Cancel</button><button class="btn danger" id="pos-ok"><i data-lucide="history"></i>Clear Positions</button>`,
   mount(){$('#pos-ok').addEventListener('click',()=>{Positions.clearAll();closeModal();toast('Watch Positions Cleared','history')})}}],0,480);
 }
 else if(act==='clear-tab'){
  const tab=a.dataset.tab;
  const labels={movies:'Movies',scenes:'Scenes',performers:'Performers',studios:'Studios',categories:'Categories'};
  const label=labels[tab]||tab;
  const count=tab==='movies'?DB.movies.length:tab==='scenes'?DB.scenes.length:tab==='performers'?DB.performers.length:tab==='studios'?DB.studios.length:DB.categories.length;
  openModal([{title:`Clear ${label}`,html:()=>`<div class="cmsg">This Permanently Deletes All ${count} ${label}. Related References (Like Cast Links) Will Remain But Point To Missing Entries. This Cannot Be Undone.</div>`,
   footer:()=>`<span class="push"></span><button class="btn" data-mclose="1">Cancel</button><button class="btn danger" id="ctab-ok"><i data-lucide="trash-2"></i>Clear ${label}</button>`,
   mount(){$('#ctab-ok').addEventListener('click',()=>{
    const arr=tab==='movies'?DB.movies:tab==='scenes'?DB.scenes:tab==='performers'?DB.performers:tab==='studios'?DB.studios:DB.categories;
    arr.length=0;
    Sync.push(tab,'deleteAll',{confirm:'DELETE'});
    closeModal();render();toast(`${label} Cleared`,'trash-2');
   })}}],0,480);
 }
 else if(act==='lock-set'){
  (async()=>{
   const cur=$('#lk-cur'),p1=$('#lk-p1'),p2=$('#lk-p2');
   if(settings.lock.pass_set){
    if(!cur||!cur.value){cur&&cur.classList.add('err');toast('Enter Current Password','alert-triangle');return}
   }
   const np=p1.value;
   if(np.length<4){p1.classList.add('err');toast('Password Must Be At Least 4 Characters','alert-triangle');return}
   if(np!==p2.value){p2.classList.add('err');toast('Passwords Do Not Match','alert-triangle');return}
   // Server-side now: the browser sends the passwords, never a hash. The
   // backend derives (slow KDF) and compares; `current` proves the change.
   const r=await fetch('/api/lock',{method:'POST',headers:{'Content-Type':'application/json'},
     body:JSON.stringify({passphrase:np,current:(cur&&cur.value)?cur.value:undefined})});
   if(!r.ok){const j=await r.json().catch(()=>({}));toast(j.detail||'Password Rejected By Backend','alert-triangle');return}
   settings.lock={on:true,pass_set:true};saveSettings();
   renderSettings();icons();
   toast('Password Saved - App Lock Enabled','key-round');
  })();
 }
 else if(act==='ip-save'){
  (async()=>{
   const cur=$('#ip-cur'),p1=$('#ip-p1'),p2=$('#ip-p2');
   if(settings.imgProt.hash&&!Sync.on){
    if(!cur.value){cur.classList.add('err');toast('Enter Current Passphrase','alert-triangle');return}
    if(!(await passMatches(cur.value,settings.imgProt.hash))){cur.classList.add('err');toast('Wrong Passphrase','alert-triangle');return}
   }
   const np=p1.value;
   if(np.length<4){p1.classList.add('err');toast('Passphrase Must Be At Least 4 Characters','alert-triangle');return}
   if(np!==p2.value){p2.classList.add('err');toast('Passphrases Do Not Match','alert-triangle');return}
   if(Sync.on){
    const r=await fetch('/api/images/passphrase',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({passphrase:np,current:cur?cur.value:null})});
    if(!r.ok){const j=await r.json().catch(()=>({}));toast(j.detail||'Passphrase Rejected By Backend','alert-triangle');return}
    settings.imgProt.hash='set';settings.imgProt.on=true;saveSettings();
    renderSettings();icons();
    toast('Passphrase Saved - Server-Side Encryption Active','key-round');
    return;
   }
   if(!HAS_SUBTLE){toast('WebCrypto Is Unavailable In This Context','alert-triangle');return}
   const newHash=await sha256(np);
   if(settings.imgProt.hash&&settings.imgProt.salt){
    const oldKey=await deriveKey(cur.value,settings.imgProt.salt);
    const salt=b2h(crypto.getRandomValues(new Uint8Array(16)));
    const newKey=await deriveKey(np,salt);
    const reEnc={};let failed=0;
    for(const id in encStore){
     try{
      const rec=encStore[id];
      const pt=await crypto.subtle.decrypt({name:'AES-GCM',iv:h2b(rec.iv)},oldKey,h2b(rec.data));
      const iv=crypto.getRandomValues(new Uint8Array(12));
      const ct=new Uint8Array(await crypto.subtle.encrypt({name:'AES-GCM',iv},newKey,pt));
      reEnc[id]={iv:b2h(iv),data:b2h(ct),t:rec.t};
     }catch(e2){failed++}
    }
    if(failed){toast(`${failed} Image${failed===1?'':'s'} Could Not Be Re-encrypted - Passphrase Unchanged`,'alert-triangle');return}
    // Transactional swap: journal the current meta + blobs first so an
    // interruption at any point rolls back completely on next boot
    // (recoverInterruptedRekey). Only then swap blobs and meta.
    settings.imgProt.rekey={salt:settings.imgProt.salt,hash:settings.imgProt.hash};
    if(!persistRekeyBackup()){delete settings.imgProt.rekey;return}
    saveSettings();
    Object.assign(encStore,reEnc);
    saveEncStore();
    settings.imgProt.salt=salt;
    settings.imgProt.hash=newHash;
    delete settings.imgProt.rekey;
    saveSettings();
    dropRekeyBackup();
    encKey=newKey;
   }else{
    settings.imgProt.salt=b2h(crypto.getRandomValues(new Uint8Array(16)));
    encKey=await deriveKey(np,settings.imgProt.salt);
    settings.imgProt.hash=newHash;
    saveSettings();
   }
   renderSettings();icons();
   hydrateEncImages(document);
   toast('Passphrase Saved','key-round');
  })().catch(e=>toast('Passphrase Save Failed: '+e.message,'alert-triangle'));
 }
 else if(act==='sh-save'){
  const plats=[];
  $$('[data-sh-plat]').forEach(el=>{if(el.classList.contains('on'))plats.push(el.dataset.shPlat)});
  const captions={};
  ['x','reddit','telegram'].forEach(id=>{
   const v=$('#sh-cap-'+id)?.value?.trim();
   if(v)captions[id]=v;
  });
  const defaultCaptions={};
  ['movie','scene','performer','studio'].forEach(id=>{
   const v=$('#sh-defcap-'+id)?.value?.trim();
   if(v)defaultCaptions[id]=v;
  });
  settings.share={platforms:plats,watermark:$('#sh-wm')?.checked!==false,defaultCaption:$('#sh-defcap')?.value?.trim()||'',captions,defaultCaptions};
  saveSettings();toast('Sharing Settings Saved','share-2');
 }
 else if(act==='ss-save'){
  settings.screenshot={
   scale:parseFloat($('#ss-scale-v')?.textContent)||2,
   watermark:$('#ss-wm')?.checked!==false,
   pageLabel:$('#ss-pagelabel')?.checked!==false,
   autoDownload:$('#ss-autodl')?.checked===true,
   format:$('#ss-fmt-jpg')?.classList.contains('primary')?'jpg':'png',
   quality:+($('#ss-quality-v')?.textContent?.replace('%',''))||92
  };
  saveSettings();toast('Screenshot Settings Saved','camera');
 }
 else if(act==='ss-scale'){
  if(!settings.screenshot)settings.screenshot={};
  let s=settings.screenshot.scale||2;
  s=Math.min(4,Math.max(1,s+(+a.dataset.d||0)));
  settings.screenshot.scale=s;
  const v=$('#ss-scale-v');v&&(v.textContent=s+'x');
  saveSettings();
 }
 else if(act==='ss-format'){
  if(!settings.screenshot)settings.screenshot={};
  settings.screenshot.format=a.dataset.v;
  $('#ss-fmt-png')?.classList.toggle('primary',a.dataset.v==='png');
  $('#ss-fmt-jpg')?.classList.toggle('primary',a.dataset.v==='jpg');
  $('#ss-quality-row')?.style.setProperty('display',a.dataset.v==='jpg'?'':'none');
  saveSettings();
 }
 else if(act==='ss-quality'){
  if(!settings.screenshot)settings.screenshot={};
  let q=settings.screenshot.quality||92;
  q=Math.min(100,Math.max(10,q+(+a.dataset.d||0)));
  settings.screenshot.quality=q;
  const v=$('#ss-quality-v');v&&(v.textContent=q+'%');
  saveSettings();
 }
 else if(act==='gl-save'){
  settings.gallery={
   enabled:$('#gl-on')?.checked!==false,
   count:+($('#gl-count-v')?.textContent)||12,
   show:+($('#gl-show-v')?.textContent)||12,
   size:$('#gl-sz-large')?.classList.contains('primary')?'large':'small'
  };
  saveSettings();toast('Gallery Settings Saved','images');
 }
 else if(act==='gl-count'){
  if(!settings.gallery)settings.gallery={};
  let c=settings.gallery.count||12;
  c=Math.min(50,Math.max(1,c+(+a.dataset.d||0)));
  settings.gallery.count=c;
  const v=$('#gl-count-v');v&&(v.textContent=c);
  saveSettings();
 }
 else if(act==='gl-show'){
  if(!settings.gallery)settings.gallery={};
  let c=settings.gallery.show||12;
  c=Math.min(50,Math.max(1,c+(+a.dataset.d||0)));
  settings.gallery.show=c;
  const v=$('#gl-show-v');v&&(v.textContent=c);
  saveSettings();
 }
 else if(act==='gl-size'){
  if(!settings.gallery)settings.gallery={};
  settings.gallery.size=a.dataset.v;
  $('#gl-sz-small')?.classList.toggle('primary',a.dataset.v==='small');
  $('#gl-sz-large')?.classList.toggle('primary',a.dataset.v==='large');
  saveSettings();
 }
 else if(act==='lock-now'){fetch('/api/lock/now',{method:'POST'}).then(r=>{if(r.ok)lockApp()}).catch(()=>{})}
 else if(act==='reveal'){
  const v=state.view;
  if(Sync.on&&v.name==='detail'&&(v.kind==='movie'||v.kind==='scene')){
   fetch(`/api/media/${v.kind}/${v.id}/reveal`,{method:'POST'}).then(r=>{
    if(!r.ok)throw new Error();
    toast('Folder Opened','folder-open');
   }).catch(()=>toast('Could Not Open Folder','alert-triangle'));
  }
 }
 else if(act==='dir-add'){
  openModal([{title:'Add Scan Directory',html:()=>`
   <label class="flab">Local Path</label>
   <div style="display:flex;gap:6px">
    <input class="field" id="ndir" placeholder="D:\\Media\\Movies" style="flex:1">
    <button class="btn" data-action="dir-browse" ${Sync.on?'':'disabled'} title="${Sync.on?'Opens A Native Folder Dialog':'Requires The Backend'}"><i data-lucide="folder-open"></i>Browse</button>
   </div>`,
   footer:()=>`<span class="push"></span><button class="btn" data-mclose="1">Cancel</button><button class="btn primary" id="ndir-ok">Add Directory</button>`,
   mount(){const inp=$('#ndir');inp.focus();
    $('#ndir-ok').addEventListener('click',()=>{const v=inp.value.trim();if(!v){inp.classList.add('err');return}settings.dirs.push(v);saveSettings();closeModal();renderSettings();icons();toast('Directory Added - Scanning...','folder-plus');lastScanDir=v;
     if(Sync.on){const stop=scanProgressWatch();
       fetch('/api/scan/candidates',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dirs:[v]})})
        .then(r=>{if(!r.ok)throw new Error('HTTP '+r.status);return r.json()})
        .then(j=>{stop('Scan Complete');openImportModal(j.candidates||[])})
        .catch(()=>{stop('Scan Failed');toast('Scan Failed','alert-triangle')})}
    })}}],0,560);
 }
 else if(act==='dir-browse'){
  a.disabled=true;
  fetch('/api/dialog/folder',{method:'POST'})
   .then(r=>{if(!r.ok)throw new Error('HTTP '+r.status);return r.json()})
   .then(j=>{a.disabled=false;if(j&&j.path){const i=$('#ndir');if(i)i.value=j.path}})
   .catch(()=>{a.disabled=false;toast('Folder Dialog Failed','alert-triangle')});
 }
 else if(act==='dir-del'){settings.dirs.splice(+a.dataset.i,1);saveSettings();renderSettings();icons()}
 else if(act==='scan'){
  const prog=$('#scanprog'),fill=$('#sp-fill'),txt=$('#sp-txt');
  if(!prog||!fill||!txt||!settings.dirs.length)return;
  prog.style.display='';a.disabled=true;
  if(Sync.on){
   fill.style.width='40%';txt.textContent='Scanning On Backend...';
   fetch('/api/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dirs:settings.dirs})})
    .then(r=>{if(!r.ok)throw new Error('HTTP '+r.status);return r.json()})
    .then(j=>{
     fill.style.width='100%';txt.textContent='Scan Complete';
     a.disabled=false;
     toast(`Scan Complete - ${j.count} Media File${j.count===1?'':'s'} Found - Use Import From Scan To Add Them`,'scan-search');
    })
    .catch(()=>{fill.style.width='100%';txt.textContent='Scan Failed';a.disabled=false;toast('Backend Scan Failed','alert-triangle')});
   return;
  }
  let i=0;const total=settings.dirs.length;
  const step=()=>{
   i++;fill.style.width=(i/total*100)+'%';
   txt.textContent=`Scanning ${settings.dirs[i-1]} (${i}/${total})`;
   if(i<total)setTimeout(step,700);
   else setTimeout(()=>{const found=Math.floor(Math.random()*4);txt.textContent='Scan Complete';a.disabled=false;
    toast(found?`Scan Complete - ${found} New Item${found===1?'':'s'} Found`:'Scan Complete - Nothing New',found?'sparkles':'check')},700);
  };
  setTimeout(step,300);
 }
 else if(act==='scan-import'){
  if(!Sync.on){toast('Import Requires The Backend','alert-triangle');return}
  const stop=scanProgressWatch();a.disabled=true;
  const scanDirs=lastScanDir?[lastScanDir]:settings.dirs;lastScanDir=null;
  fetch('/api/scan/candidates',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dirs:scanDirs})})
   .then(r=>{if(!r.ok)throw new Error('HTTP '+r.status);return r.json()})
   .then(j=>{stop('Scan Complete');a.disabled=false;openImportModal(j.candidates||[])})
   .catch(()=>{stop('Scan Failed');a.disabled=false;toast('Could Not Read Candidates','alert-triangle')});
 }
 else if(act==='imp-kind'){
  const card=a.closest('.impcard');
  const kind=card.dataset.kind=card.dataset.kind==='movie'?'scene':'movie';
  const isMovie=kind==='movie';
  a.innerHTML=`<i data-lucide="${isMovie?'film':'clapperboard'}"></i><span>${isMovie?'Movie':'Scene'}</span>`;
  const yw=card.querySelector('.imp-yearwrap'),dw=card.querySelector('.imp-datewrap');
  if(yw)yw.style.display=isMovie?'':'none';
  if(dw)dw.style.display=isMovie?'none':'';
  icons();
 }
 else if(act==='imp-do'){
  const card=a.closest('.impcard');
  const body={
   path:card.dataset.path,kind:card.dataset.kind,
   title:card.querySelector('.imp-title')?.value.trim()||card.dataset.guesstitle,
   year:parseInt(card.querySelector('.imp-year')?.value)||null,
   date:card.querySelector('.imp-date')?.value||null,
   duration_min:parseInt(card.querySelector('.imp-dur')?.value)||0,
   director:card.querySelector('.imp-dir')?.value.trim()||'',
   fav:card.querySelector('.imp-fav')?.checked||false
  };
  if(!body.title){toast('Title Is Required','alert-triangle');return}
  a.disabled=true;
  fetch('/api/scan/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
   .then(r=>{if(!r.ok)return r.json().then(j=>{throw new Error(j.detail||'Import Failed')});return r.json()})
   .then(j=>{
    const rec=j?.record;if(!rec)throw new Error('Unexpected Server Response');
    const local={
     id:rec.id,title:rec.title,fav:!!rec.fav,
     studioId:rec.studio_id||'',durationMin:rec.duration_min||0,
     director:rec.director||'',desc:rec.desc||'',
     filePath:rec.file_path||'',createdAt:rec.created_at||'',
     actorIds:rec.actor_ids||[],categoryIds:rec.category_ids||[]
    };
    if(body.kind==='movie'){
     local.year=rec.year||null;local.scenes=rec.scenes||0;
     local.posterF=rec.poster_f||'';local.posterB=rec.poster_b||'';
     DB.movies.push(local);
    }else{
     local.date=rec.date||null;local.movieId=rec.movie_id||'';
     local.covers=[rec.cover_a,rec.cover_b].filter(Boolean);local.thumb=rec.thumb||0;
     DB.scenes.push(local);
    }
    card.classList.add('imp-done');
    card.innerHTML=`<div class="imp-done-row"><i data-lucide="badge-check"></i><span>Imported As <b>${esc(local.title)}</b></span><button class="btn sm" data-action="open" data-kind="${body.kind}" data-id="${local.id}">Open</button><button class="btn sm ghost" data-action="imp-undone" data-path="${esc(body.path)}">Mark Unimported</button></div>`;
    icons();renderSidebar();
    toast('Imported: '+local.title,'import');
   })
   .catch(err=>{a.disabled=false;toast(err.message,'alert-triangle')});
 }
 else if(act==='imp-all'){
  const cards=$$('.impcard:not(.imp-done)');
  if(!cards.length){toast('Nothing To Import','check');return}
  a.disabled=true;
  // Queue may take a while per file — pending cards' own Import buttons must not
  // race it (the catch below re-arms a failed card's button).
  $$('.impcard:not(.imp-done) [data-action=imp-do]',$('#m-body')).forEach(b=>b.disabled=true);
  let done=0,failed=0;
  const total=cards.length;
  // A queue this long is slow (each import also stores sibling posters), so the
  // modal footer shows real progress instead of leaving one dead button.
  const prog=$('#impprog'),pFill=$('#ip-fill'),pTxt=$('#ip-txt');
  if(prog){prog.style.display='';pFill.style.width='0%';pTxt.textContent='0 / '+total}
  const tick=n=>{if(pFill)pFill.style.width=Math.round(n/total*100)+'%';
   if(pTxt)pTxt.textContent='Adding '+n+' / '+total+' File'+(total===1?'':'s')};
  const importOne=(card)=>{
   if(!card)return Promise.resolve();
   const body={
    path:card.dataset.path,kind:card.dataset.kind,
    title:card.querySelector('.imp-title')?.value.trim()||card.dataset.guesstitle,
    year:parseInt(card.querySelector('.imp-year')?.value)||null,
    date:card.querySelector('.imp-date')?.value||null,
    duration_min:parseInt(card.querySelector('.imp-dur')?.value)||0,
    director:card.querySelector('.imp-dir')?.value.trim()||'',
    fav:card.querySelector('.imp-fav')?.checked||false
   };
   if(!body.title){failed++;return importOne(cards.shift())}
   return fetch('/api/scan/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
    .then(r=>{if(!r.ok)throw new Error();return r.json()})
    .then(j=>{
     const rec=j?.record;if(!rec)throw new Error('Unexpected Server Response');
     const local={
      id:rec.id,title:rec.title,fav:!!rec.fav,
      studioId:rec.studio_id||'',durationMin:rec.duration_min||0,
      director:rec.director||'',desc:rec.desc||'',
      filePath:rec.file_path||'',createdAt:rec.created_at||'',
      actorIds:rec.actor_ids||[],categoryIds:rec.category_ids||[]
     };
     if(body.kind==='movie'){
      local.year=rec.year||null;local.scenes=rec.scenes||0;
      local.posterF=rec.poster_f||'';local.posterB=rec.poster_b||'';
      DB.movies.push(local);
     }else{
      local.date=rec.date||null;local.movieId=rec.movie_id||'';
      local.covers=[rec.cover_a,rec.cover_b].filter(Boolean);local.thumb=rec.thumb||0;
      DB.scenes.push(local);
     }
     card.classList.add('imp-done');
     card.innerHTML=`<div class="imp-done-row"><i data-lucide="badge-check"></i><span>Imported As <b>${esc(local.title)}</b></span><button class="btn sm" data-action="open" data-kind="${body.kind}" data-id="${local.id}">Open</button><button class="btn sm ghost" data-action="imp-undone" data-path="${esc(body.path)}">Mark Unimported</button></div>`;
     done++;
     tick(done);
    })
    .catch(()=>{failed++;tick(done+failed);card.querySelector('[data-action=imp-do]')?.removeAttribute('disabled')})
    // then(), not finally(): this promise must resolve only once the WHOLE queue
    // is done — otherwise the completion toast fires after the first import with
    // a wrong count, and the dialog gets closed while files are still pending.
    .then(()=>importOne(cards.shift()));
  };
  importOne(cards.shift()).then(()=>{
   if(prog)prog.style.display='none';
   a.disabled=false;icons();renderSidebar();
   toast(`Import Complete - ${done} Imported${failed?', '+failed+' Failed':''}`,done?'check':'alert-triangle');
  });
 }
 else if(act==='imp-undone'){
  const path=a.dataset.path;
  const card=a.closest('.impcard');
  const row=a.closest('.srcrow');
  // Rebuild the candidate from the card's own data, or from the copy stashed on
  // an "Already Imported" row, so the file goes straight back to being editable.
  let cand=card?{path,name:(card.querySelector('.imp-path')||{}).textContent||'',
                 guess_title:card.dataset.guesstitle||'',guess_kind:card.dataset.kind||'scene'}:null;
  if(!cand&&a.dataset.cand){try{cand=JSON.parse(a.dataset.cand)}catch(e){}}
  const mv=DB.movies.find(m=>m.filePath===path);
  const sc=mv?null:DB.scenes.find(s=>s.filePath===path);
  const rec=mv||sc;
  const finish=()=>{
   if(rec){const arr=mv?DB.movies:DB.scenes;arr.splice(arr.indexOf(rec),1);renderSidebar()}
   fetch('/api/scan/undone',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path})}).catch(()=>{});
   const host=$('#m-body');
   if(cand&&host){
    const tmp=document.createElement('div');
    tmp.innerHTML=importCardHTML(cand);
    const fresh=tmp.firstElementChild;
    if(card&&card.parentNode)card.replaceWith(fresh);
    else host.insertBefore(fresh,host.firstElementChild);
    icons();
   }
   if(row)row.remove();   // the "Already Imported" row it came from is now a card
   toast('Unimported - Fix The Details, Then Import Again','rotate-ccw');
  };
  // The import created a real record; un-importing must remove it, otherwise the
  // file returns as a candidate and re-importing it duplicates the row.
  if(rec){
   fetch(`/api/${mv?'movies':'scenes'}/${rec.id}`,{method:'DELETE'})
    .then(r=>{if(!r.ok)throw new Error('HTTP '+r.status);finish()})
    .catch(()=>toast('Could Not Remove The Imported Record','alert-triangle'));
  }else finish();
 }
 else if(act==='dup-check'){
  if(Sync.on){
   fetch('/api/tools/duplicates',{method:'POST'})
    .then(r=>r.json())
    .then(j=>{
     const kmap={movies:'movie',scenes:'scene',performers:'performer',studios:'studio',categories:'category'};
     const secs=(j.sections||[]).map(s=>`
      <div style="margin-bottom:18px"><div class="flab">${esc(s.label)} - ${s.groups.reduce((n,g)=>n+g.length,0)} Items</div>
      ${s.groups.map(g=>`<div style="margin-bottom:12px">
        ${g.map(rid=>{const kind=kmap[s.kind];const it=byId(kind,rid);if(!it)return '';
         const src=kind==='movie'?it.posterF:kind==='scene'?((it.covers||[])[0]||''):it.photo||'';
         return `<div class="res" data-action="open" data-kind="${kind}" data-id="${it.id}">${mediaPh(src,kind==='scene'?'w':'',({movie:'film',scene:'clapperboard',performer:'user',studio:'building-2',category:'tag'})[kind]||'image')}<div><b>${esc(it.title||it.name)}</b><div class="mono">${kindLabel(kind)}</div></div><i data-lucide="arrow-up-right"></i></div>`}).join('')}
      </div>`).join('')}</div>`).join('');
     openModal([{title:'Duplicate Check',html:()=>secs||`<div style="display:flex;flex-direction:column;align-items:center;gap:14px;padding:34px 0"><i data-lucide="badge-check" style="width:30px;height:30px;color:var(--accent)"></i><span class="cmsg">No Duplicates Found.</span></div>`,
      footer:()=>`<span class="push"></span><button class="btn" data-mclose="1">Close</button>`}],0,620);
     icons();
    })
    .catch(()=>toast('Backend Duplicate Check Failed','alert-triangle'));
   return;
  }
  const lists=[
   ['Movies',DB.movies.map(x=>({t:x.title,kind:'movie',id:x.id,y:x.year}))],
   ['Scenes',DB.scenes.map(x=>({t:x.title,kind:'scene',id:x.id,y:x.date}))],
   ['Performers',DB.performers.map(x=>({t:x.name,kind:'performer',id:x.id,y:x.gender==='m'?'Male':'Female'}))],
   ['Studios',DB.studios.map(x=>({t:x.name,kind:'studio',id:x.id,y:x.country||''}))],
   ['Categories',DB.categories.map(x=>({t:x.name,kind:'category',id:x.id,y:''}))],
  ];
  const sections=lists.map(([label,items])=>{
   const seen={},dups={};
   items.forEach(x=>{const k=x.t.trim().toLowerCase();if(seen[k]){(dups[k]=dups[k]||[seen[k]]).push(x)}else seen[k]=x});
   const groups=Object.values(dups);
   return groups.length?{label,groups}:null;
  }).filter(Boolean);
  const total=sections.reduce((n,s)=>n+s.groups.length,0);
  openModal([{title:'Duplicate Check',html:()=>total?`
   <div class="cmsg" style="margin-bottom:14px">${total} Duplicate Group${total===1?'':'s'} Found Across Movies, Scenes, Performers, Studios And Categories:</div>
   ${sections.map(s=>`<div style="margin-bottom:18px"><div class="flab">${s.label} - ${s.groups.reduce((n,g)=>n+g.length,0)} Items</div>
    ${s.groups.map(g=>`<div style="margin-bottom:12px">
     ${g.map(x=>{const it=byId(x.kind,x.id);const src=x.kind==='movie'?it.posterF:x.kind==='scene'?((it.covers||[])[0]||''):it.photo||'';
      return `<div class="res" data-action="open" data-kind="${x.kind}" data-id="${x.id}">${mediaPh(src,x.kind==='scene'?'w':'',({movie:'film',scene:'clapperboard',performer:'user',studio:'building-2',category:'tag'})[x.kind]||'image')}<div><b>${esc(x.t)}</b><div class="mono">${kindLabel(x.kind)}${x.y?' · '+esc(String(x.y)):''}</div></div><i data-lucide="arrow-up-right"></i></div>`}).join('')}
    </div>`).join('')}</div>`).join('')}`
   :`<div style="display:flex;flex-direction:column;align-items:center;gap:14px;padding:34px 0"><i data-lucide="badge-check" style="width:30px;height:30px;color:var(--accent)"></i><span class="cmsg">No Duplicates Found.</span></div>`,
   footer:()=>`<span class="push"></span><button class="btn" data-mclose="1">Close</button>`}],0,620);
 }
 else if(act==='title-case'){
  if(Sync.on){
   fetch('/api/tools/titlecase',{method:'POST'})
    .then(r=>r.json())
    .then(j=>{render();toast(`${j.changed||0} Title${(j.changed||0)===1?'':'s'} Converted To Title Case`,'case-upper')})
    .catch(()=>toast('Backend Title-Case Failed','alert-triangle'));
   return;
  }
  let n=0;
  DB.movies.forEach(m=>{const t2=titleCase(m.title);if(t2!==m.title){m.title=t2;n++}});
  DB.scenes.forEach(sc=>{const t2=titleCase(sc.title);if(t2!==sc.title){sc.title=t2;n++}});
  render();toast(n?`${n} Title${n===1?'':'s'} Converted To Title Case`:'All Titles Already In Title Case','case-upper');
 }
 else if(act==='proxy-detect'){
  // Neither the browser nor the backend can enumerate system proxies; the old
  // behavior fabricated a random result and wrote it into settings.
  toast('System Proxy Detection Is Not Available Here - Enter Your Proxy Manually','alert-triangle');
 }
 else if(act==='proxy-save'){
  settings.proxy.proto=($$('input[name=pxproto]').find(r=>r.checked)?.value)||'http';
  settings.proxy.host=$('#px-host').value.trim();settings.proxy.port=$('#px-port').value.trim();
  settings.proxy.user=$('#px-user')?.value.trim()||'';settings.proxy.pass=$('#px-pass')?.value.trim()||'';
  saveSettings();toast('Proxy Settings Saved','globe');
 }
 else if(act==='reset'){
  openModal([{title:'Return To Default Settings',html:()=>`<div class="cmsg">This Resets Theme, Advanced Colors, Data Sources, External Scrapers, Directories, Player, AI, Password, Image Protection, Cache And Proxy Settings To Their Defaults. Protected Image Copies Are Removed. Your Library Items Are Kept. Continue?</div>`,
   footer:()=>`<span class="push"></span><button class="btn" data-mclose="1">Cancel</button><button class="btn" id="rst-ok"><i data-lucide="history"></i>Return To Default Settings</button>`,
   mount(){$('#rst-ok').addEventListener('click',()=>{
    settings=JSON.parse(JSON.stringify(DEF_SETTINGS));
    clearImageCache(false);
    Object.keys(encStore).forEach(k=>delete encStore[k]);
    try{localStorage.removeItem('obscura:encimgs')}catch(e){}
    saveSettings();applyTheme();applyAdvanced();closeModal();render();
    toast('Settings Restored To Defaults','history');
   })}}],0,520);
 }
 else if(act==='wipe'){
  openModal([{title:'Clear All Data',html:()=>`
   <div class="cmsg" style="margin-bottom:12px">This Permanently Deletes Everything: All Movies, Scenes, Performers, Studios, Categories, Favorites, Encrypted Images, Data Sources, Scrapers And Settings. This Cannot Be Undone.</div>
   <label class="flab">Type DELETE To Confirm</label>
   <input class="field" id="wipe-confirm" placeholder="Type DELETE" autocomplete="off">`,
   footer:()=>`<span class="push"></span><button class="btn" data-mclose="1">Cancel</button><button class="btn danger" id="wipe-ok" disabled><i data-lucide="trash-2"></i>Clear All Data</button>`,
   mount(b,f){
    const inp=$('#wipe-confirm'),ok=$('#wipe-ok',f);
    inp.addEventListener('input',()=>{ok.disabled=inp.value.trim().toUpperCase()!=='DELETE'});
    inp.addEventListener('keydown',e=>{if(e.key==='Enter'&&!ok.disabled)ok.click()});
    setTimeout(()=>inp.focus(),50);
    ok.addEventListener('click',()=>{
     ok.disabled=true;ok.textContent='Clearing...';
     const wipeLocal=()=>{
      DB.movies.length=0;DB.scenes.length=0;DB.performers.length=0;DB.studios.length=0;DB.categories.length=0;
      Object.keys(T).forEach(k=>resetTabFilters(k));
      Positions.clearAll();
      bulkSel.selected.clear();bulkSel.active=false;
      state.profileTab='favorites';lastScanDir=null;
      clearImageCache(false);
      Object.keys(encStore).forEach(k=>delete encStore[k]);
      try{localStorage.removeItem('obscura:encimgs')}catch(e2){}
      dropRekeyBackup();
      settings=JSON.parse(JSON.stringify(DEF_SETTINGS));
      saveSettings();applyTheme();applyAdvanced();
      closeModal();
      state.view={name:'tab',tab:'movies'};state.history=[];
      render();
      toast('All Data Cleared','trash-2');
     };
     if(Sync.on){fetch('/api/wipe',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirm:'DELETE MY LIBRARY'})}).then(r=>r.ok?wipeLocal():toast('Backend Wipe Failed','alert-triangle')).catch(()=>toast('Backend Wipe Failed','alert-triangle'))}
     else wipeLocal();
    });
   }}],0,520);
 }
});
document.addEventListener('click',e=>{
 const el=e.target.closest('[data-sh-plat]');
 if(el){el.classList.toggle('on');return;}
});
document.addEventListener('keydown',e=>{
 if(e.key==='Escape'){
  if($('#lock-root').classList.contains('show'))return;
  if(modalSteps){modalIdx>0?(modalIdx--,renderModal()):closeModal()}
  else if($('#drawer-root').innerHTML)closeDrawer();
 }
});
