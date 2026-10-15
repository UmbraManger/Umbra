"use strict";
/* ===== TABS ===== */
function yearsRange(){const ys=new Set();DB.movies.forEach(m=>ys.add(m.year));DB.scenes.forEach(sc=>ys.add(String(sc.date).slice(0,4)));return [...ys].filter(Boolean).sort()}
let _ypDocClose=null; // one document-click closer for the year picker (replaced, not stacked)
function filterCount(tab){const f=T[tab].f;if(!f)return 0;if(tab==='performers')return(f.gender?1:0)+f.nationalities.size+f.hairColors.size+f.ethnicities.size+(f.boobType?1:0)+(f.piercings?1:0)+(f.tattoos?1:0)+((f.csMin||f.csMax)?1:0)+((f.heightMin||f.heightMax)?1:0)+(f.sort!=='az'?1:0);return f.studios.size+f.cats.size+f.performers.size+((f.ymin||f.ymax)?1:0)}
/* Shared pager markup for the tab lists and the detail-page catalogues
   (studio/category movies + scenes), so paging looks and behaves the same
   everywhere. `numAttr` names the attribute that carries the target page number
   — boot.js reads [data-page] for the tab lists, detail sections pass
   [data-dpage] + a `key` so they can be paged with no tab state of their own. */
function pagerHTML(o){
 const A=o.numAttr||'data-page',K=o.key!=null?` data-dkey="${esc(o.key)}"`:'',page=o.page,pages=o.pages;
 const btn=(p,label,cur,dis)=>`<button class="btn sm${cur?' on':''}"${A}="${p}"${K}${cur?' aria-current="page"':''}${dis?' disabled':''}>${label}</button>`;
 let pnums='';
 if(pages<=7){for(let i=1;i<=pages;i++)pnums+=btn(i,String(i),i===page);}
 else{
  pnums+=btn(1,'1',page===1);
  let s=Math.max(2,page-2),e=Math.min(pages-1,page+2);
  if(page<=4){s=2;e=Math.min(5,pages-1)}
  if(page>=pages-3){s=Math.max(2,pages-4);e=pages-1}
  if(s>2)pnums+=`<span class="pg-gap">…</span>`;
  for(let i=s;i<=e;i++)pnums+=btn(i,String(i),i===page);
  if(e<pages-1)pnums+=`<span class="pg-gap">…</span>`;
  pnums+=btn(pages,String(pages),page===pages);
 }
 return `<div class="pager" role="navigation" aria-label="Pagination">${btn(page-1,'<i data-lucide="chevron-left"></i>',false,page<=1)}${pnums}${btn(page+1,'<i data-lucide="chevron-right"></i>',false,page>=pages)}</div>`;
}
function listMainHTML(tab){
 const t=T[tab],items=filtered(tab);
 if(!items.length)return `<div class="empty"><i data-lucide="inbox"></i><span>Nothing Here Yet.</span><span class="mono">Adjust Filters Or Add An Item</span></div>`;
 const pp=(settings.perPage&&settings.perPage[tab])||24;
 const total=items.length,pages=Math.ceil(total/pp);
 if(t.page>pages)t.page=pages;
 if(t.page<1)t.page=1;
 const start=(t.page-1)*pp;
 const pageItems=items.slice(start,start+pp);
 const cardFn=x=>tab==='movies'?movieCard(x):tab==='scenes'?sceneCard(x):tab==='performers'?perfCard(x):tab==='studios'?studioCard(x):categoryCard(x);
 const rowFn=x=>tab==='studios'?studioCard(x):tab==='categories'?categoryCard(x):rowFor(tab,x);
 const grid=t.view==='list'
  ?`<div class="rows">${pageItems.map(rowFn).join('')}</div>`
  :`<div class="grid" style="--cw:${t.cw}px">${pageItems.map(cardFn).join('')}</div>`;
 let pager='';
 if(pages>1)pager=pagerHTML({page:t.page,pages,total,pp});
 return `<div id="list-main">${grid}${pager}</div>`;
}
/* Bulk action bar — lives inline in the toolbar's .sp gap (between the search
   box and the view switcher), centred in that gap, so it never adds layout and
   never shifts the list. Icon-only buttons; the count is a plain number in a
   chip styled like its neighbours; hidden at zero selected. */
function bulkBarHTML(tab){
 if(!bulkSel.active)return '';
 const n=bulkSel.selected.size;
 const dis=n?'':' disabled';
 const hide=n?'':' style="visibility:hidden" aria-hidden="true"';
 return `<div class="bulk-bar"${hide}><span class="bulk-count btn icon" title="${n} Selected"><span class="bc-n">${n}</span></span><button class="btn icon" data-action="bulk-fav"${dis} title="Toggle Favorite"><i data-lucide="heart"></i></button><button class="btn icon" data-action="bulk-select-all" title="Select All"><i data-lucide="check-square"></i></button><button class="btn icon" data-action="bulk-clear" title="Clear"><i data-lucide="x-square"></i></button><button class="btn icon danger" data-action="bulk-delete"${dis} title="Delete"><i data-lucide="trash-2"></i></button></div>`;
}
function listBodyHTML(tab){
 return listMainHTML(tab);
}
/* Selection-only change: update in place. A full renderTab() here rebuilt every
   <img>, re-firing their onload object-position snap -> the poster "jumped". */
function updateBulkUI(tab){
 $$('[data-bulk-id]').forEach(chk=>{
  const on=bulkSel.selected.has(chk.dataset.bulkId);
  chk.classList.toggle('on',on);
  const host=chk.closest('[data-action="open"]');
  if(host)host.toggleAttribute('data-bulk-sel',on);
 });
 const slot=$('#bulkbar-slot');
 if(slot){slot.innerHTML=bulkBarHTML(tab);icons()}
}
function toolbarHTML(tab){
 const cfg=TABS[tab],t=T[tab];
 const isMedia=tab==='movies'||tab==='scenes'||tab==='performers'||tab==='studios'||tab==='categories';
 let mediaCtrl='';
 if(isMedia){
  mediaCtrl=`<div class="seg"><button data-action="setview" data-v="grid" class="${t.view==='grid'?'on':''}" title="Grid"><i data-lucide="layout-grid"></i></button><button data-action="setview" data-v="list" class="${t.view==='list'?'on':''}" title="List"><i data-lucide="list"></i></button><button data-action="bulk-toggle" class="${bulkSel.active?'on':''}" title="Select Multiple"><i data-lucide="square-check"></i></button></div>`;
  if(t.view==='grid')mediaCtrl+=`<span class="sizewrap"><i data-lucide="scaling"></i><input type="range" min="150" max="340" step="10" value="${t.cw}" data-role="cw"></span>`;
 }
 let filterBtn='',filterPanel='';
 if(tab==='movies'||tab==='scenes'||tab==='performers'){
  const n=filterCount(tab);
  filterBtn=`<span class="fwrap2"><button class="btn" data-action="filter"><i data-lucide="sliders-horizontal"></i>Filter<span class="fbadge" data-role="fbadge" ${n?'':'style="display:none"'}>${n}</span></button></span>`;
  filterPanel=`<div class="fpop" data-role="fpop">${tab==='performers'?perfFilterPopHTML():filterPopHTML(tab)}</div>`;
 }
 const addLabel=tab==='movies'?'Add Movie':tab==='scenes'?'Add Scene':tab==='performers'?'Add Performer':tab==='studios'?'Add Studio':'Add Category';
 return `<div class="toolbar">
  <div class="searchbox"><i data-lucide="search"></i><input placeholder="${cfg.ph}" value="${esc(t.q||'')}" data-role="q"></div>
  ${filterBtn}<div class="sp"><div id="bulkbar-slot">${bulkBarHTML(tab)}</div></div>${mediaCtrl}
  <button class="btn primary" data-action="add"><i data-lucide="plus"></i>${addLabel}</button>
 </div>${filterPanel}`;
}
function filterPopHTML(tab){
 const isMovie=tab==='movies';
 const f=T[tab].f;
 const siteList=DB.studios.map(s=>({id:s.id,n:s.name,c:isMovie?DB.movies.filter(x=>x.studioId===s.id).length:DB.scenes.filter(x=>x.siteId===s.id).length})).filter(s=>s.c>0);
 if(siteList.length>12)siteList.sort((a,b)=>b.c-a.c||a.n.localeCompare(b.n));
 else siteList.sort((a,b)=>a.n.localeCompare(b.n));
 const perfList=DB.performers.map(p=>({id:p.id,n:p.name,photo:p.photo||'',c:(isMovie?DB.movies:DB.scenes).filter(x=>ensureArr(x.actorIds).includes(p.id)).length})).filter(p=>p.c>0);
 if(perfList.length>12)perfList.sort((a,b)=>b.c-a.c||a.n.localeCompare(b.n));
 else perfList.sort((a,b)=>a.n.localeCompare(b.n));
 const cats=[...DB.categories];
 if(cats.length>12)cats.sort((a,b)=>catUsage(b)-catUsage(a)||a.name.localeCompare(b.name));
 else cats.sort((a,b)=>a.name.localeCompare(b.name));
 const lim=Math.max(1,Math.min(settings.catLimit||10,8));
 const chipBlock=(list,fk,selectedSet)=>{
  const chip=item=>`<button type="button" class="chip ${selectedSet.has(item.id)?'on':''}" data-fk="${fk}" data-fv="${item.id}">${esc(item.n)}</button>`;
  const shown=list.slice(0,lim),hidden=list.slice(lim);
  const moreBtn=hidden.length?`<button type="button" class="chip" data-role="more" data-more-label="+${hidden.length} More">+${hidden.length} More</button>`:'';
  const main=shown.map(chip).join('')+moreBtn;
  const overflow=hidden.length?`<div class="filt-overflow" hidden>${hidden.map(chip).join('')}<button type="button" class="chip" data-role="less">Show Less</button></div>`:'';
  return {main,overflow};
 };
 const sites=chipBlock(siteList,'site',f.studios);
 const perfChip=item=>`<button type="button" class="peep ${f.performers.has(item.id)?'on':''}" data-fk="perf" data-fv="${esc(item.id)}">${item.photo?`<img src="${esc(item.photo)}" alt="">`:''}${esc(item.n)}</button>`;
 const perfShown=perfList.slice(0,lim),perfHidden=perfList.slice(lim);
 const perfMoreBtn=perfHidden.length?`<button type="button" class="chip" data-role="more" data-more-label="+${perfHidden.length} More">+${perfHidden.length} More</button>`:'';
 const perfMain=perfShown.map(perfChip).join('')+perfMoreBtn;
 const perfOverflow=perfHidden.length?`<div class="filt-overflow" hidden>${perfHidden.map(perfChip).join('')}<button type="button" class="chip" data-role="less">Show Less</button></div>`:'';
 const catChip=c=>`<button type="button" class="chip ${f.cats.has(c.id)?'on':''}" data-fk="cat" data-fv="${c.id}">${esc(c.name)}</button>`;
 const catShown=cats.slice(0,lim),catHidden=cats.slice(lim);
 const catMoreBtn=catHidden.length?`<button type="button" class="chip" data-role="more" data-more-label="+${catHidden.length} More">+${catHidden.length} More</button>`:'';
 const catMain=catShown.map(catChip).join('')+catMoreBtn;
 const catOverflow=catHidden.length?`<div class="filt-overflow" hidden>${catHidden.map(catChip).join('')}<button type="button" class="chip" data-role="less">Show Less</button></div>`:'';
 return `
  <div class="fgroup"><div class="flab">${siteList.length>12?'Studios · Popular First':'Studios'}</div><div class="chiprow">${sites.main}</div>${sites.overflow}</div>
  <div class="fgroup"><div class="flab">${cats.length>12?'Categories · Popular First':'Categories'}</div><div class="chiprow">${catMain}</div>${catOverflow}</div>
  <div class="fgroup"><div class="flab">${perfList.length>12?'Performers · Popular First':'Performers'}</div><div class="cast">${perfMain}</div>${perfOverflow}</div>
  <div class="fgroup"><div class="flab">Year Range</div><div class="frow" style="max-width:340px;gap:10px">
   <div class="ypick-wrap" data-role="ypick" data-which="from"><div class="ypick-input" data-role="ypick-trigger"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg><span${f.ymin?'':' class="ph"'}>${f.ymin||'From...'}</span>${f.ymin?'<button type="button" class="ypick-clear" data-role="ypick-clear" title="Clear">✕</button>':''}</div></div>
   <div class="ypick-wrap" data-role="ypick" data-which="to"><div class="ypick-input" data-role="ypick-trigger"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg><span${f.ymax?'':' class="ph"'}>${f.ymax||'To...'}</span>${f.ymax?'<button type="button" class="ypick-clear" data-role="ypick-clear" title="Clear">✕</button>':''}</div></div>
  </div><div class="ypick-popup" data-role="ypick-popup"></div></div>
  <div class="fgroup"><div class="flab">Sort</div><select class="field" data-fk="sort"><option value="new" ${f.sort==='new'?'selected':''}>Newest First</option><option value="old" ${f.sort==='old'?'selected':''}>Oldest First</option><option value="az" ${f.sort==='az'?'selected':''}>Title A-Z</option><option value="long" ${f.sort==='long'?'selected':''}>Longest</option></select></div>
  <div class="fpop-foot"><button class="btn ghost sm" data-action="filter-clear">Clear All</button><button class="btn primary" data-action="filter-apply"><i data-lucide="check"></i>Apply</button></div>`;
}
function perfFilterPopHTML(){
 const f=T.performers.f;
 const chipOn=(set,val)=>set.has(val)?'on':'';
 const genders=[{id:'m',n:'Male'},{id:'f',n:'Female'}];
 const natSet=new Set(),hairSet=new Set(),ethSet=new Set();
 DB.performers.forEach(p=>{if(p.nationality)natSet.add(p.nationality);if(p.hair)hairSet.add(p.hair);if(p.ethnicity)ethSet.add(p.ethnicity)});
 const natList=[...natSet].sort().map(n=>({id:n,n}));
 const hairList=[...hairSet].sort().map(n=>({id:n,n}));
 const ethList=[...ethSet].sort().map(n=>({id:n,n}));
 const lim=Math.max(1,Math.min(settings.catLimit||10,8));
 const chipBlock=(list,fk,selectedSet)=>{
  const chip=item=>`<button type="button" class="chip ${selectedSet.has(item.id)?'on':''}" data-fk="${fk}" data-fv="${item.id}">${esc(item.n)}</button>`;
  const shown=list.slice(0,lim),hidden=list.slice(lim);
  const moreBtn=hidden.length?`<button type="button" class="chip" data-role="more" data-more-label="+${hidden.length} More">+${hidden.length} More</button>`:'';
  const main=shown.map(chip).join('')+moreBtn;
  const overflow=hidden.length?`<div class="filt-overflow" hidden>${hidden.map(chip).join('')}<button type="button" class="chip" data-role="less">Show Less</button></div>`:'';
  return {main,overflow};
 };
 const genderChip=g=>`<button type="button" class="chip ${f.gender===g.id?'on':''}" data-fk="gender" data-fv="${g.id}">${esc(g.n)}</button>`;
 const nat=chipBlock(natList,'nat',f.nationalities);
 const hair=chipBlock(hairList,'hair',f.hairColors);
 const eth=chipBlock(ethList,'eth',f.ethnicities);
 const boobList=BOOBS.map(n=>({id:n,n}));
 const genderChip2=(set,val,label)=>`<button type="button" class="chip ${set===val?'on':''}" data-fk="${set}" data-fv="${val}">${esc(label)}</button>`;
 const boobChip=b=>`<button type="button" class="chip ${f.boobType===b.id?'on':''}" data-fk="boobType" data-fv="${b.id}">${esc(b.n)}</button>`;
 const csYears=()=>{const ys=new Set();DB.performers.forEach(p=>{if(p.careerStart)ys.add(p.careerStart)});return[...ys].filter(Boolean).sort()};
 return `
  <div class="fgroup"><div class="flab">Gender</div><div class="chiprow">${genders.map(genderChip).join('')}</div></div>
  <div class="fgroup"><div class="flab">${ethList.length>lim?'Ethnicity · All':'Ethnicity'}</div><div class="chiprow">${eth.main}</div>${eth.overflow}</div>
  <div class="fgroup"><div class="flab">${natList.length>lim?'Nationality · All':'Nationality'}</div><div class="chiprow">${nat.main}</div>${nat.overflow}</div>
  <div class="fgroup"><div class="flab">${hairList.length>lim?'Hair Color · All':'Hair Color'}</div><div class="chiprow">${hair.main}</div>${hair.overflow}</div>
  <div class="fgroup"><div class="flab">Boobs</div><div class="chiprow">${boobList.map(boobChip).join('')}</div></div>
  <div class="fgroup"><div class="flab">Body Decoration</div><div class="chiprow"><button type="button" class="chip ${f.piercings?'on':''}" data-fk="pierc" data-fv="yes">Piercings</button><button type="button" class="chip ${f.tattoos?'on':''}" data-fk="tatto" data-fv="yes">Tattoos</button></div></div>
  <div class="fgroup"><div class="flab">Career Start Range</div><div class="frow" style="max-width:340px;gap:10px">
   <div class="ypick-wrap" data-role="ypick" data-which="from"><div class="ypick-input" data-role="ypick-trigger"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg><span${f.csMin?'':' class="ph"'}>${f.csMin||'From...'}</span>${f.csMin?'<button type="button" class="ypick-clear" data-role="ypick-clear" title="Clear">✕</button>':''}</div></div>
   <div class="ypick-wrap" data-role="ypick" data-which="to"><div class="ypick-input" data-role="ypick-trigger"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg><span${f.csMax?'':' class="ph"'}>${f.csMax||'To...'}</span>${f.csMax?'<button type="button" class="ypick-clear" data-role="ypick-clear" title="Clear">✕</button>':''}</div></div>
  </div><div class="ypick-popup" data-role="ypick-popup"></div></div>
  <div class="fgroup"><div class="flab">Height Range (cm)</div><div class="frow" style="max-width:340px;gap:10px"><input type="number" class="field" data-fk="heightMin" placeholder="Min" min="100" max="250" step="1" value="${esc(f.heightMin||'')}"><input type="number" class="field" data-fk="heightMax" placeholder="Max" min="100" max="250" step="1" value="${esc(f.heightMax||'')}"></div></div>
  <div class="fgroup"><div class="flab">Sort</div><select class="field" data-fk="sort"><option value="az" ${f.sort==='az'?'selected':''}>Name A-Z</option><option value="za" ${f.sort==='za'?'selected':''}>Name Z-A</option><option value="new" ${f.sort==='new'?'selected':''}>Newest Career</option><option value="old" ${f.sort==='old'?'selected':''}>Oldest Career</option></select></div>
  <div class="fpop-foot"><button class="btn ghost sm" data-action="filter-clear">Clear All</button><button class="btn primary" data-action="filter-apply"><i data-lucide="check"></i>Apply</button></div>`;
}
function yearPickerInit(pop,pend,updBadge){
 const yps=pop.querySelectorAll('[data-role=ypick]');
 const popup=pop.querySelector('.fgroup:last-of-type [data-role=ypick-popup]')||pop.querySelector('[data-role=ypick-popup]');
 if(!popup||!yps.length)return;
 let activeWhich=null,activeTrigger=null;
 const decades={};yps.forEach(w=>{decades[w.dataset.which]=Math.floor(((w.dataset.which==='from'?pend.ymin:pend.ymax)||new Date().getFullYear())/12)*12});
 const renderYearGrid=()=>{
  if(!activeWhich)return;
  const which=activeWhich,decadeStart=decades[which];
  const minY=1900,maxY=2099,sel=which==='from'?pend.ymin:pend.ymax,selOther=which==='from'?pend.ymax:pend.ymin;
  let h=`<div class="ypick-label">${which==='from'?'From Year':'To Year'}</div><div class="ypick-head"><button type="button" data-role="yp-dec-prev"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg></button><span class="yr-label">${decadeStart}-${decadeStart+11}</span><button type="button" data-role="yp-dec-next"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg></button></div><div class="ypick-grid">`;
  for(let y=decadeStart;y<decadeStart+12;y++){
   const out=y<minY||y>maxY;
   const isSel=y==sel;
   const inRange=sel&&selOther&&((which==='from'&&y>=sel&&y<=selOther)||(which==='to'&&y>=selOther&&y<=sel));
   const cls=out?'out':isSel?'sel':inRange?'in-range':'';
   h+=`<button type="button" data-year="${y}" class="${cls}"${out?' disabled':''}>${y}</button>`;
  }
  h+='</div>';
  const grid=popup.querySelector('.ypick-grid');
  if(grid){grid.style.opacity='0';setTimeout(()=>{popup.innerHTML=h;const g2=popup.querySelector('.ypick-grid');if(g2)requestAnimationFrame(()=>g2.style.opacity='1')},120)}
  else popup.innerHTML=h;
 };
 const closePopup=()=>{popup.classList.remove('open');if(activeTrigger)activeTrigger.classList.remove('open');activeWhich=null;activeTrigger=null};
 yps.forEach(wrap=>{
  const which=wrap.dataset.which;
  const trigger=wrap.querySelector('[data-role=ypick-trigger]');
  trigger.addEventListener('click',e=>{if(e.target.closest('[data-role=ypick-clear]'))return;e.stopPropagation();if(activeWhich===which){closePopup();return}closePopup();activeWhich=which;activeTrigger=trigger;renderYearGrid();popup.classList.add('open');trigger.classList.add('open')});
  const clr=wrap.querySelector('[data-role=ypick-clear]');
  if(clr)clr.addEventListener('click',e=>{e.stopPropagation();if(which==='from')pend.ymin='';else pend.ymax='';const sp=trigger.querySelector('span');sp.textContent=which==='from'?'From...':'To...';sp.classList.add('ph');clr.remove();updBadge();if(activeWhich===which)renderYearGrid()});
  trigger.addEventListener('click',e=>{
   const c=e.target.closest('[data-role=ypick-clear]');if(!c)return;
   e.stopPropagation();
   if(which==='from')pend.ymin='';else pend.ymax='';
   const sp=trigger.querySelector('span');sp.textContent=which==='from'?'From...':'To...';sp.classList.add('ph');
   c.remove();updBadge();if(activeWhich===which)renderYearGrid();
  });
 });
 popup.addEventListener('click',e=>{
  e.stopPropagation();
  const btn=e.target.closest('[data-role=yp-dec-prev]');if(btn){decades[activeWhich]=Math.max(1900,decades[activeWhich]-12);renderYearGrid();return}
  const btn2=e.target.closest('[data-role=yp-dec-next]');if(btn2){decades[activeWhich]=Math.min(2088,decades[activeWhich]+12);renderYearGrid();return}
  const yr=e.target.closest('[data-year]');if(yr&&!yr.disabled){
   const val=yr.dataset.year;
   if(activeWhich==='from')pend.ymin=val;else pend.ymax=val;
   const sp=activeTrigger.querySelector('span');sp.textContent=val;sp.classList.remove('ph');
   if(!activeTrigger.querySelector('[data-role=ypick-clear]')){const c=document.createElement('button');c.type='button';c.className='ypick-clear';c.dataset.role='ypick-clear';c.title='Clear';c.textContent='✕';activeTrigger.appendChild(c)}
   closePopup();updBadge();
  }
 });
 if(_ypDocClose)document.removeEventListener('click',_ypDocClose);
 _ypDocClose=closePopup;
 document.addEventListener('click',closePopup);
}
function pageHeadHTML(tab){
 const cfg=TABS[tab];
 return `<div class="page-head"><div><div class="crumb mono">${cfg.crumb}</div><h1><span class="hicon"><i data-lucide="${cfg.icon}"></i></span>${cfg.title}</h1></div></div>`;
}
function continueHTML(tab){
  if(!Sync.on||(tab!=='movies'&&tab!=='scenes'))return '';
  const kind=tab==='movies'?'movie':'scene';
  const filteredIds=new Set(filtered(tab).map(x=>x.id));
  const cwLimit=Math.max(1,settings.cwLimit||4);
  const items=(tab==='movies'?DB.movies:DB.scenes)
   .filter(it=>filteredIds.has(it.id))
   .map(it=>({it,p:Positions.progress(kind,it.id)}))
    // any real watch counts (positions only exist after ~3s of playback) —
    // the old 2% floor hid short watches of long titles entirely; near-complete
    // items stay (the player clears the position at the real end)
    .filter(x=>x.p>0&&x.p<0.995)
   // most-recently-watched first (NOT "furthest along") so the row holds the
   // items you were last watching; items with no recency fall back to progress
   .sort((a,b)=>{
    const da=Positions.age(kind+':'+a.it.id),db=Positions.age(kind+':'+b.it.id);
    if(da!==db)return da-db;
    return b.p-a.p;
   })
   .slice(0,cwLimit);
  if(!items.length)return '';
  const cw=T[tab].cw;
  return `<div id="cw-section"><div class="seclabel mono">Continue Watching</div>
   <div class="grid" style="--cw:${cw}px;margin-bottom:6px">${items.map(x=>{
    const c=kind==='movie'?movieCard(x.it):sceneCard(x.it);
    return c.replace('<span class="badge">',`<span class="prog" style="width:${Math.round(x.p*100)}%"></span><span class="badge">`);
   }).join('')}</div></div>`;
}
function renderTab(tab){
 if(tab==='settings')return renderSettings();
 if(tab==='profile')return renderProfile();
 if(tab==='about')return renderAbout();
 const t=T[tab];
 $('#main').innerHTML=`<div class="page">${pageHeadHTML(tab)}${continueHTML(tab)}${toolbarHTML(tab)}${listBodyHTML(tab)}</div>`;
 const q=$('[data-role=q]');q&&q.addEventListener('input',()=>{t.q=q.value;t.page=1;refreshList(tab)});
 $$('[data-role=cw]').forEach(r=>r.addEventListener('input',()=>{t.cw=+r.value;settings.cardWidths=settings.cardWidths||{};settings.cardWidths[state.view.tab]=t.cw;saveSettings();$$('.grid').forEach(g=>g.style.setProperty('--cw',t.cw+'px'))}));
 // Pagination (handled by persistent delegated listener below)
 const pop=$('[data-role=fpop]');
 if(pop){
  // Pending filter state - changes are staged here until Apply is clicked
  const f=T[tab].f;
  let pend,updBadge;
  if(tab==='performers'){
   pend={gender:f.gender,nationalities:new Set(f.nationalities),hairColors:new Set(f.hairColors),ethnicities:new Set(f.ethnicities),boobType:f.boobType,piercings:f.piercings,tattoos:f.tattoos,csMin:f.csMin,csMax:f.csMax,heightMin:f.heightMin,heightMax:f.heightMax,sort:f.sort||'az',ymin:f.csMin,ymax:f.csMax};
   T.performers._pend=pend;
   $$('[data-fk]',pop).forEach(el=>{
    const k=el.dataset.fk,v=el.dataset.fv;
    if(k==='gender')el.classList.toggle('on',pend.gender===v);
    else if(k==='nat'&&v)el.classList.toggle('on',pend.nationalities.has(v));
    else if(k==='hair'&&v)el.classList.toggle('on',pend.hairColors.has(v));
    else if(k==='eth'&&v)el.classList.toggle('on',pend.ethnicities.has(v));
    else if(k==='boobType')el.classList.toggle('on',pend.boobType===v);
    else if(k==='pierc')el.classList.toggle('on',pend.piercings===v);
    else if(k==='tatto')el.classList.toggle('on',pend.tattoos===v);
    else if(k==='sort')el.value=pend.sort||'az';
    else if(k==='heightMin')el.value=pend.heightMin||'';
    else if(k==='heightMax')el.value=pend.heightMax||'';
   });
   updBadge=()=>{
    const n=(pend.gender?1:0)+pend.nationalities.size+pend.hairColors.size+pend.ethnicities.size+(pend.boobType?1:0)+(pend.piercings?1:0)+(pend.tattoos?1:0)+((pend.ymin||pend.ymax)?1:0)+((pend.heightMin||pend.heightMax)?1:0)+(pend.sort!=='az'?1:0);
    const b=$('[data-role=fbadge]');if(b){b.textContent=n;b.style.display=n?'':'none'}
   };
  }else{
   pend={studios:new Set(f.studios),cats:new Set(f.cats),performers:new Set(f.performers),ymin:f.ymin,ymax:f.ymax,sort:f.sort};
   T[tab]._pend=pend;
   $$('[data-fk]',pop).forEach(el=>{
    const k=el.dataset.fk,v=el.dataset.fv;
    if(k==='site'&&v)el.classList.toggle('on',pend.studios.has(v));
    else if(k==='cat'&&v)el.classList.toggle('on',pend.cats.has(v));
    else if(k==='perf'&&v)el.classList.toggle('on',pend.performers.has(v));
    else if(k==='sort')el.value=pend.sort||'new';
   });
   updBadge=()=>{
    const n=pend.studios.size+pend.cats.size+pend.performers.size+(pend.ymin?1:0)+(pend.ymax?1:0)+(pend.sort!=='new'?1:0);
    const b=$('[data-role=fbadge]');if(b){b.textContent=n;b.style.display=n?'':'none'}
   };
  }
  updBadge();
  yearPickerInit(pop,pend,updBadge);
  $$('[data-fk]',pop).forEach(el=>{
   const isBtn=el.tagName==='BUTTON';
   el.addEventListener(isBtn?'click':'change',()=>{
    const k=el.dataset.fk,v=el.dataset.fv||el.value;
    if(tab==='performers'){
     if(k==='gender'){pend.gender=pend.gender===v?'':v;$$('[data-fk=gender]',pop).forEach(x=>x.classList.toggle('on',pend.gender===x.dataset.fv))}
     else if(k==='nat'){pend.nationalities.has(v)?pend.nationalities.delete(v):pend.nationalities.add(v);el.classList.toggle('on')}
     else if(k==='hair'){pend.hairColors.has(v)?pend.hairColors.delete(v):pend.hairColors.add(v);el.classList.toggle('on')}
     else if(k==='eth'){pend.ethnicities.has(v)?pend.ethnicities.delete(v):pend.ethnicities.add(v);el.classList.toggle('on')}
     else if(k==='boobType'){pend.boobType=pend.boobType===v?'':v;$$('[data-fk=boobType]',pop).forEach(x=>x.classList.toggle('on',pend.boobType===x.dataset.fv))}
     else if(k==='pierc'){pend.piercings=pend.piercings===v?'':v;el.classList.toggle('on')}
     else if(k==='tatto'){pend.tattoos=pend.tattoos===v?'':v;el.classList.toggle('on')}
     else if(k==='heightMin'){pend.heightMin=v}
     else if(k==='heightMax'){pend.heightMax=v}
     else if(k==='sort'){pend.sort=v}
    }else{
     if(k==='site'){pend.studios.has(v)?pend.studios.delete(v):pend.studios.add(v);el.classList.toggle('on')}
     else if(k==='cat'){pend.cats.has(v)?pend.cats.delete(v):pend.cats.add(v);el.classList.toggle('on')}
     else if(k==='perf'){pend.performers.has(v)?pend.performers.delete(v):pend.performers.add(v);el.classList.toggle('on')}
     else if(k==='sort'){pend.sort=v}
    }
    updBadge();
   });
  });
  $$('[data-role=more]',pop).forEach(btn=>{
   btn.addEventListener('click',()=>{
    const group=btn.closest('.fgroup');
    const overflow=group?group.querySelector('.filt-overflow'):null;
    if(!overflow)return;
    overflow.hidden=false;
    btn.style.display='none';
   });
  });
  $$('[data-role=less]',pop).forEach(btn=>{
   btn.addEventListener('click',()=>{
    const group=btn.closest('.fgroup');
    const overflow=group?group.querySelector('.filt-overflow'):null;
    const moreBtn=group?group.querySelector('[data-role=more]'):null;
    if(overflow)overflow.hidden=true;
    if(moreBtn)moreBtn.style.display='';
   });
  });
 }
}
function renderProfile(){
 const pt=state.profileTab;
 const subTabs=[{id:'favorites',label:'Favorites',icon:'heart'},{id:'playlists',label:'Playlists',icon:'list-music'},{id:'info',label:'Profile',icon:'user'}];
 const tabBtns=subTabs.map(s=>`<button class="btn sm ${pt===s.id?'primary':''}" data-action="profile-tab" data-tab="${s.id}"><i data-lucide="${s.icon}"></i>${s.label}</button>`).join('');
 let body='';
 if(pt==='favorites'){
  const fm=DB.movies.filter(m=>m.fav),fs=DB.scenes.filter(s=>s.fav);
  if(!fm.length&&!fs.length){
   body=`<div class="empty"><i data-lucide="heart"></i><span>No Favorites Yet.</span><span class="mono">Tap The Heart On Any Movie Or Scene</span></div>`;
  }else{
   body=`${fm.length?`<div class="seclabel mono" style="margin-top:0">Movies - ${fm.length}</div><div class="grid" style="--cw:200px">${fm.map(movieCard).join('')}</div>`:''}
    ${fs.length?`<div class="seclabel mono"${fm.length?'':' style="margin-top:0"'}>Scenes - ${fs.length}</div><div class="grid" style="--cw:250px">${fs.map(sceneCard).join('')}</div>`:''}`;
  }
 }else if(pt==='playlists'){
  const pls=settings.playlists||[];
  if(!pls.length){
   body=`<div class="empty"><i data-lucide="list-music"></i><span>No Playlists Yet.</span><span class="mono">Create Your First Playlist Below</span></div>`;
  }else{
   body=pls.map(pl=>{
    const movies=(pl.movieIds||[]).map(id=>DB.movies.find(m=>m.id===id)).filter(Boolean);
    const scenes=(pl.sceneIds||[]).map(id=>DB.scenes.find(s=>s.id===id)).filter(Boolean);
    const total=movies.length+scenes.length;
    return `<div class="seclabel mono" style="margin-top:14px;display:flex;align-items:center;gap:8px"><i data-lucide="list-music"></i>${esc(pl.name)} <span class="dim">(${total} Item${total===1?'':'s'})</span><span class="push"></span><button class="tx" data-action="pl-rename" data-plid="${pl.id}" title="Rename"><i data-lucide="pencil"></i></button><button class="tx" data-action="pl-delete" data-plid="${pl.id}" title="Delete"><i data-lucide="trash-2"></i></button></div>
     ${movies.length?`<div class="grid" style="--cw:180px;margin-top:8px">${movies.map(m=>movieCard(m)).join('')}</div>`:''}
     ${scenes.length?`<div class="grid" style="--cw:220px;margin-top:8px">${scenes.map(s=>sceneCard(s)).join('')}</div>`:''}
     ${!total?'<div class="dim" style="font-size:12px;padding:8px 0">Empty Playlist — Add Items From Detail Pages</div>':''}`;
   }).join('');
  }
  body+=`<div style="margin-top:16px"><button class="btn" data-action="pl-create"><i data-lucide="plus"></i>New Playlist</button></div>`;
 }else if(pt==='info'){
  const totalMovies=DB.movies.length,totalScenes=DB.scenes.length,totalPerfs=DB.performers.length,totalStudios=DB.studios.length;
  const favMovies=DB.movies.filter(m=>m.fav).length,favScenes=DB.scenes.filter(s=>s.fav).length;
  const pls=(settings.playlists||[]).length;
  body=`<div class="dgrid" style="grid-template-columns:repeat(2,1fr)">
    <div><div class="mono"><i data-lucide="film"></i> Movies</div><div class="dv">${totalMovies}</div></div>
    <div><div class="mono"><i data-lucide="clapperboard"></i> Scenes</div><div class="dv">${totalScenes}</div></div>
    <div><div class="mono"><i data-lucide="users"></i> Performers</div><div class="dv">${totalPerfs}</div></div>
    <div><div class="mono"><i data-lucide="building-2"></i> Studios</div><div class="dv">${totalStudios}</div></div>
    <div><div class="mono"><i data-lucide="heart"></i> Favorites</div><div class="dv">${favMovies+favScenes}</div></div>
    <div><div class="mono"><i data-lucide="list-music"></i> Playlists</div><div class="dv">${pls}</div></div>
   </div>
   <div class="seclabel mono" style="margin-top:18px">Quick Stats</div>
   <div class="dgrid" style="grid-template-columns:repeat(2,1fr)">
    <div><div class="mono"><i data-lucide="heart"></i> Fav Movies</div><div class="dv">${favMovies}</div></div>
    <div><div class="mono"><i data-lucide="heart"></i> Fav Scenes</div><div class="dv">${favScenes}</div></div>
    <div><div class="mono"><i data-lucide="tag"></i> Categories</div><div class="dv">${DB.categories.length}</div></div>
    <div><div class="mono"><i data-lucide="clock"></i> Positions</div><div class="dv">${Object.keys(Positions.all||{}).length}</div></div>
   </div>`;
 }
 $('#main').innerHTML=`<div class="page">${pageHeadHTML('profile')}
  <div style="display:flex;gap:6px;margin-bottom:18px;flex-wrap:wrap">${tabBtns}</div>
  ${body}
 </div>`;
}
function refreshList(tab){
 // Update Continue Watching
 const cwOld=$('#cw-section');
 const cwNew=continueHTML(tab);
 if(cwOld){if(cwNew)cwOld.outerHTML=cwNew;else cwOld.remove()}
 else if(cwNew){const page=$('.page');if(page)page.insertAdjacentHTML('afterbegin',cwNew)}
 // Update bulk bar in its own slot (kept out of the list replacement so it
 // cannot be duplicated when #list-main is swapped)
 const slot=$('#bulkbar-slot');
 if(slot)slot.innerHTML=bulkBarHTML(tab);
 // Update main list
 const old=$('#list-main');
 const html=listMainHTML(tab);
 if(old)old.outerHTML=html;else $('#main .page').insertAdjacentHTML('beforeend',html);
 icons();
}
