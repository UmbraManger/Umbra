"use strict";
/* ===== MODAL ===== */
let modalSteps=null,modalIdx=0;
function closeModal(){const s=modalSteps&&modalSteps[modalIdx];modalSteps=null;$('#modal-root').innerHTML='';s&&s.onClose&&s.onClose()}
function openModal(steps,startIdx=0,mw){const p=modalSteps&&modalSteps[modalIdx];modalSteps=steps;modalIdx=startIdx;p&&p.onClose&&p.onClose();renderModal(mw)}
function renderModal(mw){
 if(!modalSteps||!modalSteps[modalIdx])return closeModal();
 const s=modalSteps[modalIdx];
 $('#modal-root').innerHTML=`<div class="overlay" data-mclose="1"></div><div class="modal" ${mw?`style="--mw:${mw}px"`:''}>
  <div class="mhead">${modalIdx>0?`<button class="btn icon ghost" id="m-back" title="Back"><i data-lucide="arrow-left"></i></button>`:''}
   <div class="mtitle"><span id="m-title-text">${esc(s.title)}</span><span class="mstep mono">Step ${modalIdx+1}/${modalSteps.length}</span></div>
   <button class="btn icon ghost" data-mclose="1"><i data-lucide="x"></i></button></div>
  <div class="mbody" id="m-body">${s.html()}</div>
  <div class="mfoot" id="m-foot">${s.footer?s.footer():'<span class="push"></span>'}</div></div>`;
 icons();
 const ov=$('#modal-root .overlay');ov&&ov.addEventListener('click',closeModal);
 $$('[data-mclose]').forEach(b=>b.addEventListener('click',closeModal));
 const bk=$('#m-back');bk&&bk.addEventListener('click',()=>{modalIdx--;renderModal()});
 s.mount&&s.mount($('#m-body'),$('#m-foot'));
}

/* ===== FETCH (local simulation fallback) ===== */
function mockResult(kind,title,variant,studioName,gender){
 const h=hashStr(title+'::'+variant+'::'+studioName);
 const r=mulberry32(h);
 const pick=a=>a[Math.floor(r()*a.length)];
 const t2=variant===1?title:variant===2?title+' - Extended Cut':title;
 const base={title:t2,studioName};
 if(kind==='movie')return {...base,year:2016+Math.floor(r()*9),durationMin:78+Math.floor(r()*60),scenes:1+Math.floor(r()*4),director:pick(DIRECTORS),catNames:[pick(CATS_POOL),pick(CATS_POOL)].filter((v,i,a)=>a.indexOf(v)===i),desc:DESCS[h%4](t2),posterF:img('mock-'+slug(title)+'-'+variant+'-f',600,900),posterB:img('mock-'+slug(title)+'-'+variant+'-b',600,900)};
 if(kind==='scene'){const d=new Date(2020+Math.floor(r()*5),Math.floor(r()*12),1+Math.floor(r()*28));const ds=d.getFullYear()+'-'+pad(d.getMonth()+1)+'-'+pad(d.getDate());return {...base,date:ds,durationMin:18+Math.floor(r()*45),director:pick(DIRECTORS),catNames:[pick(CATS_POOL)],desc:DESCS[h%4](t2),covers:[img('mock-'+slug(title)+'-'+variant+'-a',800,450),img('mock-'+slug(title)+'-'+variant+'-b',800,450)]}}
 const g=gender||'f';
 return {...base,gender:g,birth:`${1990+Math.floor(r()*9)}-${pad(1+Math.floor(r()*12))}-${pad(1+Math.floor(r()*28))}`,ethnicity:pick(ETH),hair:pick(HAIR),eyes:pick(EYES),height:155+Math.floor(r()*30),weight:48+Math.floor(r()*25),measurements:g==='f'?`${82+Math.floor(r()*10)}-${59+Math.floor(r()*6)}-${85+Math.floor(r()*10)}`:null,boobs:g==='f'?pick(BOOBS):null,piercings:g==='f'?pick(['None','Navel','Ears, Navel']):null,tattoos:pick(['None','Small Script On Wrist','Left Forearm Sleeve']),careerStart:2012+Math.floor(r()*9),photo:img('mockperf-'+slug(title)+'-'+variant,600,800)};
}
const FDEF={
 movie:[['studioName','Studio'],['year','Year'],['durationMin','Duration'],['scenes','Scenes'],['director','Director'],['performers','Cast'],['catNames','Categories'],['desc','Description']],
 scene:[['studioName','Studio'],['date','Release Date'],['durationMin','Duration'],['director','Director'],['performers','Cast'],['groups','Movie'],['catNames','Categories'],['desc','Description']],
 performer:[['birth','Born'],['ethnicity','Ethnicity'],['nationality','Nationality'],['aliases','Aliases'],['height','Height'],['weight','Weight'],['hair','Hair'],['eyes','Eyes'],['measurements','Measurements'],['boobs','Boobs'],['piercings','Piercings'],['tattoos','Tattoos'],['careerStart','Career Start'],['twitter','X (Twitter)'],['instagram','Instagram'],['onlyfans','OnlyFans']],
};
const FEMALE_ONLY=['measurements','boobs','piercings'];
function fieldDisplay(kind,key,val){
 if(val==null||val==='')return null;
 if(key==='height')return ftIn(val)+' ('+val+' cm)';
 if(key==='date')return fmtDate(val);
 if(key==='durationMin')return fmtDur(val);
 if(Array.isArray(val))return val.length?val.join(', '):null;
 return val;
}
function curVal(cur,key,kind){
 if(key==='catNames')return catsOf(cur);
 if(key==='performers')return actorsOf(cur);
 if(key==='groups')return cur.movieId?[DB.movies.find(m=>m.id===cur.movieId)?.title].filter(Boolean):[];
 if(key==='studioName'){const sid=kind==='movie'?cur.studioId:cur.siteId;return (DB.studios.find(s=>s.id===sid)||{}).name||''}
 return cur[key];
}
function buildCompareStep(kind,m,ctx,sourceLabel){
 const g=ctx.gender||m.gender||'f';
 const fields=(FDEF[kind]||[]).filter(fd=>!(kind==='performer'&&g==='m'&&FEMALE_ONLY.includes(fd[0])));
 const cur=ctx.current||{};
 const curTitle=cur.title||ctx.title;
 const isPostersOnly=!!ctx.postersOnly;
 return {title:isPostersOnly?(kind==='movie'?'Update Posters - Compare':'Update Covers - Compare'):'Update Information - Compare',html:()=>{
   const posters=kind==='movie'?{a:m.posterF,b:m.posterB,la:'Front',lb:'Back'}:kind==='scene'?{a:m.covers[0],b:m.covers[1],la:'Cover Thumbnail',lb:'Cover Player'}:{a:m.photo,b:null,la:'Photo',lb:null};
  const curA=kind==='movie'?cur.posterF:kind==='scene'?(cur.covers||[])[0]:cur.photo;
  const curB=kind==='movie'?cur.posterB:kind==='scene'?(cur.covers||[])[1]:null;
  return `
  <div class="prevhead"><div class="pvs">
   <figure class="pv"><img class="${kind!=='movie'?'w':''}" src="${esc(posters.a||'')}" alt="" onload="this.naturalWidth>this.naturalHeight&&(this.style.objectPosition='97% center')"><figcaption>${posters.la}</figcaption></figure>
   ${posters.b?`<figure class="pv"><img class="${kind!=='movie'?'w':''}" src="${esc(posters.b||'')}" alt=""><figcaption>${posters.lb}</figcaption></figure>`:''}
  </div>
  <div class="previnfo"><h3>${esc(m.title)}</h3><div class="sub2 mono">${esc(m.studioName||'')} · ${kind==='movie'?esc(m.year):kind==='scene'?esc(fmtDate(m.date)):esc(m.ethnicity)}${sourceLabel?' · '+esc(sourceLabel):''}</div>
   ${kind!=='performer'?`<div class="kv"><span class="kl">Director</span><span class="kvs">${esc(m.director)}</span></div><div class="kv"><span class="kl">Duration</span><span class="kvs">${esc(fmtDur(m.durationMin))}${m.scenes?` · ${esc(m.scenes)} Scene${m.scenes===1?'':'s'}`:''}</span></div>`:`<div class="kv"><span class="kl">Born</span><span class="kvs">${esc(fmtDate(m.birth))}</span></div><div class="kv"><span class="kl">Appearance</span><span class="kvs">${esc(m.hair)} Hair · ${esc(m.eyes)} Eyes · ${ftIn(m.height)}</span></div>`}
  </div></div>
  ${!isPostersOnly?`
  <div class="cmphd"><span></span><span>Field</span><span>Current</span><span>Found - Select To Apply</span></div>
  <label class="cmp"><input type="checkbox" checked disabled><span class="cmp-l">Title</span><span class="cmp-cur">${esc(curTitle)}</span><span class="cmp-new">${esc(m.title)}</span></label>
  ${fields.map(fd=>{const nv=fieldDisplay(kind,fd[0],m[fd[0]]);const cv=fieldDisplay(kind,fd[0],curVal(cur,fd[0],kind));const same=String(nv)===String(cv);return `<label class="cmp ${same?'same':''}"><input type="checkbox" data-fld="${fd[0]}" ${same?'disabled checked':'checked'}><span class="cmp-l">${fd[1]}</span><span class="cmp-cur">${esc(cv??'-')}</span><span class="cmp-new">${esc(nv??'-')}</span></label>`}).join('')}`:''}
  <div class="divider" style="display:flex;align-items:center;gap:12px;margin:22px 0 16px;color:var(--faint)"><span class="mono" style="font-size:9px;letter-spacing:.14em">Posters</span></div>
  <div class="pvsel">
   <figure class="pv ${curA&&curA===posters.a?'pv-cur':''}"><img class="${kind!=='movie'?'w':''}" src="${esc(posters.a||'')}" alt="" onload="this.naturalWidth>this.naturalHeight&&(this.style.objectPosition='97% center')"><figcaption>${posters.la}</figcaption></figure>
   ${posters.b?`<figure class="pv ${curB&&curB===posters.b?'pv-cur':''}"><img class="${kind!=='movie'?'w':''}" src="${esc(posters.b||'')}" alt=""><figcaption>${posters.lb}</figcaption></figure>`:''}
  </div>
  <label class="ckrow" style="margin-top:8px"><input type="checkbox" id="cmp-posters" checked>Replace ${kind==='movie'?'Posters':kind==='scene'?'Covers':'Photo'} With The Ones Shown Above</label>`;},
 footer:()=>`<span class="push"></span><button class="btn primary" id="cmp-apply"><i data-lucide="check"></i>Apply Selected</button>`,
 mount(b,f){
  $('#cmp-apply',f).addEventListener('click',()=>{
   const out={title:m.title};
   if(!isPostersOnly)$$('[data-fld]',b).forEach(c=>{if(c.checked&&!c.disabled)out[c.dataset.fld]=m[c.dataset.fld]});
   if($('#cmp-posters').checked){
    if(kind==='movie'){out.posterF=m.posterF;out.posterB=m.posterB}
    else if(kind==='scene'){out.covers=m.covers}
    else out.photo=m.photo;
   }
   if(kind==='performer')out.gender=m.gender;
   ctx.apply&&ctx.apply(out);
   closeModal();
  });
 }};
}
function openFetchModal(kind,ctx){
 // Fallback: use current item name if title is empty
 if(!ctx.title&&ctx.current&&ctx.current.name)ctx.title=ctx.current.name;
 const ai=settings.ai;
 const sites=(settings.sources[kind]||[]);
 const scrapers=settings.scrapers.filter(s=>s.kind===kind&&s.enabled);
 let chosen=null;
 const s0={title:'Get Information - Choose Source',html:()=>`
  <div class="cmsg" style="margin-bottom:14px">Pick A Source To Look Up <b>"${esc(ctx.title)}"</b> - Or Paste A Direct URL.${Sync.on?' <span class="dim">(Lookups Run On The Backend)</span>':''}</div>
  ${sites.length?sites.map((s,i)=>`<div class="siterow" data-site="${i}"><span class="dot"></span><b>${esc(s.name)}</b><span class="mono">${esc(s.url)}</span></div>`).join('')
   :`<div class="cmsg" style="margin-bottom:10px;color:var(--faint)">No ${kindLabel(kind)} Websites Added Yet - Add Them In Settings › Data Sources.</div>`}
  ${scrapers.length?`<div class="flab" style="margin:14px 0 8px">External Scrapers</div>${scrapers.map((s,i)=>`<div class="siterow scraper" data-scr="${i}"><span class="dot"></span><i data-lucide="${s.type==='python'?'file-code':'file-json'}"></i><b>${esc(s.name)}</b><span class="mono">${s.type==='python'?'Python':'YAML'}${s.structure?' · Mapped':''}</span></div>`).join('')}`:''}
  <div style="margin-top:14px"><label class="flab">Direct URL (Optional)</label><input class="field" id="fu-url" placeholder="https://..."></div>
  <div class="divider" style="display:flex;align-items:center;gap:12px;margin:20px 0 12px;color:var(--faint)"><span class="mono" style="font-size:9px;letter-spacing:.14em">Or Use AI</span></div>
  <button class="siterow ai" id="fu-ai" type="button"><i data-lucide="bot"></i><b>Ask AI Assistant</b><span class="mono">${ai.on?esc(ai.model||'AI'):'Disabled'}</span></button>`,
  footer:()=>`<span class="push"></span><button class="btn primary" id="fu-next" disabled>Continue<i data-lucide="arrow-right"></i></button>`,
  mount(b){
   $$('.siterow[data-site]',b).forEach(r=>r.addEventListener('click',()=>{$$('.siterow[data-site]',b).forEach(x=>x.classList.remove('on'));r.classList.add('on');chosen={type:'site',s:sites[+r.dataset.site]};$('#fu-next').disabled=false}));
   $$('.siterow[data-scr]',b).forEach(r=>r.addEventListener('click',()=>{$$('.siterow',b).forEach(x=>x.classList.remove('on'));r.classList.add('on');chosen={type:'scraper',s:scrapers[+r.dataset.scr]};$('#fu-next').disabled=false}));
   $('#fu-ai').addEventListener('click',()=>openAIFlow(kind,ctx));
   $('#fu-next').addEventListener('click',()=>{
    const u=$('#fu-url')?$('#fu-url').value.trim():'';
    if(Sync.on&&chosen){backendFetch(kind,ctx,chosen,u);return}
    modalIdx=1;renderModal();
    setTimeout(()=>{if(modalSteps&&modalSteps[modalIdx]===sSearch){modalIdx=2;renderModal()}},900);
   });
  }};
 const sSearch={title:'Searching...',html:()=>`<div style="display:flex;flex-direction:column;align-items:center;gap:16px;padding:40px 0"><i data-lucide="loader-2" class="spin" style="width:30px;height:30px;color:var(--accent)"></i><span class="mono" style="font-size:10px;letter-spacing:.16em;color:var(--muted)">Querying ${esc(chosen?chosen.s.name:'')}...</span></div>`,footer:()=>'<span class="push"></span>'};
 const results=()=>{const n=1+hashStr(ctx.title)%2;return [0,1,2].slice(0,n+1).map(i=>mockResult(kind,ctx.title,i,chosen?chosen.s.name:'',ctx.gender))};
 const sResults={title:'Results',html:()=>`<div class="cmsg" style="margin-bottom:14px">${results().length} Matches For <b>"${esc(ctx.title)}"</b>${chosen?' On '+esc(chosen.s.name):''}:</div>${results().map((r,i)=>`
   <div class="res" data-res="${i}"><img class="${kind!=='movie'?'w':''}" src="${esc(kind==='performer'?(r.photo||''):kind==='movie'?(r.posterF||''):((r.covers||[])[0]||''))}" alt="" onload="this.naturalWidth>this.naturalHeight&&(this.style.objectPosition='97% center')"><div><b>${esc(r.title)}</b><div class="mono">${kind==='performer'?(esc(r.ethnicity)+' · '+ftIn(r.height)):esc(r.studioName)+' · '+(kind==='movie'?esc(r.year):esc(fmtDate(r.date)))}</div></div><i data-lucide="chevron-right"></i></div>`).join('')}`,
  footer:()=>`<span class="push"></span>`,
  mount(b){$$('.res',b).forEach(r=>r.addEventListener('click',()=>{
   const m=results()[+r.dataset.res];
   const step=buildCompareStep(kind,m,ctx,chosen?chosen.s.name:'');
   modalSteps=modalSteps.slice(0,3).concat([step]);
   modalIdx=3;renderModal();
  }))}};
 openModal([s0,sSearch,sResults],0,720);
}

/* ===== AI FLOW (local simulation fallback) ===== */
const AI_STAGES=['Parsing Request...','Reading Your Library Context...','Querying Knowledge...','Cross-Checking Fields...','Merging Results...'];
function openAIFlow(kind,ctx){
 const ai=settings.ai;
 if(!ai.on){toast('Enable AI First - Settings › AI Assistant','bot');return}
 if(!ai.model.trim()){toast('Set A Model In AI Settings','alert-triangle');return}
 let _aiMemo=null;
 const aiResult=()=>(_aiMemo||(_aiMemo=mockResult(kind,ctx.title,'ai',AI_PROVIDERS[ai.provider]?.[0]||'AI',ctx.gender)));
 const sAIConf={title:'AI Assistant - Configure',html:()=>`
  <div class="cmsg" style="margin-bottom:14px">The Assistant Will Look Up <b>"${esc(ctx.title)}"</b> And Prepare ${kindLabel(kind)} Metadata You Can Compare And Apply.</div>
  <div class="kv"><span class="kl">Provider</span><span class="kvs">${esc(AI_PROVIDERS[ai.provider]?.[0]||ai.provider)}</span></div>
  <div class="kv"><span class="kl">Model</span><span class="kvs">${esc(ai.model)}</span></div>
  <div class="kv"><span class="kl">Endpoint</span><span class="kvs" style="word-break:break-all">${esc(ai.endpoint||'-')}</span></div>
  <div class="kv"><span class="kl">API Key</span><span class="kvs">${ai.key?'•••••••• (Stored Locally)':'Not Set - Demo Mode'}</span></div>
  <div style="margin-top:16px"><label class="flab">Extra Instructions (Optional)</label><textarea class="field" id="ai-instr" rows="3" placeholder="e.g. Prefer The Original Release Year..."></textarea></div>
  <p class="note" style="margin-top:10px">${Sync.on?'With The Backend Running, This Request Goes To Your Configured Endpoint Server-Side.':'Demo Mode - The Result Is Generated Locally And Simulated.'}</p>`,
  footer:()=>`<span class="push"></span><button class="btn primary" id="ai-go"><i data-lucide="bot"></i>Run AI Lookup</button>`,
  mount(b,f){$('#ai-go',f).addEventListener('click',()=>{
   if(Sync.on){backendAI(kind,ctx,$('#ai-instr')?$('#ai-instr').value.trim():'');return}
   modalIdx=1;renderModal();
  })}};
 const sAIThink={title:'AI Assistant - Thinking',html:()=>`
  <div style="display:flex;flex-direction:column;align-items:center;gap:16px;padding:40px 0">
   <i data-lucide="bot" class="spin" style="width:30px;height:30px;color:var(--accent)"></i>
   <span class="mono" id="ai-stage" style="font-size:10px;letter-spacing:.16em;color:var(--muted)">Parsing Request...</span>
  </div>`,footer:()=>'<span class="push"></span>',
  mount(){
   let i=0;
   const tick=setInterval(()=>{
    const el=$('#ai-stage');if(!el){clearInterval(tick);return}
    i=(i+1)%AI_STAGES.length;el.textContent=AI_STAGES[i];
   },380);
   setTimeout(()=>{
    clearInterval(tick);
    if(modalSteps&&modalSteps[modalIdx]===sAIThink){modalIdx=2;renderModal()}
   },1600);
  }};
 const sAIResult={title:'AI Result',html:()=>{
  const r=aiResult();
  return `<div class="cmsg" style="margin-bottom:14px">The Assistant Prepared One Merged Record For <b>"${esc(ctx.title)}"</b>:</div>
   <div class="res"><img class="${kind!=='movie'?'w':''}" src="${esc(kind==='performer'?(r.photo||''):kind==='movie'?(r.posterF||''):((r.covers||[])[0]||''))}" alt="" onload="this.naturalWidth>this.naturalHeight&&(this.style.objectPosition='97% center')"><div><b>${esc(r.title)}</b><div class="mono">${esc(ai.model)} · AI Generated</div></div><i data-lucide="chevron-right"></i></div>
   <p class="note" style="margin-top:10px">Open It To Compare Each Field Against The Current Record And Choose What To Apply.</p>`},
  footer:()=>`<span class="push"></span>`,
  mount(b){$('.res',b).addEventListener('click',()=>{
   const m=aiResult();
   const step=buildCompareStep(kind,m,ctx,'AI · '+ai.model);
   modalSteps=modalSteps.slice(0,3).concat([step]);
   modalIdx=3;renderModal();
  })}};
 openModal([sAIConf,sAIThink,sAIResult],0,720);
}
