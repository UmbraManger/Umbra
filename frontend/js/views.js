"use strict";
/* ===== SIDEBAR / ROUTER ===== */
function navItem(id,ic,lb,n){const on=state.view.name==='tab'&&state.view.tab===id;
 return `<button class="nitem ${on?'on':''}" data-action="nav" data-tab="${id}"><i data-lucide="${ic}"></i><span class="nav-label">${lb}</span>${n!=null?`<span class="ncount mono">${n}</span>`:''}</button>`}
function renderSidebar(){
 $('#sidebar').innerHTML=`
  <div class="brand"><span class="bmark"><img src="img/umbra.png" alt=""></span><div><div class="bname">Umbra</div><div class="bsub mono">Private Media Manager</div></div></div>
  <div class="navlbl mono">Library</div>
  <nav>
   ${navItem('movies','film','Movies',DB.movies.length)}
   ${navItem('scenes','clapperboard','Scenes',DB.scenes.length)}
   ${navItem('performers','users','Performers',DB.performers.length)}
   ${navItem('studios','building-2','Studios',DB.studios.length)}
   ${navItem('categories','tag','Categories',DB.categories.length)}
   ${navItem('profile','user','Profile',favCount())}
  </nav>
  <div class="navlbl mono">System</div>
  <nav>
   ${navItem('settings','settings','Settings',null)}
   ${navItem('about','info','About',null)}
  </nav>
  <div class="sfoot">
   <button class="btn icon ghost" data-action="theme-quick" title="Toggle Theme"><i data-lucide="${settings.theme==='dark'?'sun':'moon'}"></i></button>
   <button class="btn icon ghost" data-action="lock-now" title="Lock Now" ${settings.lock.on?'':'style="display:none"'}><i data-lucide="lock"></i></button>
   <span class="mono">v0.9 · ${Sync.on?'Synced':'Local'}</span>
  </div>`;
}
function render(){
 renderSidebar();
 const v=state.view;
 if(v.name==='tab')renderTab(v.tab);
 else if(v.name==='detail')renderDetail(v.kind,v.id);
 icons();
}

/* ===== CARDS ===== */
function movieCard(m){const st=DB.studios.find(s=>s.id===m.studioId);const cats=catsOf(m).slice(0,2).join(' · ');
 const chk=bulkSel.active?`<div class="bulk-chk ${bulkSel.selected.has(m.id)?'on':''}" data-bulk-id="${m.id}" data-bulk-kind="movie"></div>`:'';
 return `<article class="card" ${bulkSel.selected.has(m.id)?'data-bulk-sel':''} data-action="open" data-kind="movie" data-id="${m.id}">${chk}<div class="card-media r23">${mediaPh(m.posterF,'','film')}<button class="favbtn ${m.fav?'on':''}" data-action="toggle-fav" data-kind="movie" data-id="${m.id}" title="Favorite"><i data-lucide="heart"></i></button><span class="badge">${fmtDur(m.durationMin)}</span></div><div class="card-body"><h3>${esc(m.title)}</h3><div class="cmeta mono">${m.year||'-'} · ${esc(st?.name||'-')}</div>${cats?`<div class="ctags">${esc(cats)}</div>`:''}</div></article>`}
function sceneCard(sc){const st=DB.studios.find(s=>s.id===sc.siteId);const cats=catsOf(sc).slice(0,2).join(' · ');const thumb=(sc.covers||[])[sc.thumb||0]||sc.covers?.[0]||'';
 const chk=bulkSel.active?`<div class="bulk-chk ${bulkSel.selected.has(sc.id)?'on':''}" data-bulk-id="${sc.id}" data-bulk-kind="scene"></div>`:'';
 return `<article class="card" ${bulkSel.selected.has(sc.id)?'data-bulk-sel':''} data-action="open" data-kind="scene" data-id="${sc.id}">${chk}<div class="card-media r169">${mediaPh(thumb,'','clapperboard')}<button class="favbtn ${sc.fav?'on':''}" data-action="toggle-fav" data-kind="scene" data-id="${sc.id}" title="Favorite"><i data-lucide="heart"></i></button><span class="badge">${fmtDur(sc.durationMin)}</span></div><div class="card-body"><h3>${esc(sc.title)}</h3><div class="cmeta mono">${fmtDate(sc.date)} · ${esc(st?.name||'-')}</div>${cats?`<div class="ctags">${esc(cats)}</div>`:''}</div></article>`}
function perfCard(p){const chk=bulkSel.active?`<div class="bulk-chk ${bulkSel.selected.has(p.id)?'on':''}" data-bulk-id="${p.id}" data-bulk-kind="performer"></div>`:'';
 return `<article class="card perfcard" ${bulkSel.selected.has(p.id)?'data-bulk-sel':''} data-action="open" data-kind="performer" data-id="${p.id}">${chk}<div class="card-media r34">${mediaPh(p.photo,'','user')}</div><div class="card-body center"><h3>${esc(p.name)}</h3></div></article>`}
function studioCard(s){const nm=DB.movies.filter(m=>m.studioId===s.id).length,nsc=DB.scenes.filter(sc=>sc.siteId===s.id).length;
 const mom=s.parentId?DB.studios.find(x=>x.id===s.parentId):null;
 const banner=s.logo?`<div class="studio-logo"><img src="${esc(s.logo)}" alt="" loading="lazy"></div>`:'';
 const mono=s.logo?'':`<div class="monogram">${esc(s.name[0]||'?')}</div>`;
 const chk=bulkSel.active?`<div class="bulk-chk ${bulkSel.selected.has(s.id)?'on':''}" data-bulk-id="${s.id}" data-bulk-kind="studio"></div>`:'';
 return `<article class="card card-flat" ${bulkSel.selected.has(s.id)?'data-bulk-sel':''} data-action="open" data-kind="studio" data-id="${s.id}">${chk}${banner}<div class="card-body">${mono}<h3>${esc(s.name)}</h3><div class="cmeta mono">${esc(s.url||'-')}</div><div class="cmeta mono dim">${nm} Movies · ${nsc} Scenes${mom?` · ↳ ${esc(mom.name)}`:''}</div></div></article>`}
function categoryCard(c){const n=DB.movies.filter(m=>ensureArr(m.categoryIds).includes(c.id)).length+DB.scenes.filter(sc=>ensureArr(sc.categoryIds).includes(c.id)).length;
 const chk=bulkSel.active?`<div class="bulk-chk ${bulkSel.selected.has(c.id)?'on':''}" data-bulk-id="${c.id}" data-bulk-kind="category"></div>`:'';
 return `<article class="card card-flat" ${bulkSel.selected.has(c.id)?'data-bulk-sel':''} data-action="open" data-kind="category" data-id="${c.id}">${chk}<div class="card-body"><div class="monogram"><i data-lucide="${esc(c.icon||'tag')}"></i></div><h3>${esc(c.name)}</h3><div class="cmeta mono dim">${n} Items</div></div></article>`}
function ageFromBirth(birth){
 if(!birth)return null;
 const d=new Date(birth+'T00:00:00');
 if(isNaN(d))return null;
 const now=new Date();
 let age=now.getFullYear()-d.getFullYear();
 if(now.getMonth()<d.getMonth()||(now.getMonth()===d.getMonth()&&now.getDate()<d.getDate()))age--;
 return age>0&&age<120?age:null;
}
function rowFor(tab,x){
 const _rchk=(id,kind)=>bulkSel.active?`<div class="bulk-chk ${bulkSel.selected.has(id)?'on':''}" data-bulk-id="${id}" data-bulk-kind="${kind}"></div>`:'';
 if(tab==='movies'){const st=DB.studios.find(s=>s.id===x.studioId);const cats=catsOf(x);
  return `<div class="row" ${bulkSel.selected.has(x.id)?'data-bulk-sel':''} data-action="open" data-kind="movie" data-id="${x.id}">${_rchk(x.id,'movie')}${mediaPh(x.posterF,'rowimg','film')}<div class="rowmain"><b>${esc(x.title)}</b><span class="rsub">${esc(String(x.year||'-'))} · ${esc(st?.name||'-')}</span>${cats.length?`<span class="rsub">${esc(cats.join(' · '))}</span>`:''}</div><span class="rtime">${fmtDur(x.durationMin)}</span><i data-lucide="chevron-right"></i></div>`}
 if(tab==='scenes'){const st=DB.studios.find(s=>s.id===x.siteId);const cats=catsOf(x);
  return `<div class="row" ${bulkSel.selected.has(x.id)?'data-bulk-sel':''} data-action="open" data-kind="scene" data-id="${x.id}">${_rchk(x.id,'scene')}${mediaPh((x.covers||[])[x.thumb||0]||'','rowimg w','clapperboard')}<div class="rowmain"><b>${esc(x.title)}</b><span class="rsub">${esc(fmtDate(x.date))} · ${esc(st?.name||'-')}</span>${cats.length?`<span class="rsub">${esc(cats.join(' · '))}</span>`:''}</div><span class="rtime">${fmtDur(x.durationMin)}</span><i data-lucide="chevron-right"></i></div>`}
 const age=ageFromBirth(x.birth);
 const bits=[x.gender==='m'?'Male':'Female'];
 if(age!=null)bits.push(age+' Y/O');
 if(x.ethnicity)bits.push(x.ethnicity);
 if(x.nationality)bits.push(x.nationality);
 if(x.hair)bits.push(x.hair+' Hair');
 if(x.eyes)bits.push(x.eyes+' Eyes');
 if(x.height)bits.push(x.height+'cm');
 if(x.weight)bits.push(x.weight+'kg');
 const bodyBits=[];
 if(x.measurements)bodyBits.push(x.measurements);
 if(x.boobs)bodyBits.push(x.boobs==='Natural'?'Natural':'Enhanced');
 if(x.piercings&&x.piercings.toLowerCase()!=='none')bodyBits.push('Piercings');
 if(x.tattoos&&x.tattoos.toLowerCase()!=='none')bodyBits.push('Tattoos');
 if(x.careerStart)bodyBits.push('Since '+x.careerStart);
 const movieCount=DB.movies.filter(m=>ensureArr(m.actorIds).includes(x.id)).length;
 const sceneCount=DB.scenes.filter(s=>ensureArr(s.actorIds).includes(x.id)).length;
 const countParts=[];
 if(movieCount)countParts.push(movieCount+(movieCount===1?' Movie':' Movies'));
 if(sceneCount)countParts.push(sceneCount+(sceneCount===1?' Scene':' Scenes'));
 return `<div class="row" ${bulkSel.selected.has(x.id)?'data-bulk-sel':''} data-action="open" data-kind="performer" data-id="${x.id}">${_rchk(x.id,'performer')}${mediaPh(x.photo,'rowimg','user')}<div class="rowmain"><b>${esc(x.name)}</b><span class="rsub">${esc(bits.join(' · '))}</span>${bodyBits.length?`<span class="rsub">${esc(bodyBits.join(' · '))}</span>`:''}</div><span class="rtime">${countParts.length?countParts.join(' · '):''}</span><i data-lucide="chevron-right"></i></div>`;
}
function yearMatch(f,y){
 if(f.ymin&&f.ymax)return y>=+f.ymin&&y<=+f.ymax;
 // One-sided bounds must filter as ranges, not equality tests.
 if(f.ymin)return y>=+f.ymin;
 if(f.ymax)return y<=+f.ymax;
 return true;
}
function filtered(tab){
 if(tab==='movies'){const{q,f}=T.movies;
  let a=DB.movies.filter(x=>{const hay=[x.title,DB.studios.find(s=>s.id===x.studioId)?.name,...ensureArr(x.actorIds).map(id=>DB.performers.find(p=>p.id===id)?.name)].join(' ').toLowerCase();
   return (!q||hay.includes(q.toLowerCase()))&&(!f.studios.size||f.studios.has(x.studioId))&&(!f.cats.size||[...f.cats].every(c=>ensureArr(x.categoryIds).includes(c)))&&(!f.performers.size||ensureArr(x.actorIds).some(id=>f.performers.has(id)))&&yearMatch(f,x.year)});
  const s=f.sort;a.sort((a,b)=>s==='az'?a.title.localeCompare(b.title):s==='old'?a.year-b.year:s==='long'?b.durationMin-a.durationMin:b.year-a.year||a.title.localeCompare(b.title));return a}
 if(tab==='scenes'){const{q,f}=T.scenes;
  let a=DB.scenes.filter(x=>{const hay=[x.title,DB.studios.find(s=>s.id===x.siteId)?.name].join(' ').toLowerCase();
   return (!q||hay.includes(q.toLowerCase()))&&(!f.studios.size||f.studios.has(x.siteId))&&(!f.cats.size||[...f.cats].every(c=>ensureArr(x.categoryIds).includes(c)))&&(!f.performers.size||ensureArr(x.actorIds).some(id=>f.performers.has(id)))&&yearMatch(f,+String(x.date).slice(0,4))});
  const s=f.sort;a.sort((a,b)=>s==='az'?a.title.localeCompare(b.title):s==='old'?String(a.date).localeCompare(b.date):s==='long'?b.durationMin-a.durationMin:String(b.date).localeCompare(a.date));return a}
 if(tab==='performers'){const{q,f}=T.performers;
  return DB.performers.filter(x=>{
   if(q&&!(x.name+' '+(x.aliases||'')).toLowerCase().includes(q.toLowerCase()))return false;
   if(f.gender&&x.gender!==f.gender)return false;
   if(f.nationalities.size&&!f.nationalities.has(x.nationality))return false;
   if(f.hairColors.size&&!f.hairColors.has(x.hair))return false;
   if(f.ethnicities.size&&!f.ethnicities.has(x.ethnicity))return false;
   if(f.boobType&&x.boobs!==f.boobType)return false;
   if(f.piercings&&!(x.piercings&&x.piercings.toLowerCase()!=='none'))return false;
   if(f.tattoos&&!(x.tattoos&&x.tattoos.toLowerCase()!=='none'))return false;
   if(f.csMin&&(!x.careerStart||x.careerStart<+f.csMin))return false;
   if(f.csMax&&(!x.careerStart||x.careerStart>+f.csMax))return false;
   if(f.heightMin&&(!x.height||x.height<+f.heightMin))return false;
   if(f.heightMax&&(!x.height||x.height>+f.heightMax))return false;
   return true;
  }).sort((a,b)=>{
   const s=f.sort;
   if(s==='za')return b.name.localeCompare(a.name);
   if(s==='new')return(b.careerStart||0)-(a.careerStart||0);
   if(s==='old')return(a.careerStart||0)-(b.careerStart||0);
   return a.name.localeCompare(b.name);
  })}
 if(tab==='studios')return DB.studios.filter(x=>!x.parentId&&(!T.studios.q||x.name.toLowerCase().includes(T.studios.q.toLowerCase()))).sort((a,b)=>a.name.localeCompare(b.name));
 return DB.categories.filter(x=>!T.categories.q||x.name.toLowerCase().includes(T.categories.q.toLowerCase())).sort((a,b)=>a.name.localeCompare(b.name));
}
