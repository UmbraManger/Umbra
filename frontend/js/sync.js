"use strict";
/* ===== BACKEND SYNC ===== */
const failedBackendImgs=new Set();
document.addEventListener('error',e=>{
 const t=e.target;
 if(t&&t.tagName==='IMG'){
  const s=t.getAttribute('src')||'';
  if(s.indexOf('/api/images/')===0)failedBackendImgs.add(t);
 }
},true);
function reloadFailedBackendImages(){
 failedBackendImgs.forEach(im=>{
  const s=im.getAttribute('src');
  im.src=s+(s.includes('?')?'&':'?')+'u='+Date.now();
  failedBackendImgs.delete(im);
 });
}
function ensureArr(v){return Array.isArray(v)?v:(typeof v==='string'?(()=>{try{return JSON.parse(v)}catch(e){return []}})():[])}
function normItem(x){if(x.actorIds)x.actorIds=ensureArr(x.actorIds);if(x.categoryIds)x.categoryIds=ensureArr(x.categoryIds);return x}
const Sync={
 on:false,
 async init(){
  try{
   const r=await fetch('/api/ping');
   if(!r.ok)return;
   const j=await r.json();
   if(!j||!j.ok)return;
   this.on=true;
   window.addEventListener('online',()=>this._flush());
   const lib=await(await fetch('/api/library')).json();
   if(lib){
    DB.movies=(lib.movies||[]).map(normItem);DB.scenes=(lib.scenes||[]).map(normItem);DB.performers=lib.performers||[];
    // One-time cleanup: purge any leftover picsum.photos mock/placeholder URLs that
    // got persisted into real records by an earlier version of this app, plus any
    // movie whose back cover is an exact duplicate of its front cover (also almost
    // certainly an old auto-duplicate rather than a genuine distinct back cover).
    const isMock=v=>typeof v==='string'&&v.includes('picsum.photos');
    for(const mv of DB.movies){
     let changed=false;
     if(isMock(mv.posterF)){mv.posterF='';changed=true}
     if(isMock(mv.posterB)||(mv.posterB&&mv.posterB===mv.posterF)){mv.posterB='';changed=true}
     if(changed)Sync.push('movies','update',mv);
    }
    for(const sc of DB.scenes){
     if(Array.isArray(sc.covers)&&sc.covers.some(isMock)){
      sc.covers=sc.covers.filter(c=>!isMock(c));
      Sync.push('scenes','update',sc);
     }
    }
    for(const p of DB.performers){
     if(isMock(p.photo)){p.photo='';Sync.push('performers','update',p)}
    }
    DB.studios=lib.studios||[];DB.categories=lib.categories||[];
   }
   const st=lib&&lib.settings?lib.settings:null;
   if(st&&Object.keys(st).length){
    settings=mergeSettings(settings,st);
    if(!settings.catLimit)settings.catLimit=10;
    if(!settings.cwLimit)settings.cwLimit=4;
    if(!settings.adv)settings.adv={accent:'',background:'',font:'',radius:null,border:'1'};
    applyTheme();applyAdvanced();
   }
   await refreshScrapers();
    await Positions.load();
    render();
    // Deferred while the App Lock screen is up (lockApp picks it up after the
    // password clears) so entry never stacks two password prompts at once.
    if(!(settings.lock&&settings.lock.on))this.checkImageLock();
   toast('Backend Connected - Library Loaded','database');
  }catch(e){/* no backend - standalone demo mode */}
 },
 // Outgoing write queue: pushes retry transient failures with backoff instead
 // of being silently dropped; repeated settings writes coalesce into one.
 _queue:[],_flushing:false,_warned:false,
 _enqueue(req,coalesce){
  if(coalesce)this._queue=this._queue.filter(q=>q.url!==req.url);
  this._queue.push(req);
  if(this._queue.length>400)this._queue.shift();
  this._flush();
 },
 _flush(){
  if(this._flushing||!this.on||!this._queue.length)return;
  this._flushing=true;
  const req=this._queue.shift();
  fetch(req.url,{method:req.method,headers:{'Content-Type':'application/json'},body:req.body})
   .then(r=>{
    if(r.status===429||r.status>=500)throw new Error('retry');
    if(!r.ok){if(!this._warned){this._warned=true;toast('Some Changes Were Rejected By The Backend','alert-triangle')}return}
    this._warned=false;
   })
   .catch(()=>{
    req.attempts=(req.attempts||0)+1;
    if(req.attempts<=5){this._queue.unshift(req);setTimeout(()=>Sync._flush(),1200*req.attempts)}
    else if(!this._warned){this._warned=true;toast('Some Local Changes Could Not Be Saved To The Backend','alert-triangle')}
   })
   .finally(()=>{this._flushing=false;if(this._queue.length)this._flush()});
 },
 push(kind,op,item){
  if(!this.on||!item)return;
  if(op==='deleteAll'){this._enqueue({url:'/api/'+kind+'/deleteAll',method:'POST',body:JSON.stringify(item)},true);return}
  this._enqueue({url:op==='delete'?'/api/'+kind+'/'+item.id:'/api/'+kind,
   method:op==='delete'?'DELETE':op==='create'?'POST':'PUT',body:JSON.stringify(item)});
 },
 pushSettings(){
  if(!this.on)return;
  this._enqueue({url:'/api/settings',method:'PUT',body:JSON.stringify(settings)},true);
 },
 async checkImageLock(){
  try{
   const r=await fetch('/api/images/status');
   if(!r.ok)return;
   const s=await r.json();
    if(s.pass_set)settings.imgProt.hash=settings.imgProt.hash||'set';
    // Prompt whenever ciphertext still needs opening: protection on, or off
    // with blobs left encrypted (unlock then repairs them back to plaintext).
    if(!s.unlocked&&s.pass_set&&(s.on||(s.enc_count||0)>0))this.unlockPrompt();
  }catch(e){}
 },
 unlockPrompt(){
  openModal([{title:'Image Protection - Passphrase',html:()=>`
   <div class="cmsg" style="margin-bottom:12px">Enter The Image Protection Passphrase To View Protected Images.</div>
   <input class="field" id="bk-ip-pass" type="password" placeholder="Passphrase">`,
   footer:()=>`<span class="push"></span><button class="btn primary" id="bk-ip-ok"><i data-lucide="unlock"></i>Unlock</button>`,
   mount(){
    const inp=$('#bk-ip-pass');setTimeout(()=>inp.focus(),50);
    const go=async()=>{
     const r=await fetch('/api/images/unlock',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({passphrase:inp.value})});
     if(r.ok){closeModal();reloadFailedBackendImages();icons();toast('Images Unlocked','unlock')}
     else{inp.classList.add('err');toast('Wrong Passphrase','alert-triangle')}
    };
    $('#bk-ip-ok').addEventListener('click',go);
    inp.addEventListener('keydown',e=>{if(e.key==='Enter')go()});
   }}],0,460);
 }
};
/* ===== WATCH POSITIONS (resume / continue watching) ===== */
const Positions={
 map:{},_t:{},order:[],_ordKey:'obscura:posorder',
 // recency ledger: most-recently-watched kind:id first (localStorage, no backend shape change)
 loadOrder(){try{const o=JSON.parse(localStorage.getItem(this._ordKey)||'[]');this.order=Array.isArray(o)?o.filter(x=>typeof x==='string'):[]}catch(e){this.order=[]}},
 saveOrder(){try{localStorage.setItem(this._ordKey,JSON.stringify(this.order))}catch(e){}},
 touch(key){this.order=this.order.filter(k=>k!==key);this.order.unshift(key);if(this.order.length>300)this.order.length=300;this.saveOrder()},
 age(key){const i=this.order.indexOf(key);return i<0?Infinity:i},
 forget(key){this.order=this.order.filter(k=>k!==key);this.saveOrder()},
 async load(){ if(!Sync.on)return; try{const r=await fetch('/api/positions'); if(r.ok)this.map=await r.json()||{}}catch(e){} },
 get(kind,id){ return this.map[kind+':'+id]||0 },
 save(kind,id,pos){
  if(!Sync.on||!(pos>0))return;
  const key=kind+':'+id;this.map[key]=pos;this.touch(key);
  clearTimeout(this._t[key]);
  this._t[key]=setTimeout(()=>{
   fetch(`/api/media/${kind}/${id}/position`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({position:pos})}).catch(()=>{});
  },800);
 },
 saveNow(kind,id,pos){
  if(!Sync.on||!(pos>0))return;
  const key=kind+':'+id;this.map[key]=pos;this.touch(key);
  clearTimeout(this._t[key]);delete this._t[key];
  fetch(`/api/media/${kind}/${id}/position`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({position:pos})}).catch(()=>{});
 },
 clear(kind,id){
  const key=kind+':'+id;
  clearTimeout(this._t[key]);delete this._t[key];
  if(this.map[key]!=null)delete this.map[key];
  this.forget(key);
  if(Sync.on)fetch(`/api/media/${kind}/${id}/position`,{method:'DELETE'}).catch(()=>{});
 },
 clearAll(){ this.map={};this.order=[];this.saveOrder();Object.keys(this._t).forEach(k=>clearTimeout(this._t[k]));this._t={}; if(Sync.on)fetch('/api/positions',{method:'DELETE'}).catch(()=>{}) },
  progress(kind,id){
   const it=byId(kind,id); if(!it) return 0;
   const pos=this.get(kind,id); if(!pos) return 0;
   let dur=(it.durationMin||0)*60;
   // a movie with no file plays its linked scenes — progress against that total,
   // not the (often missing or scraped) movie metadata runtime
   if(kind==='movie'&&!it.filePath){
    const sum=DB.scenes.filter(s=>s.movieId===id&&s.filePath).reduce((a,s)=>a+(s.durationMin||0)*60,0);
    if(sum)dur=sum;
   }
   if(!dur) return 0;
   return Math.min(0.99,pos/dur);
  }
};
Positions.loadOrder();
function toISODate(s){
 if(s==null)return null;
 const str=String(s).trim();
 if(/^\d{4}-\d{2}-\d{2}/.test(str))return str.slice(0,10);
 const d=new Date(str);
 if(isNaN(d))return null;
 return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');
}
function normResult(kind,d){
 if(!d||typeof d!=='object')return null;
 const g={...d};
 if(kind==='performer'&&g.name&&g.title==null)g.title=g.name;
 g.title=g.title||'Unknown';
 g.studioName=g.studio||g.studioName||g.studio_name||'';
 if(g.duration_min!=null)g.durationMin=g.duration_min;
 if(g.details!=null&&g.desc==null)g.desc=g.details;
 if(g.birthday!=null&&g.birth==null){const iso=toISODate(g.birthday);if(iso)g.birth=iso}
 if(g.date!=null){const iso=toISODate(g.date);if(iso)g.date=iso}
 if(g.hairColor!=null&&g.hair==null)g.hair=g.hairColor;
 if(g.eyeColor!=null&&g.eyes==null)g.eyes=g.eyeColor;
 if(g.activeYears!=null&&g.careerStart==null){const cm=String(g.activeYears).match(/\d{4}/);if(cm)g.careerStart=parseInt(cm[0],10);}
 if(Array.isArray(g.tags)&&!Array.isArray(g.categories))g.categories=g.tags;
 if(g.poster_f!=null)g.posterF=g.poster_f;
 if(g.poster_b!=null)g.posterB=g.poster_b;
 if(g.career_start!=null)g.careerStart=g.career_start;
 if(!Array.isArray(g.covers)){g.covers=[g.cover_a||g.coverA||g.cardThumbnail||g.image||null,g.cover_b||g.coverB||g.thumbnail||g.image||null].filter(Boolean);if(g.covers.length===2&&g.covers[0]===g.covers[1])g.covers=[g.covers[0]];}
 if(Array.isArray(g.categories))g.catNames=g.categories;
 if(Array.isArray(g.performers))g.performers=g.performers.map(p=>typeof p==='string'?p:(p&&p.name)||'').filter(Boolean);
 if(Array.isArray(g.groups))g.groups=g.groups.map(p=>typeof p==='string'?p:(p&&p.name)||'').map(s=>String(s).trim()).filter(n=>n&&!/^(movies?|dvds?|films?)$/i.test(n));
 if(kind==='movie'){g.posterF=g.posterF||g.image||null;g.posterB=g.posterB||null}
 if(kind==='performer')g.photo=g.photo||g.image||null;
 if(g.social_urls!=null&&g.urls==null)g.urls=g.social_urls;
 return g;
}
async function backendFetch(kind,ctx,chosen,url){
 modalIdx=1;renderModal();
 const glCount=(settings.gallery&&settings.gallery.count)||12;
 const body=chosen.type==='scraper'
  ?{kind,mode:'scraper',scraper_id:chosen.s.id,title:ctx.title,url:url||'',gallery_count:kind==='scene'?glCount:0}
  :{kind,mode:'site',source:chosen.s,title:ctx.title,url:url||'',gallery_count:kind==='scene'?glCount:0};
 try{
  const r=await fetch('/api/scrape',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if(!r.ok){const j=await r.json().catch(()=>({}));throw new Error(j.detail||('HTTP '+r.status))}
  const raw=await r.json();
  if(raw&&(raw.notFound||raw.error))throw new Error(raw.error||'No Match Found');
  const m=normResult(kind,raw);
  if(!m)throw new Error('Empty Result');
  if(!modalSteps||modalSteps.length<1){closeModal();return}
  const step=buildCompareStep(kind,m,ctx,chosen.s.name);
  modalSteps=[modalSteps[0],step];modalIdx=1;renderModal();
 }catch(err){
  toast('Lookup Failed: '+err.message,'alert-triangle');
  modalIdx=0;renderModal();
 }
}
async function backendAI(kind,ctx,extra){
 modalIdx=1;renderModal();
 try{
  const r=await fetch('/api/scrape',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind,mode:'ai',title:ctx.title,extra:extra||''})});
  if(!r.ok){const j=await r.json().catch(()=>({}));throw new Error(j.detail||('HTTP '+r.status))}
  const m=normResult(kind,await r.json());
  if(!m)throw new Error('Empty Result');
  if(!modalSteps||modalSteps.length<1){closeModal();return}
  const step=buildCompareStep(kind,m,ctx,'AI · '+(settings.ai.model||'AI'));
  modalSteps=[modalSteps[0],step];modalIdx=1;renderModal();
 }catch(err){
  toast('AI Lookup Failed: '+err.message,'alert-triangle');
  modalIdx=0;renderModal();
 }
}
