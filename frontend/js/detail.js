"use strict";
/* ===== DETAIL ===== */
function spreadHTML(item,kind){
 if(kind==='scene'){
  const c=[...(item.covers||[])];
  const thumbIdx=item.thumb||0;
  const thumb=c[thumbIdx]||c[0]||'';
  return `<div class="spread ${kind}">${thumb?`<img src="${esc(thumb)}" alt="" style="width:100%">`:`<div class="noimg" style="width:100%">No Image</div>`}</div>`;
 }
 const srcs=playerSrcs(item,kind).filter(Boolean);
 const two=srcs.length===2;
 if(!srcs.length)return `<div class="spread ${kind}"><div class="noimg" style="width:100%">No Image</div></div>`;
 if(!two)return `<div class="spread ${kind} single"><img src="${esc(srcs[0])}" alt="" style="width:100%"></div>`;
 return `<div class="spread ${kind} two"><img src="${esc(srcs[0])}" alt=""><img src="${esc(srcs[1])}" alt=""></div>`;
}
function isEmptyVal(v){
 if(v==null)return true;
 if(typeof v==='object')return false;
 const s=String(v).trim();
 return !s||/^[-_\s]+$/.test(s);
}
const WEIGHT_ICON='<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a4 4 0 0 0-4 4c0 2 2 4 4 7 2-3 4-5 4-7a4 4 0 0 0-4-4z"/><circle cx="12" cy="7" r="1.5" fill="currentColor"/><path d="M6 21h12"/><path d="M8 17v4"/><path d="M16 17v4"/></svg>';
const PIERCINGS_ICON='<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="4" r="2.5"/><circle cx="12" cy="20" r="2.5"/><line x1="12" y1="6.5" x2="12" y2="17.5"/><path d="M7 12c2-2 3-3 5-3s3 1 5 3"/></svg>';
const BOOBS_ICON='<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 123.1 104.65" fill="none" stroke="currentColor" stroke-width="3"><path d="M94.72,40.87c-3.81,0-6.9,3.09-6.9,6.9s3.09,6.9,6.9,6.9c3.81,0,6.9-3.09,6.9-6.9S98.53,40.87,94.72,40.87z M28.38,40.87c3.81,0,6.9,3.09,6.9,6.9s-3.09,6.9-6.9,6.9c-3.81,0-6.9-3.09-6.9-6.9S24.56,40.87,28.38,40.87z M12.1,0.34l0.53,7.99c0.06,0.9,0.13,1.57,0.2,2.13c0.17,1.53,0.21,1.88-1.13,3.95C-1.79,35.26-2.12,51.2,3.68,61.75c3.47,6.31,9.12,10.66,15.46,12.98c0.17,0.06,0.34,0.12,0.52,0.18c0.02,5.05-0.23,10.06-0.81,15c-0.59,5-1.53,9.89-2.91,14.63h3.39c1.44-4.98,2.42-9.07,3.03-14.22c0.56-4.71,0.81-9.52,0.83-14.42c5.17,1.15,10.6,1.02,15.54-0.41c9.43-2.73,17.14-10.16,18.22-22.53l-3.53-0.3c-0.94,10.69-7.57,17.09-15.68,19.45c-5.55,1.61-11.78,1.35-17.4-0.7c-5.58-2.04-10.54-5.85-13.57-11.36c-5.23-9.51-4.77-24.17,7.88-43.71c2.03-3.14,1.97-3.71,1.68-6.26c-0.06-0.53-0.13-1.17-0.18-1.97L12.1,0.34z M28.38,45.59c1.21,0,2.18,0.98,2.18,2.18c0,1.21-0.98,2.18-2.18,2.18c-1.21,0-2.18-0.98-2.18-2.18C26.19,46.57,27.17,45.59,28.38,45.59z M110.99,0.34l-0.53,7.99c-0.06,0.9-0.13,1.57-0.2,2.13c-0.17,1.53-0.21,1.88,1.13,3.95c13.49,20.85,13.82,36.79,8.02,47.34c-3.47,6.31-9.12,10.66-15.46,12.98c-0.17,0.06-0.34,0.12-0.52,0.18c-0.02,5.05,0.23,10.06,0.81,15c0.59,5,1.53,9.89,2.91,14.63h-3.39c-1.44-4.98-2.42-9.07-3.03-14.22c-0.56-4.71-0.81-9.52-0.83-14.42c-5.17,1.15-10.6,1.02-15.54-0.41c-9.43-2.73-17.14-10.16-18.22-22.53l3.53-0.3c0.94,10.69,7.57,17.09,15.68,19.45c5.55,1.61,11.78,1.35,17.4-0.7c5.58-2.04,10.54-5.85,13.57-11.36c5.23-9.51,4.77-24.17-7.88-43.71c-2.03-3.14-1.97-3.71-1.68-6.26c0.06-0.53,0.13-1.17,0.18-1.97L110.99,0.34z M94.72,45.59c-1.21,0-2.18,0.98-2.18,2.18c0,1.21,0.98,2.18,2.18,2.18c1.21,0,2.18-0.98,2.18-2.18C96.91,46.57,95.93,45.59,94.72,45.59z"/></svg>';
const INFO_ICONS={Duration:'clock',Director:'megaphone','Release Year':'calendar','Release Date':'calendar',Studio:'building',Scenes:'clapperboard',Movie:'film',Gender:'user',Born:'cake',Ethnicity:'globe',Nationality:'flag',Hair:'scissors',Eyes:'eye',Height:'ruler',Weight:WEIGHT_ICON,'Career Start':'rocket',Aliases:'at-sign',Tattoos:'pen-tool',Measurements:'move',Boobs:BOOBS_ICON,Piercings:PIERCINGS_ICON,Social:'share-2'};
function infoGrid(kind,item){
  const rows=[];
  if(kind==='movie'||kind==='scene'){
   const st=DB.studios.find(s=>s.id===(kind==='movie'?item.studioId:item.siteId));
   rows.push(['Duration',item.durationMin?fmtDur(item.durationMin):''],['Director',item.director||'']);
   rows.push(kind==='movie'?['Release Year',item.year||'']:['Release Date',item.date?fmtDate(item.date):'']);
   rows.push(['Studio',st?.name||'']);
   if(kind==='movie')rows.push(['Scenes',item.scenes||'']);
   else{const mv=item.movieId?DB.movies.find(m=>m.id===item.movieId):null;if(mv)rows.push(['Movie',{kind:'movie',id:mv.id,label:mv.title}])}
   const filtered=rows.filter(r=>!isEmptyVal(r[1]));
   return `<div class="dgrid">${filtered.map(r=>{const ic=INFO_ICONS[r[0]];return `<div><div class="mono">${ic?`<i data-lucide="${ic}"></i> `:''}${r[0]}</div><div class="dv">${r[1]&&typeof r[1]==='object'?`<button class="peep" data-action="open" data-kind="${r[1].kind}" data-id="${r[1].id}">${esc(r[1].label)}<i data-lucide="arrow-up-right"></i></button>`:esc(String(r[1]))}</div></div>`}).join('')}</div>`;
  }
 const male=item.gender==='m';
 rows.push(['Gender',male?'Male':'Female'],['Born',item.birth?fmtDate(item.birth)+(ageOf(item.birth)!=null?` · ${ageOf(item.birth)} yrs`:''):''],['Ethnicity',item.ethnicity||''],['Nationality',item.nationality||''],['Hair',item.hair||''],['Eyes',item.eyes||''],['Height',item.height?ftIn(item.height)+' ('+item.height+' cm)':''],['Weight',item.weight?item.weight+' kg':''],['Career Start',item.careerStart||''],['Aliases',item.aliases||''],['Tattoos',item.tattoos||'']);
 if(!male)rows.splice(8,0,['Measurements',item.measurements||''],['Boobs',item.boobs||''],['Piercings',item.piercings||'']);
 const filtered=rows.filter(r=>!isEmptyVal(r[1]));
 const socials=[];
 if(item.twitter)socials.push({href:'https://x.com/'+item.twitter.replace(/^@/,''),icon:'twitter',label:'X'});
 if(item.instagram)socials.push({href:'https://instagram.com/'+item.instagram.replace(/^@/,''),icon:'instagram',label:'Instagram'});
 if(item.onlyfans)socials.push({href:item.onlyfans.startsWith('http')?item.onlyfans:'https://onlyfans.com/'+item.onlyfans.replace(/^@/,''),icon:'onlyfans',label:'OnlyFans'});
 const ofIcon='<svg fill="currentColor" role="img" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" width="16" height="16"><title>OnlyFans</title><path d="M24 4.003h-4.015c-3.45 0-5.3.197-6.748 1.957a7.996 7.996 0 1 0 2.103 9.211c3.182-.231 5.39-2.134 6.085-5.173 0 0-2.399.585-4.43 0 4.018-.777 6.333-3.037 7.005-5.995zM5.61 11.999A2.391 2.391 0 0 1 9.28 9.97a2.966 2.966 0 0 1 2.998-2.528h.008c-.92 1.778-1.407 3.352-1.998 5.263A2.392 2.392 0 0 1 5.61 12Zm2.386-7.996a7.996 7.996 0 1 0 7.996 7.996 7.996 7.996 0 0 0-7.996-7.996Zm0 10.394A2.399 2.399 0 1 1 10.395 12a2.396 2.396 0 0 1-2.399 2.398Z"/></svg>';
 const socialHTML='<span style="display:inline-flex;gap:6px">'+socials.map(s=>`<a href="${esc(s.href)}" target="_blank" rel="noopener" class="btn icon" title="${esc(s.label)}" style="color:var(--accent);border-color:var(--line2)">${s.icon==='onlyfans'?ofIcon:`<i data-lucide="${s.icon}"></i>`}</a>`).join('')+'</span>';
 if(socials.length){filtered.push(['Social',socialHTML]);}
 const _infoClamp=(label,val)=>{
  if(typeof val!=='string'||val.length<60)return `<div class="dv">${esc(val)}</div>`;
  const key=label+':'+item.id;const exp=!!infoExpand[key];
  return `<div class="dv ${exp?'':'clamped'}" data-info-key="${esc(key)}">${esc(val)}</div><button type="button" class="info-more" data-action="${exp?'info-collapse':'info-expand'}" data-info-key="${esc(key)}">${exp?'Show Less':'Show More'}</button>`;
 };
 return `<div class="dgrid">${filtered.map(r=>{const ic=INFO_ICONS[r[0]];const isHTML=r[0]==='Social';const iconHTML=ic?(ic.startsWith('<svg')?ic:`<i data-lucide="${ic}"></i> `):'';return `<div><div class="mono">${iconHTML}${r[0]}</div>${typeof r[1]==='string'&&!isHTML?_infoClamp(r[0],r[1]):`<div class="dv">${r[1]}</div>`}</div>`}).join('')}</div>`;}
function descHTML(kind,item,mstyle){
 const text=item.desc||'';
 if(isEmptyVal(text))return '';
 const long=text.length>260;
 const exp=!!descExpand[kind+':'+item.id];
 const cls=long&&!exp?'ddesc clamped':'ddesc';
 return `<p class="${cls}" style="${mstyle}">${esc(text)}</p>`+
  (long?`<button type="button" class="desc-more" data-action="${exp?'desc-collapse':'desc-expand'}">${exp?'Show Less':'Show More'}</button>`:'');
}
function castChips(item,kind){
 const all=ensureArr(item.actorIds).map(id=>DB.performers.find(x=>x.id===id)).filter(Boolean);
 const lim=Math.max(1,settings.catLimit||10),exp=!!castExpand[kind+':'+item.id];
 const shown=exp?all:all.slice(0,lim);
 const chips=shown.map(p=>`<button class="peep" data-action="open" data-kind="performer" data-id="${p.id}">${p.photo?`<img src="${esc(p.photo)}" alt="">`:''}${esc(p.name)}<i data-lucide="arrow-up-right"></i></button>`).join('');
 const more=all.length>lim?`<button type="button" class="chip" data-action="${exp?'cast-collapse':'cast-expand'}">${exp?'Show Less':'+'+(all.length-lim)+' More'}</button>`:'';
 return chips+more;
}
function catChipsHTML(kind,item){
 const all=ensureArr(item.categoryIds).map(cid=>DB.categories.find(c=>c.id===cid)).filter(Boolean);
 const lim=Math.max(1,settings.catLimit||10),exp=!!catExpand[kind+':'+item.id];
 const shown=exp?all:all.slice(0,lim);
 if(!all.length)return '';
 return shown.map(c=>`<button class="chip on" data-action="open" data-kind="category" data-id="${c.id}" style="cursor:pointer">${esc(c.name)}<i data-lucide="arrow-up-right" style="width:11px;height:11px;margin-left:4px"></i></button>`).join('')
  +(all.length>lim?`<button type="button" class="chip" data-action="${exp?'cats-collapse':'cats-expand'}">${exp?'Show Less':'+'+(all.length-lim)+' More'}</button>`:'');
}

/* ===== detail-page catalogue paging =====
   A studio/category page used to render every movie and scene that belongs to
   it in one page. dSec() pages any catalogue section the way the tab lists do —
   same .pager markup, same settings.perPage[tab] page size — and detailGoto()
   re-renders just that one section when its page changes. Sections are
   registered for the detail page that is on screen only. */
const detailPg={},detailSecs={};
function dPageState(key){
 const s=detailSecs[key];if(!s)return null;
 const items=dMatch(s.items);
 const pp=(settings.perPage&&settings.perPage[s.tab])||24;
 const pages=Math.max(1,Math.ceil(items.length/pp));
 let p=detailPg[key]||1;if(p>pages)p=pages;if(p<1)p=1;detailPg[key]=p;
 return {s:s,items:items,pp:pp,pages:pages,p:p,show:items.slice((p-1)*pp,p*pp)};
}
function dSecHTML(key){
 const st=dPageState(key);if(!st)return'';
 const s=st.s,items=st.items,pages=st.pages,p=st.p,show=st.show,pp=st.pp;
 const body=show.length
  ?detailUI.view==='list'
   ?`<div class="rows">${show.map(x=>rowFor(s.tab,x)).join('')}</div>`
   :`<div class="grid" style="--cw:${detailUI.cw}px">${show.map(s.cardFn).join('')}</div>`
  :`<div class="empty" style="margin-top:10px"><i data-lucide="inbox"></i><span>No Matches.</span></div>`;
 return `<div data-dsec="${esc(key)}"${bulkSel.active?' class="bulk-on"':''}>${body}`
  +(items.length>pp?pagerHTML({page:p,pages,total:items.length,pp,numAttr:'data-dpage',key}):'')+`</div>`;
}
function dSec(key,items,cardFn,tab){
 detailSecs[key]={items:items,cardFn:cardFn,tab:tab};
 detailPg[key]=1;   // a fresh render starts at page 1
 return dSecHTML(key);
}
function detailGoto(key,page){
 if(!detailSecs[key])return;
 detailPg[key]=page;
 const el=$$('[data-dsec]').find(x=>x.dataset.dsec===key);
 if(el){
  el.outerHTML=dSecHTML(key);
  const fresh=$$('[data-dsec]').find(x=>x.dataset.dsec===key);
  if(fresh)dEnsureChecks(fresh);
  icons();
 }
 const main=$('#main');
 if(main&&main.scrollTo)main.scrollTo({top:0,behavior:'smooth'});
}
function detailRefreshSections(resetPage){
 if(resetPage)for(const k in detailSecs)detailPg[k]=1;
 $$('[data-dsec]').forEach(el=>{if(detailSecs[el.dataset.dsec])el.outerHTML=dSecHTML(el.dataset.dsec)});
 $$('[data-dsec]').forEach(el=>dEnsureChecks(el));
 icons();
}
/* The card renderer only emits its .bulk-chk in tab views, so make sure every
   card in a catalogue section has one and gate it with .bulk-on on the section.
   Switching bulk mode is then a class toggle — no re-render, so the posters do
   not reload and the grid does not jump (the reason updateBulkUI() exists). */
function dEnsureChecks(root){
 if(!root)return;
 $$('.card, .row',root).forEach(card=>{
  if(card.querySelector('[data-bulk-id]'))return;
  const host=card.dataset.id?card:(card.querySelector('[data-action="open"]')||card.closest('[data-action="open"]')||card);
  const id=host.dataset.id;if(!id)return;
  const chk=document.createElement('div');
  chk.className='bulk-chk';chk.dataset.bulkId=id;
  card.insertBefore(chk,card.firstChild);
 });
}

/* ===== studio catalogue toolbar (search · filter · view · size · add) =====
   The list toolbar's counterpart on the studio/category page, scoped to that
   studio's catalogue. The filter panel is the scenes/movies tab filter
   (filterPopHTML) minus its Studios group — every item on this page already
   belongs to one studio. Everything the tab-list handlers would see is
   namespaced (data-daction / data-drole / data-dfk): those handlers in
   events.js act on state.view.tab and call renderTab(state.view.tab), which on
   a detail page is renderTab(undefined) — a crash. The only markup shared with
   them is data-action="filter" + data-role="fpop", which just toggles a class.
   The year picker is reused as-is: yearPickerInit() wires its own listeners
   inside the popover and only touches the `pend` object it is handed. */
const detailUI={q:'',view:'grid',cw:250,f:null,_pend:null,raw:{movie:[],scene:[]},kinds:new Set()};
function dFilterState(){return{cats:new Set(),performers:new Set(),ymin:'',ymax:'',sort:'new'}}
function dFilterCount(f){return f.cats.size+f.performers.size+((f.ymin||f.ymax)?1:0)}
function detailUIReset(raw,kinds){
 detailUI.q='';detailUI.view='grid';
 detailUI.cw=(settings.cardWidths&&settings.cardWidths.detail)||250;
 detailUI.f=dFilterState();detailUI._pend=dFilterState();
 detailUI.raw=raw||{movie:[],scene:[]};detailUI.kinds=kinds||new Set();
}
function dMatch(items){
 const f=detailUI.f,q=detailUI.q.trim().toLowerCase();
 const out=items.filter(it=>{
  if(q&&![it.title,it.director].some(v=>String(v||'').toLowerCase().includes(q)))return false;
  if(f.cats.size&&!ensureArr(it.categoryIds).some(id=>f.cats.has(id)))return false;
  if(f.performers.size&&!ensureArr(it.actorIds).some(id=>f.performers.has(id)))return false;
  const y=parseInt(String(it.year||it.date||'').slice(0,4),10)||0;
  if(f.ymin&&(!y||y<+f.ymin))return false;
  if(f.ymax&&(!y||y>+f.ymax))return false;
  return true;
 });
 if(f.sort==='old')out.reverse();
 else if(f.sort==='az')out.sort((a,b)=>String(a.title||'').localeCompare(String(b.title||'')));
 else if(f.sort==='long')out.sort((a,b)=>(b.durationMin||0)-(a.durationMin||0));
 return out;
}
function dYPick(which,val){
 return `<div class="ypick-wrap" data-role="ypick" data-which="${which}"><div class="ypick-input" data-role="ypick-trigger"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg><span${val?'':' class="ph"'}>${val||(which==='from'?'From...':'To...')}</span>${val?'<button type="button" class="ypick-clear" data-role="ypick-clear" title="Clear">✕</button>':''}</div></div>`;
}
function dFilterPopHTML(){
 const p=detailUI._pend,all=detailUI.raw.movie.concat(detailUI.raw.scene);
 const count=(kind,id)=>all.filter(x=>ensureArr(kind==='cat'?x.categoryIds:x.actorIds).includes(id)).length;
 const cats=DB.categories.map(c=>({id:c.id,n:c.name,c:count('cat',c.id)})).filter(x=>x.c>0).sort((a,b)=>b.c-a.c||a.n.localeCompare(b.n));
 const perfs=DB.performers.map(x=>({id:x.id,n:x.name,photo:x.photo||'',c:count('perf',x.id)})).filter(x=>x.c>0).sort((a,b)=>b.c-a.c||a.n.localeCompare(b.n));
 const catChip=c=>`<button type="button" class="chip ${p.cats.has(c.id)?'on':''}" data-dfk="cat" data-dfv="${c.id}">${esc(c.n)}</button>`;
 const perfChip=x=>`<button type="button" class="peep ${p.performers.has(x.id)?'on':''}" data-dfk="perf" data-dfv="${x.id}">${x.photo?`<img src="${esc(x.photo)}" alt="">`:''}${esc(x.n)}</button>`;
 // same cap + "+N More" / "Show Less" overflow as filterPopHTML's chipBlock
 const lim=Math.max(1,Math.min(settings.catLimit||10,8));
 const chipBlock=(list,render)=>{
  const shown=list.slice(0,lim),hidden=list.slice(lim);
  const moreBtn=hidden.length?`<button type="button" class="chip" data-drole="more" data-more-label="+${hidden.length} More">+${hidden.length} More</button>`:'';
  const main=shown.map(render).join('')+moreBtn;
  const overflow=hidden.length?`<div class="filt-overflow" hidden>${hidden.map(render).join('')}<button type="button" class="chip" data-drole="less">Show Less</button></div>`:'';
  return {main:main,overflow:overflow};
 };
 const catB=chipBlock(cats,catChip),perfB=chipBlock(perfs,perfChip);
 return `<div class="fpop" data-role="fpop">
  <div class="fgroup"><div class="flab">${cats.length>12?'Categories · Popular First':'Categories'}</div><div class="chiprow">${catB.main}</div>${catB.overflow}</div>
  <div class="fgroup"><div class="flab">${perfs.length>12?'Performers · Popular First':'Performers'}</div><div class="cast">${perfB.main}</div>${perfB.overflow}</div>
  <div class="fgroup"><div class="flab">Year Range</div><div class="frow" style="max-width:340px;gap:10px">${dYPick('from',p.ymin)}${dYPick('to',p.ymax)}</div><div class="ypick-popup" data-role="ypick-popup"></div></div>
  <div class="fgroup"><div class="flab">Sort</div><select class="field" data-dfk="sort"><option value="new" ${p.sort==='new'?'selected':''}>Newest First</option><option value="old" ${p.sort==='old'?'selected':''}>Oldest First</option><option value="az" ${p.sort==='az'?'selected':''}>Title A-Z</option><option value="long" ${p.sort==='long'?'selected':''}>Longest</option></select></div>
  <div class="fpop-foot"><button class="btn ghost sm" data-daction="filter-clear">Clear All</button><button class="btn primary" data-daction="filter-apply"><i data-lucide="check"></i>Apply</button></div>
 </div>`;
}
function dToolbarHTML(){
 const n=dFilterCount(detailUI._pend);
 const add=[...detailUI.kinds].map(k=>`<button class="btn primary" data-daction="add" data-dkind="${k}"><i data-lucide="plus"></i>Add ${k==='movie'?'Movie':'Scene'}</button>`).join('')
  ||`<button class="btn primary" data-daction="add" data-dkind="scene"><i data-lucide="plus"></i>Add Scene</button>`;
 return `<div class="toolbar">
  <div class="searchbox"><i data-lucide="search"></i><input placeholder="Search This Studio..." value="${esc(detailUI.q||'')}" data-drole="q"></div>
  <span class="fwrap2"><button class="btn" data-action="filter"><i data-lucide="sliders-horizontal"></i>Filter<span class="fbadge" data-drole="fbadge" ${n?'':'style="display:none"'}>${n}</span></button></span>
  <div class="sp"><div id="bulkbar-slot" data-drole="bulkbar">${dBulkBarHTML()}</div></div>
  <div class="seg"><button data-daction="setview" data-dv="grid" class="${detailUI.view==='grid'?'on':''}" title="Grid"><i data-lucide="layout-grid"></i></button><button data-daction="setview" data-dv="list" class="${detailUI.view==='list'?'on':''}" title="List"><i data-lucide="list"></i></button><button data-daction="dbulk-toggle" class="${bulkSel.active?'on':''}" title="Select Multiple"><i data-lucide="square-check"></i></button></div>
  ${detailUI.view==='grid'?`<span class="sizewrap"><i data-lucide="scaling"></i><input type="range" min="150" max="340" step="10" value="${detailUI.cw}" data-drole="cw"></span>`:''}
  ${add}
 </div>${dFilterPopHTML()}`;
}
function dInitPicker(){const pop=$('[data-role=fpop]');if(pop&&typeof yearPickerInit==='function')yearPickerInit(pop,detailUI._pend,dUpdateBadge)}
function detailRefreshToolbar(){const el=$('[data-dtoolbar]');if(!el)return;el.innerHTML=dToolbarHTML();dInitPicker();icons()}
function dUpdateBadge(){
 const b=$('[data-drole=fbadge]');if(!b)return;
 const n=dFilterCount(detailUI._pend);
 b.textContent=n;b.style.display=n?'':'none';
}
/* ===== bulk selection (detail page) =====
   Mirrors the tab lists' bulk bar, but namespaced: the tab handlers for
   bulk-fav / -select-all / -clear / -delete all call renderTab(state.view.tab)
   and filtered(state.view.tab), which on a detail page is renderTab(undefined).
   Select-all works on the *filtered* current page of every catalogue section,
   so the search and the filters apply to bulk selection too. */
function dBulkBarHTML(){
 if(!bulkSel.active)return '';
 const n=bulkSel.selected.size;
 const dis=n?'':' disabled';
 const hide=n?'':' style="visibility:hidden" aria-hidden="true"';
 return `<div class="bulk-bar"${hide}><span class="bulk-count btn icon" title="${n} Selected"><span class="bc-n">${n}</span></span><button class="btn icon" data-daction="dbulk-fav"${dis} title="Toggle Favorite"><i data-lucide="heart"></i></button><button class="btn icon" data-daction="dbulk-select-all" title="Select All"><i data-lucide="check-square"></i></button><button class="btn icon" data-daction="dbulk-clear" title="Clear"><i data-lucide="x-square"></i></button><button class="btn icon danger" data-daction="dbulk-delete"${dis} title="Delete"><i data-lucide="trash-2"></i></button></div>`;
}
function dUpdateBulkUI(){
 $$('[data-bulk-id]').forEach(chk=>{
  const on=bulkSel.selected.has(chk.dataset.bulkId);
  chk.classList.toggle('on',on);
  const host=chk.closest('[data-action="open"]');
  if(host)host.toggleAttribute('data-bulk-sel',on);
 });
 const slot=$('[data-drole=bulkbar]');
 if(slot){slot.innerHTML=dBulkBarHTML();icons()}
}
function dFindItem(id){
 for(const kind of ['movies','scenes']){
  const arr=DB[kind],i=arr.findIndex(x=>x.id===id);
  if(i>-1)return{kind:kind,arr:arr,i:i,item:arr[i]};
 }
 return null;
}
function detailToolbarClick(e){
 const target=e.target;
 if(!target||!target.closest)return;
 const chk=target.closest('[data-bulk-id]');
 if(chk&&$('[data-dtoolbar]')){
  // stop the card's [data-action="open"] from navigating away (boot.js's own
  // bulk listener bails out on detail pages, so nothing else stops it here)
  e.preventDefault();e.stopPropagation();
  const id=chk.dataset.bulkId;
  if(bulkSel.selected.has(id))bulkSel.selected.delete(id);else bulkSel.selected.add(id);
  dUpdateBulkUI();return;
 }
 const chip=target.closest('button[data-dfk]');
 if(chip&&chip.closest('[data-dtoolbar]')){
  const p=detailUI._pend,fv=chip.dataset.dfv;
  const map={cat:'cats',perf:'performers'};
  const set=p[map[chip.dataset.dfk]];if(!set)return;
  if(set.has(fv))set.delete(fv);else set.add(fv);
  chip.classList.toggle('on');dUpdateBadge();return;
 }
 const roleBtn=target.closest('[data-drole]');
 if(roleBtn&&roleBtn.closest('[data-dtoolbar]')){
  const role=roleBtn.dataset.drole;
  if(role==='more'||role==='less'){
   // reveal / hide the .filt-overflow that filterPopHTML's chipBlock hides
   const grp=roleBtn.closest('.fgroup'),ov=grp&&grp.querySelector('.filt-overflow');
   if(ov){
    const open=role==='more';
    ov.hidden=!open;
    const mb=grp.querySelector('[data-drole=more]');
    if(mb)mb.style.display=open?'none':'';
   }
   return;
  }
 }
 const a=target.closest('[data-daction]');
 if(!a||!a.closest('[data-dtoolbar]'))return;
 const act=a.dataset.daction;
 if(act==='setview'){
  detailUI.view=a.dataset.dv;
  detailRefreshToolbar();detailRefreshSections(false);
 }
 else if(act==='add'){
  if(a.dataset.dkind==='movie')mediaForm('movie',null);else mediaForm('scene',null);
 }
 else if(act==='filter-apply'){
  const p=detailUI._pend;
  detailUI.f={cats:new Set(p.cats),performers:new Set(p.performers),ymin:p.ymin,ymax:p.ymax,sort:p.sort};
  detailRefreshToolbar();detailRefreshSections(true);
  toast('Filters Applied','filter');
 }
 else if(act==='filter-clear'){
  detailUI._pend=dFilterState();detailUI.f=dFilterState();
  detailRefreshToolbar();detailRefreshSections(true);
 }
 else if(act==='dbulk-toggle'){
  bulkSel.active=!bulkSel.active;
  if(!bulkSel.active)bulkSel.selected.clear();
  // in place: no section re-render, so the posters don't reload / the grid
  // doesn't jump (same as the tabs' updateBulkUI path)
  $$('[data-dsec]').forEach(el=>el.classList.toggle('bulk-on',bulkSel.active));
  a.classList.toggle('on',bulkSel.active);
  dUpdateBulkUI();
 }
 else if(act==='dbulk-select-all'){
  // only the sections actually on screen — detailSecs can still hold entries
  // from a previous render
  $$('[data-dsec]').forEach(el=>{const st=dPageState(el.dataset.dsec);if(st)st.show.forEach(x=>bulkSel.selected.add(x.id))});
  dUpdateBulkUI();
 }
 else if(act==='dbulk-clear'){
  bulkSel.selected.clear();dUpdateBulkUI();
 }
 else if(act==='dbulk-fav'){
  const ids=[...bulkSel.selected];
  ids.forEach(id=>{const rec=dFindItem(id);if(rec){rec.item.fav=!rec.item.fav;Sync.push(rec.kind,'update',rec.item)}});
  bulkSel.selected.clear();bulkSel.active=false;
  toast(`${ids.length} Item${ids.length===1?'':'s'} Updated`,'heart');
  detailRefreshSections(true);detailRefreshToolbar();
 }
 else if(act==='dbulk-delete'){
  const ids=[...bulkSel.selected];if(!ids.length)return;
  const labels=ids.map(id=>{const rec=dFindItem(id);return rec?(rec.item.title||rec.item.name):''}).filter(Boolean);
  openModal([{title:`Delete ${ids.length} Item${ids.length===1?'':'s'}`,html:()=>`
   <div class="cmsg" style="margin-bottom:12px">Permanently Delete <b>${ids.length}</b> Selected Item${ids.length===1?'':'s'}?${ids.length<=5?'<br>'+labels.map(l=>'&bull; '+esc(l)).join('<br>'):''}<br><span style="color:var(--danger)">This Cannot Be Undone.</span></div>`,
   footer:()=>`<span class="push"></span><button class="btn" data-mclose="1">Cancel</button><button class="btn danger" id="dbulk-del-ok"><i data-lucide="trash-2"></i>Delete ${ids.length}</button>`,
   mount(bl,f){
    $('#dbulk-del-ok',f)?.addEventListener('click',async()=>{
     let ok=0;
     for(const id of ids){
      const rec=dFindItem(id);if(!rec)continue;
      if(Sync.on){try{
       const r=await fetch(`/api/${rec.kind}/${id}`,{method:'DELETE'});
       if(!r.ok)throw new Error('HTTP '+r.status);
      }catch(e){toast('Server Delete Failed - '+(rec.item.title||rec.item.name||id),'alert-triangle');continue}}
      ok++;
      rec.arr.splice(rec.i,1);
      if(rec.kind==='movies')DB.scenes.forEach(s=>{if(s.movieId===id)s.movieId=null});
      Positions.clear(rec.kind.replace(/s$/,''),id);
      ['movie','scene'].forEach(k=>{const r=detailUI.raw[k];const j=r.indexOf(rec.item);if(j>-1)r.splice(j,1)});
     }
     bulkSel.selected.clear();bulkSel.active=false;
     closeModal();if(ok)toast(`${ok} Item${ok===1?'':'s'} Deleted`,'trash-2');
     detailRefreshSections(true);detailRefreshToolbar();
    });
   }}],0,520);
 }
}
function detailToolbarInput(e){
 const el=e.target,role=el.dataset&&el.dataset.drole;
 if(role==='q'){
  detailUI.q=el.value;
  // Debounced: typing used to re-render every catalogue section per keystroke.
  clearTimeout(detailUI._qt);
  detailUI._qt=setTimeout(()=>detailRefreshSections(true),180);
 }
 else if(role==='cw'){
  detailUI.cw=+el.value;
  settings.cardWidths=settings.cardWidths||{};settings.cardWidths.detail=detailUI.cw;saveSettings();
  $$('[data-dsec] .grid').forEach(g=>g.style.setProperty('--cw',detailUI.cw+'px'));
 }
 else if(el.dataset&&el.dataset.dfk==='sort'){
  detailUI._pend.sort=el.value;dUpdateBadge();
 }
}

function renderDetail(kind,id){
 const item=byId(kind,id);
 if(!item){smartBack(kind);return}
 for(const k in detailSecs)delete detailSecs[k];
 for(const k in detailPg)delete detailPg[k];
 detailUIReset();
 if(kind!=='studio'&&kind!=='category'&&bulkSel.active){bulkSel.active=false;bulkSel.selected.clear();}
 const st=DB.studios.find(s=>s.id===(kind==='movie'?item.studioId:item.siteId));
 const backLabel={movie:'Movies',scene:'Scenes',performer:'Performers',studio:'Studios',category:'Categories'}[kind];
 let mediaHTML='',infoHTML='',playerBlock='',extra='',socLinks='',cTag='',actsHTML='';
 if(kind==='movie'||kind==='scene'){
  mediaHTML=spreadHTML(item,kind);
  const minfo=mediaInfo(item,kind);
  const metaBits=kind==='movie'
   ?[item.year,st?.name,fmtDur(item.durationMin),(item.scenes||0)+' Scene'+(item.scenes===1?'':'s')].filter(Boolean)
   :[fmtDate(item.date),st?.name,fmtDur(item.durationMin)].filter(Boolean);
  infoHTML=`<div class="dinfo"><h1>${esc(item.title)}</h1>
   <div class="dmeta mono">${metaBits.map(esc).join(` <span class="dotsep">·</span> `)}</div>
   ${infoGrid(kind,item)}
   <div class="dchips">${catChipsHTML(kind,item)}</div>
   ${descHTML(kind,item,'margin:0 0 16px')?`<div class="flab">Description</div>${descHTML(kind,item,'margin:0 0 16px')}`:''}
   <div class="flab">Cast</div><div class="cast">${castChips(item,kind)||'<span class="dim" style="font-size:12.5px">No Cast Recorded.</span>'}</div>
   <div class="dacts">
    <button class="btn ${item.fav?'fav-on':''}" data-action="toggle-fav" data-kind="${kind}" data-id="${item.id}"><i data-lucide="heart"></i>${item.fav?'In Favorites':'Add To Favorites'}</button>
    <button class="btn" data-action="add-to-pl" data-kind="${kind}" data-id="${item.id}"><i data-lucide="list-plus"></i>Add To Playlist</button>
    <button class="btn" data-action="edit"><i data-lucide="pencil"></i>Edit</button>
    <button class="btn" data-action="fetch-info"><i data-lucide="cloud-download"></i>Update Information</button>
    <button class="btn" data-action="fetch-posters"><i data-lucide="image-plus"></i>${kind==='movie'?'Update Posters':'Update Covers'}</button>
    ${kind==='scene'?`<button class="btn" data-action="fetch-gallery"><i data-lucide="images"></i>Fetch Gallery</button>`:''}
    <button class="btn" data-action="reveal"><i data-lucide="folder-open"></i>Show File Location</button>
    <button class="btn" data-action="share"><i data-lucide="share-2"></i>Share</button>
    <button class="btn danger" data-action="del"><i data-lucide="trash-2"></i>Delete</button>
   </div></div>`;
  const thumbSel=kind==='scene'&&(item.covers||[]).length>1
   ?`<span class="seg textseg"><button class="${(item.thumb||0)===0?'on':''}" data-action="set-thumb" data-i="0">Thumb A</button><button class="${(item.thumb||0)===1?'on':''}" data-action="set-thumb" data-i="1">Thumb B</button></span>`:'';
  playerBlock=`<div class="player-section"><div class="seclabel mono" style="margin-top:0">Watching</div><div id="pwrap">${(Sync.on&&item.filePath)?realPlayerHTML(kind==='movie'?'16/9':'16/9',item,kind):playerHTML(kind==='movie'?'16/9':'16/9')}</div></div>`;
  if(kind==='movie'){
   const linked=DB.scenes.filter(sc=>sc.movieId===item.id);
   extra=linked.length?`<div class="seclabel mono">Scenes In This Movie</div><div class="grid" style="--cw:250px">${linked.map(sceneCard).join('')}</div>`:'';
  }
 }
 else if(kind==='performer'){
  mediaHTML=`<div class="pperf"><img src="${esc(item.photo||'')}" alt=""></div>`;
  infoHTML=`<div class="dinfo"><h1>${esc(item.name)}</h1>
   <div class="dmeta mono">${item.gender==='m'?'Male':'Female'}${item.aliases?' · AKA '+esc(item.aliases):''}</div>
   ${infoGrid('performer',item)}
   <div class="dacts">
    <button class="btn" data-action="edit"><i data-lucide="pencil"></i>Edit</button>
    <button class="btn" data-action="fetch-info"><i data-lucide="cloud-download"></i>Update Information</button>
    <button class="btn" data-action="share"><i data-lucide="share-2"></i>Share</button>
    <button class="btn danger" data-action="del"><i data-lucide="trash-2"></i>Delete</button>
   </div></div>`;
  const movies=DB.movies.filter(m=>ensureArr(m.actorIds).includes(item.id)),scenes=DB.scenes.filter(sc=>ensureArr(sc.actorIds).includes(item.id));
  extra=`${movies.length?`<div class="seclabel mono">Movies With ${esc(item.name)}</div><div class="grid" style="--cw:200px">${movies.map(movieCard).join('')}</div>`:''}
   ${scenes.length?`<div class="seclabel mono">Scenes & Sequences With ${esc(item.name)}</div><div class="grid" style="--cw:250px">${scenes.map(sceneCard).join('')}</div>`:''}
   ${!movies.length&&!scenes.length?`<div class="seclabel mono">Filmography</div><div class="empty"><i data-lucide="clapperboard"></i><span>No Appearances Recorded Yet.</span></div>`:''}`;
 }
 else{
  const kids=kind==='studio'?DB.studios.filter(x=>x.parentId===item.id):[];
  const mother=kind==='studio'&&item.parentId?DB.studios.find(x=>x.id===item.parentId):null;
  const nm=kind==='studio'?DB.movies.filter(m=>m.studioId===item.id):DB.movies.filter(m=>ensureArr(m.categoryIds).includes(item.id));
  const nsc=kind==='studio'?DB.scenes.filter(sc=>sc.siteId===item.id):DB.scenes.filter(sc=>ensureArr(sc.categoryIds).includes(item.id));
  socLinks=kind==='studio'?`${item.url?`<a href="${esc(/^https?:/.test(item.url)?item.url:'https://'+item.url)}" target="_blank" rel="noopener" class="btn icon" title="${esc(item.url)}"><i data-lucide="globe"></i></a>`:''}${item.twitter?`<a href="https://x.com/${esc(item.twitter.replace(/^@/,''))}" target="_blank" rel="noopener" class="btn icon" title="X (Twitter)"><i data-lucide="twitter"></i></a>`:''}${item.instagram?`<a href="https://instagram.com/${esc(item.instagram.replace(/^@/,''))}" target="_blank" rel="noopener" class="btn icon" title="Instagram"><i data-lucide="instagram"></i></a>`:''}`:'';
  const cTagSet=kind==='studio'&&item.country?`<div class="logo-meta ${item.logo?'':'inline'}"><i data-lucide="map-pin"></i>${esc(item.country)}</div>`:'';cTag=cTagSet;
  actsHTML=`<div class="dacts"><button class="btn" data-action="edit"><i data-lucide="pencil"></i>Edit</button><button class="btn" data-action="share"><i data-lucide="share-2"></i>Share</button><button class="btn danger" data-action="del"><i data-lucide="trash-2"></i>Delete</button></div>`;
  const dActs=item.logo?'':actsHTML;   // with a logo the actions live on the logo itself
  const chipsHTML=`${mother?`<div class="dchips"><button class="chip on" data-action="open" data-kind="studio" data-id="${mother.id}" style="cursor:pointer">↳ Series Of ${esc(mother.name)}<i data-lucide="arrow-up-right" style="width:11px;height:11px;margin-left:4px"></i></button></div>`:''}
    ${kids.length?`<div class="dchips">${kids.map(k=>`<button class="chip on" data-action="open" data-kind="studio" data-id="${k.id}" style="cursor:pointer">${esc(k.name)}<i data-lucide="arrow-up-right" style="width:11px;height:11px;margin-left:4px"></i></button>`).join('')}</div>`:''}`;
  infoHTML=`<div class="dinfo">${item.logo?'':`<h1>${esc(item.name)}</h1>`}
   ${!item.logo?cTagSet:''}
   ${kind==='studio'&&!item.logo&&socLinks?`<div class="logo-socials inline">${socLinks}</div>`:''}
   ${((()=>{const d=descHTML(kind,item,'margin:0;max-width:none');return d?`<div class="flab">Description</div>${d}`:'';})()) }
   ${kids.length?`<div class="flab">Series Under This Studio (${kids.length})</div>`:''}
   ${(mother||kids.length)?`<div class="drow">${chipsHTML}</div>`:''}
   ${dActs}
  </div>`;
  const tabsFor=(gp,mAll,sAll,cap)=>{
   const mOn=mAll.length?'movies':'scenes';
   const mShow=cap?mAll.slice(0,cap):mAll,sShow=cap?sAll.slice(0,cap):sAll;
   const tp=(n,lbl)=>`<button class="chip ${n===mOn?'on':''}" style="cursor:pointer" data-stabg="${gp}" data-stab="${gp}-${n}">${lbl}</button>`;
   return `<div class="dchips" style="margin-bottom:10px">${tp('movies','Movies ('+mAll.length+')')}${tp('scenes','Scenes ('+sAll.length+')')}</div>`
    +`<div data-stabp="${gp}-movies"${mOn==='movies'?'':' style="display:none"'}>${mShow.length?`<div class="grid" style="--cw:200px">${mShow.map(movieCard).join('')}</div>`:`<div class="empty" style="margin-top:10px"><i data-lucide="inbox"></i><span>No Movies.</span></div>`}</div>`
    +`<div data-stabp="${gp}-scenes"${mOn==='scenes'?'':' style="display:none"'}>${sShow.length?`<div class="grid" style="--cw:250px">${sShow.map(sceneCard).join('')}</div>`:`<div class="empty" style="margin-top:10px"><i data-lucide="inbox"></i><span>No Scenes.</span></div>`}</div>`;
  };
  const seriesSecs=kids.map(k=>{
   const km=DB.movies.filter(m=>m.studioId===k.id),ks=DB.scenes.filter(sc=>sc.siteId===k.id);
   const tot=km.length+ks.length;if(!tot)return '';
   const CAP=10;
   const more=(km.length>CAP||ks.length>CAP)?`<button class="morebtn" style="order:1" data-action="open" data-kind="studio" data-id="${k.id}">More<i data-lucide="arrow-up-right"></i></button>`:'';
   return `<div class="seclabel mono"><i data-lucide="layers"></i>${esc(k.name)}${more}</div>`+tabsFor('k-'+k.id,km,ks,CAP);
  }).join('');
  const dkey=kind+':'+item.id;
  detailUIReset({movie:nm,scene:nsc},new Set([...(nm.length?['movie']:[]),...(nsc.length?['scene']:[])]));
  extra=`<div data-dtoolbar>${dToolbarHTML()}</div>
   ${nm.length?`<div class="seclabel mono">Movies</div>${dSec(dkey+':movies',nm,movieCard,'movies')}`:''}
   ${nsc.length?`<div class="seclabel mono">Scenes</div>${dSec(dkey+':scenes',nsc,sceneCard,'scenes')}`:''}
   ${seriesSecs}
   ${!nm.length&&!nsc.length&&!seriesSecs?`<div class="empty" style="margin-top:26px"><i data-lucide="inbox"></i><span>Nothing Filed Under This ${kind==='studio'?'Studio':'Category'} Yet.</span></div>`:''}`;
 }
 let galleryHTML='';
 if(kind==='scene'){
  const gl=ensureArr(item.gallery);
  const glSettings=settings.gallery||{};
  const glOn=glSettings.enabled!==false;
  const glShow=glSettings.show||12;
  if(glOn&&gl.length){
   const shown=gl.slice(0,glShow);
   const isLarge=(glSettings.size)==='large';
   galleryHTML=`<div class="seclabel mono" style="margin-top:14px"><i data-lucide="images"></i>Gallery (${gl.length} Photo${gl.length===1?'':'s'})</div><div class="gallery-grid ${isLarge?'gl-large':''}">${shown.map((u,i)=>`<div class="gallery-item" data-idx="${i}"><img src="${esc(u)}" alt="Gallery ${i+1}" loading="lazy"></div>`).join('')}</div>${gl.length>glShow?`<div class="mono dim" style="font-size:11px;margin-top:8px">Showing ${glShow} Of ${gl.length} — Increase In Settings › Gallery To See More</div>`:''}`;
  }
 }
 $('#main').innerHTML=`<div class="page">
  <button class="backlink" data-action="back"><i data-lucide="arrow-left"></i><span class="mono">${backLabel}</span></button>
  ${item.logo?`<div class="studio-logo-lg"><img src="${esc(item.logo)}" alt=""><div class="logo-foot"><div class="logo-side">${cTag}${socLinks?`<span class="logo-socials">${socLinks}</span>`:''}</div>${actsHTML}</div></div>`:''}
  <div class="detail-head ${kind==='performer'?'perf':''}${(kind==='studio'||kind==='category')?' single':''}">${kind==='scene'?`<div class="media-col">${mediaHTML}${galleryHTML}</div>`:`${mediaHTML}${galleryHTML}`}${infoHTML}</div>
  ${playerBlock}${extra}</div>`;
 if(kind==='movie'||kind==='scene')mountPlayer($('#pwrap'),item,kind);
 if(kind==='studio'||kind==='category'){dInitPicker();dEnsureChecks($('#main'))}
 // Movies / Scenes tabs (sub-studio sections + sub-studio pages)
 $$('[data-stab]',$('#main')).forEach(b=>b.addEventListener('click',()=>{
  const g=b.dataset.stabg;
  $$('[data-stabg="'+g+'"]',$('#main')).forEach(x=>x.classList.toggle('on',x===b));
  $$('[data-stabp]',$('#main')).forEach(p=>{if(p.dataset.stabp.indexOf(g+'-')===0)p.style.display=p.dataset.stabp===b.dataset.stab?'':'none'});
 }));
 // Gallery lightbox — open ONCE, then swap content in place.
 // (Re-opening the modal on every arrow click replayed the .pop animation +
 //  re-created the <img>, which read as the dialog "jumping" on each step.)
 $$('.gallery-item',$('#main')).forEach(el=>el.addEventListener('click',()=>{
  const allUrls=ensureArr(item.gallery);
  let curIdx=+el.dataset.idx||0;
  const lbCache=new Map();
  function srcFor(u){
   const s=String(u||'');
   if(!s.startsWith('enc://'))return Promise.resolve(s);
   if(!lbCache.has(s))lbCache.set(s,encToObjectURL(s).then(o=>o||''));
   return lbCache.get(s);
  }
  function paint(bl,f){
   const img=$('#gl-img',bl);
   if(img){img.style.opacity='.35';srcFor(allUrls[curIdx]).then(u=>{if(u)img.src=u;else img.style.opacity='1'})}
   const ttl=$('#m-title-text');if(ttl)ttl.textContent='Gallery '+(curIdx+1)+'/'+allUrls.length;
   const cnt=$('#gl-count',f);if(cnt)cnt.textContent=(curIdx+1)+' / '+allUrls.length;
   const pv=$('[data-action=gl-prev]',f),nx=$('[data-action=gl-next]',f);
   if(pv)pv.disabled=curIdx<=0;
   if(nx)nx.disabled=curIdx>=allUrls.length-1;
   [curIdx-1,curIdx+1].forEach(i=>{if(allUrls[i])srcFor(allUrls[i]).then(u=>{if(u){const im=new Image();im.src=u}})});
  }
  openModal([{title:'Gallery '+(curIdx+1)+'/'+allUrls.length,
   html:()=>`<div style="text-align:center"><img id="gl-img" src="" alt="" style="max-width:100%;max-height:80vh;border-radius:8px;opacity:.35;transition:opacity .15s"></div>`,
   footer:()=>`<button class="btn" data-action="gl-prev"><i data-lucide="chevron-left"></i></button><span class="mono" id="gl-count" style="font-size:12px"></span><button class="btn" data-action="gl-next"><i data-lucide="chevron-right"></i></button><span class="push"></span>`,
   onClose(){lbCache.clear()},
   mount(bl,f){
    icons(bl);icons(f);
    const img=$('#gl-img',bl);
    img&&img.addEventListener('load',()=>{img.style.opacity='1'});
    $('[data-action=gl-prev]',f)?.addEventListener('click',()=>{if(curIdx>0){curIdx--;paint(bl,f)}});
    $('[data-action=gl-next]',f)?.addEventListener('click',()=>{if(curIdx<allUrls.length-1){curIdx++;paint(bl,f)}});
    paint(bl,f);
   }
  }],0,700);
 }));
}
