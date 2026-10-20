"use strict";
/* ===== MOVIE / SCENE FORM ===== */
function mediaForm(kind,item){
 const isMovie=kind==='movie';
 const editing=!!item;
 const years=yearsRange();
 const studioNames=DB.studios.map(s=>s.name),perfNames=DB.performers.map(p=>p.name);
 const R={};
 const scenesField=isMovie
  ?`<div class="fw"><label class="flab">Scenes</label><input class="field" id="ff-scenes" type="number" min="1" value="${item?.scenes||''}"></div>`
  :`<div class="fw"><label class="flab">Movie</label><div class="tagwrap"><div id="ff-movie"></div></div></div>`;
 const body=`
  <button class="fetchbtn hide" id="fetchbtn" type="button"><i data-lucide="cloud-download"></i>Get Information<em>Title + Studio Required</em></button>
  <div class="fsec"><div class="fttl">Identity</div>
   <div class="fw"><label class="flab">Title *</label><input class="field" id="ff-title" value="${esc(item?.title||'')}" placeholder="${isMovie?'Movie Title':'Scene Title'}"></div>
   <div class="fw"><label class="flab">Studio *</label><div id="ff-studio"></div></div>
   <div class="frow"><div class="fw"><label class="flab">${isMovie?'Release Year':'Release Date'}</label>${isMovie
     ?`<select class="field" id="ff-year"><option value="">Year...</option>${years.map(y=>`<option value="${y}" ${item?.year==y?'selected':''}>${y}</option>`).join('')}<option value="__new" ${item&&!years.includes(item.year)?'selected':''}>Other...</option></select><input class="field" id="ff-year-x" placeholder="Enter Year" style="display:${item&&!years.includes(item.year)?'':'none'};margin-top:8px" value="${item&&!years.includes(item.year)?esc(item.year):''}">`
     :`<input class="field" id="ff-date" type="date" value="${esc(toISODate(item?.date)||'')}">`}</div>
   <div class="fw"><label class="flab">Duration (Min)</label><input class="field" id="ff-dur" type="number" min="1" value="${item?.durationMin||''}"></div></div>
   <div class="frow">${scenesField}
   <div class="fw"><label class="flab">Director</label><input class="field" id="ff-dir" value="${esc(item?.director||'')}" list="dl-dir"><datalist id="dl-dir">${DIRECTORS.map(d=>`<option value="${esc(d)}">`).join('')}</datalist></div></div>
  </div>
  <div class="fsec"><div class="fttl">People & Tags</div>
   <div class="fw"><label class="flab">Actors</label><div id="ff-actors"></div></div>
   <div class="fw"><label class="flab">Categories</label><div class="tagwrap"><div id="ff-cats"></div></div></div>
   <div class="fw"><label class="flab">Description</label><textarea class="field" id="ff-desc" rows="4" placeholder="Synopsis...">${esc(item?.desc||'')}</textarea></div>
  </div>
   <div class="fsec"><div class="fttl">${isMovie?'Posters':'Covers'} (Max 2)</div>
    <div class="slots2">
     <div><label class="flab">${isMovie?'Front Poster':'Cover Thumbnail'}</label><div id="slot-a"></div></div>
     <div><label class="flab">${isMovie?'Back Poster':'Cover Player'}</label><div id="slot-b"></div></div>
    </div>
${!isMovie?`<div style="margin-top:10px"><label class="flab">List Thumbnail</label>
      <div class="radiogroup"><label class="ckrow"><input type="radio" name="thumbpick" value="0" ${(item?.thumb||0)===0?'checked':''}>Cover Thumbnail</label>
      <label class="ckrow"><input type="radio" name="thumbpick" value="1" ${(item?.thumb||0)===1?'checked':''}>Cover Player</label></div></div>`:''}
  </div>
  <div class="fsec"><div class="fttl">Media File</div>
   <div class="fw">
    <div class="dirrow" id="ff-file-row" style="${item?.filePath?'':'display:none'}">
     <i data-lucide="film"></i>
     <span id="ff-file-path">${esc(item?.filePath||'')}</span>
     <button class="tx" type="button" id="ff-file-clear" title="Remove"><i data-lucide="x"></i></button>
    </div>
    <div style="display:flex;gap:8px;margin-top:${item?.filePath?'8px':'0'}" id="ff-file-btns">
     <button class="btn sm" type="button" id="ff-file-browse"><i data-lucide="folder-open"></i>Browse Server</button>
     <input class="field" id="ff-file-manual" placeholder="Or paste file path..." value="${esc(item?.filePath||'')}" style="flex:1">
    </div>
   </div>
  </div>`;
 openDrawer({
  title:editing?(isMovie?'Edit Movie':'Edit Scene'):(isMovie?'Add Movie':'Add Scene'),
  sub:isMovie?'Movie Record':'Scene / Sequence Record',
  body,
  onMount(){
   R.titleEl=$('#ff-title');
   R.studio=item?[DB.studios.find(s=>s.id===(isMovie?item.studioId:item.siteId))?.name].filter(Boolean):[];
   const studioBox=$('#ff-studio');
   R.renderStudio=()=>{
    studioBox.classList.add('tagbox');
    studioBox.innerHTML=R.studio.map((v,i)=>`<span class="tag"><span>${esc(v)}</span><button class="tx" data-i="${i}" type="button"><i data-lucide="x"></i></button></span>`).join('')
     +`<button type="button" class="tag" id="ff-studio-add" style="cursor:pointer"><i data-lucide="plus" style="width:11px;height:11px"></i><span>Select</span></button>`;
    icons();
   };
   studioBox.addEventListener('click',e=>{
    const tx=e.target.closest('.tx');
    if(tx){R.studio.splice(+tx.dataset.i,1);R.renderStudio();return}
    if(e.target.closest('#ff-studio-add'))openStudioPicker(R.studio,arr=>{R.studio=arr;R.renderStudio();R.updFetch&&R.updFetch()});
   });
   R.renderStudio();
   if(isMovie)R.scenesEl=$('#ff-scenes');
   else R.movieTag=tagInput($('#ff-movie'),item&&item.movieId?[DB.movies.find(m=>m.id===item.movieId)?.title].filter(Boolean):[],DB.movies.map(m=>m.title),{single:true,ph:'Movie Title (Optional)...'});
   R.actors=item?ensureArr(item.actorIds).map(id=>DB.performers.find(p=>p.id===id)?.name).filter(Boolean):[];
   const actorsBox=$('#ff-actors');
   R.renderActors=()=>{
    actorsBox.classList.add('tagbox');
    actorsBox.innerHTML=R.actors.map((v,i)=>`<span class="tag"><span>${esc(v)}</span><button class="tx" data-i="${i}" type="button"><i data-lucide="x"></i></button></span>`).join('')
     +`<button type="button" class="tag" id="ff-actors-add" style="cursor:pointer"><i data-lucide="plus" style="width:11px;height:11px"></i><span>Select</span></button>`;
    icons();
   };
   actorsBox.addEventListener('click',e=>{
    const tx=e.target.closest('.tx');
    if(tx){R.actors.splice(+tx.dataset.i,1);R.renderActors();return}
    if(e.target.closest('#ff-actors-add'))openActorPicker(R.actors,arr=>{R.actors=arr;R.renderActors()});
   });
   R.renderActors();
   R.cats=item?catsOf(item):[];
   const catBox=$('#ff-cats');
   R.renderCats=()=>{
    catBox.classList.add('tagbox');
    catBox.innerHTML=R.cats.map((v,i)=>`<span class="tag"><span>${esc(v)}</span><button class="tx" data-i="${i}" type="button"><i data-lucide="x"></i></button></span>`).join('')
     +`<button type="button" class="tag" id="ff-cats-add" style="cursor:pointer"><i data-lucide="plus" style="width:11px;height:11px"></i><span>Select</span></button>`;
    icons();
   };
   catBox.addEventListener('click',e=>{
    const tx=e.target.closest('.tx');
    if(tx){R.cats.splice(+tx.dataset.i,1);R.renderCats();return}
    if(e.target.closest('#ff-cats-add'))openCategoryPicker(R.cats,arr=>{R.cats=arr;R.renderCats()});
   });
   R.renderCats();
   R.slotA=bindSlot('slot-a',isMovie?'r23':'r169',item?(isMovie?item.posterF:item.covers?.[0]):'');
   R.slotB=bindSlot('slot-b',isMovie?'r23':'r169',item?(isMovie?item.posterB:item.covers?.[1]):'');
   const ySel=$('#ff-year'),yX=$('#ff-year-x');
   if(ySel)ySel.addEventListener('change',()=>{yX.style.display=ySel.value==='__new'?'':'none'});
   R.getStudio=()=>R.studio[0]||'';
   R.fetchBtn=$('#fetchbtn');
   R.fetchBtn.addEventListener('click',()=>{
    const d=collect(false);
    openFetchModal(kind,{title:d.title,studio:R.getStudio(),current:pseudoCurrent(d),apply:u=>applyToMediaForm(R,u,kind)});
   });
   wireFetchToggle(R,R.titleEl);
   // File picker
   R.filePath=item?.filePath||'';
   const fileRow=$('#ff-file-row'),filePathEl=$('#ff-file-path'),fileManual=$('#ff-file-manual');
   const updateFileUI=()=>{
    if(R.filePath){fileRow.style.display='';filePathEl.textContent=R.filePath;fileManual.value=R.filePath}
    else{fileRow.style.display='none';fileManual.value=''}
   };
   $('#ff-file-browse').addEventListener('click',async()=>{
    if(!Sync.on){toast('Server Not Connected - Paste Path Manually','alert-triangle');return}
    try{
     const r=await fetch('/api/dialog/file',{method:'POST'});
     if(!r.ok)throw new Error('HTTP '+r.status);
     const j=await r.json();
     if(j.path){R.filePath=j.path;updateFileUI();toast('File Selected','film')}
    }catch(e){toast('Could Not Open File Dialog','alert-triangle')}
   });
   $('#ff-file-clear').addEventListener('click',()=>{R.filePath='';updateFileUI()});
   fileManual.addEventListener('change',()=>{R.filePath=fileManual.value.trim()});
   return R;
  },
  onSave(){
   const d=collect(true);if(!d)return false;
   const studioId=resolveStudio(d.studio);
   const actorIds=d.actors.map(resolvePerformer);
   const categoryIds=d.cats.map(resolveCategory);
   const title=titleCase(d.title);
   const director=titleCase(d.dir);
   if(isMovie){
    if(editing){
     Object.assign(item,{title,studioId,durationMin:d.dur,scenes:d.scenes,director,actorIds,categoryIds,desc:d.desc,year:d.year,posterF:d.pA||item.posterF,posterB:d.pB||item.posterB,filePath:d.filePath||item.filePath||''});
     Sync.push('movies','update',item);
    }else{
      const rec={id:uid('mv'),title,studioId,durationMin:d.dur,scenes:d.scenes,director,actorIds,categoryIds,fav:false,desc:d.desc,year:d.year,posterF:d.pA||'',posterB:d.pB||'',filePath:d.filePath||''};
     DB.movies.push(rec);Sync.push('movies','create',rec);
    }
    toast(editing?'Saved Changes':'Movie Added');
   }else{
     const mv=resolveMovie(d.movie,studioId);
    let covers=[d.pA,d.pB].filter(Boolean);
    if(covers.length===2&&covers[0]===covers[1])covers=[covers[0]];
    const finalCovers=covers.length?covers:(item?.covers?.length?item.covers:[]);
    const thumb=Math.min(d.thumb||0,Math.max(0,finalCovers.length-1));
    if(editing){
     Object.assign(item,{title,siteId:studioId,movieId:mv?mv.id:null,durationMin:d.dur,director,actorIds,categoryIds,desc:d.desc,date:d.date,covers:finalCovers,thumb,filePath:d.filePath||item.filePath||''});
     Sync.push('scenes','update',item);
    }else{
     const rec={id:uid('sc'),title,siteId:studioId,movieId:mv?mv.id:null,durationMin:d.dur,director,actorIds,categoryIds,fav:false,desc:d.desc,date:d.date,covers:finalCovers,thumb,filePath:d.filePath||''};
     DB.scenes.push(rec);Sync.push('scenes','create',rec);
    }
    if(mv)toast('Scene Saved - Linked To '+mv.title,'link');
    else toast(editing?'Saved Changes':'Scene Added');
   }
   render();
  }
 });
 function pseudoCurrent(d){
  if(isMovie)return{title:d.title,year:d.year,durationMin:d.dur,scenes:d.scenes,director:d.dir,desc:d.desc,posterF:d.pA,posterB:d.pB};
  let covers=[d.pA,d.pB].filter(Boolean);
  if(covers.length===2&&covers[0]===covers[1])covers=[covers[0]];
  return{title:d.title,date:d.date,durationMin:d.dur,director:d.dir,desc:d.desc,covers};
 }
 function collect(strict){
  const title=$('#ff-title')?.value.trim()||'';
  const studio=R.studio[0]||'';
  let year=null,date=null,scenes=0,movie='';
  if(isMovie){
   const s=$('#ff-year'),x=$('#ff-year-x');if(s)year=s.value==='__new'?(parseInt(x?.value)||null):(s.value?+s.value:null);
   scenes=parseInt(R.scenesEl?.value)||0;
  }else{
   date=$('#ff-date')?.value||null;
   R.movieTag.flush();
   movie=R.movieTag.get()[0]||'';
  }
  const d={title,studio,year,date,scenes,movie,dur:parseInt($('#ff-dur')?.value)||0,dir:$('#ff-dir')?.value.trim()||'',actors:R.actors.slice(),cats:R.cats.slice(),desc:$('#ff-desc')?.value.trim()||'',pA:R.slotA.get(),pB:R.slotB.get(),thumb:parseInt($$('input[name=thumbpick]').find(r=>r.checked)?.value)||0,filePath:R.filePath||''};
  if(strict){
   if(!title){$('#ff-title').classList.add('err');toast('Title Is Required','alert-triangle');return null}
   if(!studio){toast('Studio Is Required','alert-triangle');return null}
  }
  return d;
 }
}
function applyToMediaForm(R,u,kind){
 if(!u)return;
 const isMovie=kind==='movie';
 if(u.title!=null)R.titleEl.value=u.title;
 if(u.studioName){R.studio=[u.studioName];R.renderStudio()}
 if(isMovie&&u.year!=null){const s=$('#ff-year'),x=$('#ff-year-x');if(s){const has=[...s.options].some(o=>o.value==String(u.year));if(has){s.value=String(u.year);x&&(x.style.display='none')}else{s.value='__new';if(x){x.style.display='';x.value=u.year}}}}
 if(!isMovie&&u.date!=null){const el=$('#ff-date');el&&(el.value=u.date)}
 if(u.durationMin!=null)$('#ff-dur').value=u.durationMin;
 if(isMovie&&u.scenes!=null&&R.scenesEl)R.scenesEl.value=u.scenes;
 if(u.director!=null)$('#ff-dir').value=u.director;
 if(Array.isArray(u.performers)){R.actors=u.performers.slice();R.renderActors()}
 if(!isMovie&&Array.isArray(u.groups)&&R.movieTag)R.movieTag.set(u.groups.length?[u.groups[0]]:[]);
 if(u.catNames){R.cats=u.catNames.slice();R.renderCats()}
 if(u.desc!=null)$('#ff-desc').value=u.desc;
 if(isMovie){
  if(u.posterF!=null){
   if(R.slotB.get()&&R.slotB.get()===R.slotA.get())R.slotB.set('');
   R.slotA.set(u.posterF);
  }
  if(u.posterB!=null)R.slotB.set(u.posterB);
 }
 else if(u.covers){if(u.covers[0]!=null)R.slotA.set(u.covers[0]);if(u.covers[1]!=null)R.slotB.set(u.covers[1])}
 R.updFetch&&R.updFetch();
 toast('Information Applied To Form','cloud-download');
}

/* ===== PERFORMER FORM ===== */
function performerForm(item){
 const editing=!!item;
 const R={};
 const body=`
  <button class="fetchbtn hide" id="fetchbtn" type="button"><i data-lucide="cloud-download"></i>Get Information<em>Name Required</em></button>
  <div class="fsec"><div class="fttl">Identity</div>
   <div class="frow"><div class="fw"><label class="flab">Stage Name *</label><input class="field" id="pf-name" value="${esc(item?.name||'')}"></div>
   <div class="fw"><label class="flab">Aliases</label><input class="field" id="pf-alias" value="${esc(item?.aliases||'')}"></div></div>
   <div class="fw"><label class="flab">Gender</label><div class="radiogroup">
    <label class="radioline"><input type="radio" name="pfg" value="f" ${item?.gender!=='m'?'checked':''}><span class="dot"></span>Female</label>
    <label class="radioline"><input type="radio" name="pfg" value="m" ${item?.gender==='m'?'checked':''}><span class="dot"></span>Male</label>
   </div></div>
   <div class="fw"><label class="flab">Birth Date</label><input class="field" id="pf-birth" type="date" value="${esc(toISODate(item?.birth)||'')}"></div>
  </div>
  <div class="fsec"><div class="fttl">Appearance</div>
   <div class="frow3">
    <div class="fw"><label class="flab">Ethnicity</label><input class="field" id="pf-eth" value="${esc(item?.ethnicity||'')}" list="dl-eth"><datalist id="dl-eth">${ETH.map(e=>`<option value="${esc(e)}">`).join('')}</datalist></div>
    <div class="fw"><label class="flab">Nationality</label><input class="field" id="pf-nat" value="${esc(item?.nationality||'')}"></div>
    <div class="fw"><label class="flab">Hair</label><input class="field" id="pf-hair" value="${esc(item?.hair||'')}" list="dl-hair"><datalist id="dl-hair">${HAIR.map(e=>`<option value="${esc(e)}">`).join('')}</datalist></div>
    <div class="fw"><label class="flab">Eyes</label><input class="field" id="pf-eyes" value="${esc(item?.eyes||'')}" list="dl-eyes"><datalist id="dl-eyes">${EYES.map(e=>`<option value="${esc(e)}">`).join('')}</datalist></div>
   </div>
   <div class="frow3">
    <div class="fw"><label class="flab">Height (cm)</label><input class="field" id="pf-h" type="number" value="${item?.height||''}"></div>
    <div class="fw"><label class="flab">Weight (kg)</label><input class="field" id="pf-w" type="number" value="${item?.weight||''}"></div>
    <div class="fw"><label class="flab">Career Start</label><input class="field" id="pf-cs" type="number" placeholder="2016" value="${item?.careerStart||''}"></div>
   </div>
   <div class="frow"><div class="fw fem"><label class="flab">Measurements</label><input class="field" id="pf-meas" placeholder="86-61-89" value="${esc(item?.measurements||'')}"></div>
   <div class="fw fem"><label class="flab">Boobs</label><div class="radiogroup">
    <label class="radioline"><input type="radio" name="pfb" value="Natural" ${(item?.boobs||'Natural')==='Natural'?'checked':''}><span class="dot"></span>Natural</label>
    <label class="radioline"><input type="radio" name="pfb" value="Enhanced" ${item?.boobs==='Enhanced'?'checked':''}><span class="dot"></span>Enhanced</label>
   </div></div></div>
   <div class="frow"><div class="fw fem"><label class="flab">Piercings</label><input class="field" id="pf-pierce" value="${esc(item?.piercings||'')}"></div>
   <div class="fw"><label class="flab">Tattoos</label><input class="field" id="pf-tat" value="${esc(item?.tattoos||'')}"></div></div>
  </div>
  <div class="fsec"><div class="fttl">Social</div>
   <div class="fw"><label class="flab">X (Twitter)</label><input class="field" id="pf-twitter" placeholder="@handle" value="${esc(item?.twitter||'')}"></div>
   <div class="fw"><label class="flab">Instagram</label><input class="field" id="pf-instagram" placeholder="@handle" value="${esc(item?.instagram||'')}"></div>
   <div class="fw"><label class="flab">OnlyFans</label><input class="field" id="pf-onlyfans" placeholder="username or URL" value="${esc(item?.onlyfans||'')}"></div>
  </div>
  <div class="fsec"><div class="fttl">Photo</div><div id="slot-photo"></div></div>`;
 openDrawer({title:editing?'Edit Performer':'Add Performer',sub:'Performer Record',body,
  onMount(){
   R.nameEl=$('#pf-name');
   R.photo=bindSlot('slot-photo','r34',item?.photo||'');
   const gender=()=>$$('input[name=pfg]').find(r=>r.checked)?.value||'f';
   const updGender=()=>{const m=gender()==='m';$$('.fem').forEach(e=>e.style.display=m?'none':'')};
   $$('input[name=pfg]').forEach(r=>r.addEventListener('change',updGender));updGender();
   R.getStudio=()=>'__ok';
    R.fetchBtn=$('#fetchbtn');
    R.fetchBtn.addEventListener('click',()=>openPerformerFetchMenu(R,item,gender));
    wireFetchToggle(R,R.nameEl);
    return R;
   },
  onSave(){
   const name=titleCase($('#pf-name').value.trim());
   if(!name){$('#pf-name').classList.add('err');toast('Stage Name Is Required','alert-triangle');return false}
   const gender=$$('input[name=pfg]').find(r=>r.checked)?.value||'f';
   const rec=item||{id:uid('p')};
   Object.assign(rec,{name,gender,aliases:titleCase($('#pf-alias').value.trim()),birth:$('#pf-birth').value||null,ethnicity:titleCase($('#pf-eth').value.trim()),nationality:titleCase($('#pf-nat').value.trim()),hair:titleCase($('#pf-hair').value.trim()),eyes:titleCase($('#pf-eyes').value.trim()),height:parseInt($('#pf-h').value)||null,weight:parseInt($('#pf-w').value)||null,careerStart:parseInt($('#pf-cs').value)||null,measurements:gender==='f'?$('#pf-meas').value.trim():null,boobs:gender==='f'?($$('input[name=pfb]').find(r=>r.checked)?.value||'Natural'):null,piercings:gender==='f'?titleCase($('#pf-pierce').value.trim()):null,tattoos:titleCase($('#pf-tat').value.trim()),twitter:$('#pf-twitter').value.trim()||null,instagram:$('#pf-instagram').value.trim()||null,onlyfans:$('#pf-onlyfans').value.trim()||null,photo:R.photo.get()||rec.photo||''});
   if(!item)DB.performers.push(rec);
   Sync.push('performers',editing?'update':'create',rec);
   toast('Saved');render();
  }});
}
function openPerformerFetchMenu(R,item,gender){
 const name=R.nameEl?.value?.trim()||item?.name||'';
 if(!name){$('#pf-name').classList.add('err');toast('Stage Name Is Required','alert-triangle');return}
 openModal([{title:'Get Information & Picture',html:()=>`
  <div class="cmsg" style="margin-bottom:14px">Choose What To Fetch For <b>"${esc(name)}"</b>.</div>
  <div style="display:flex;flex-direction:column;gap:8px">
   <button class="btn" id="pf-fi" type="button"><i data-lucide="cloud-download"></i>Get Performer Information</button>
   <button class="btn" id="pf-fp" type="button"><i data-lucide="user-round"></i>Update Performer Picture</button>
  </div>`,
  footer:()=>`<span class="push"></span><button class="btn" data-mclose="1">Close</button>`,
  mount(){icons();
   $('#pf-fi').addEventListener('click',()=>{modalSteps=null;closeModal();openFetchModal('performer',{title:name,gender:gender(),current:item||{},apply:u=>applyToPerfForm(R,u)})});
   $('#pf-fp').addEventListener('click',()=>{modalSteps=null;closeModal();openPerformerPhotoModal(v=>R.photo.set(v),name)});
  }}],0,520);
}
function openPerformerPhotoModal(setPhoto,name,onDone){
 const scrapers=settings.scrapers.filter(s=>kindHas(s.kind,'performer')&&s.enabled);
 if(!scrapers.length){toast('No Performer Scraper Enabled','alert-triangle');return}
 let chosen=null;
 openModal([{title:'Update Performer Picture',html:()=>`
  <div class="cmsg" style="margin-bottom:14px">Fetch A Fresh Picture For <b>"${esc(name)}"</b>.</div>
  <div style="display:flex;flex-direction:column;gap:8px">
   ${scrapers.map((s,i)=>`<div class="siterow scraper" data-scr="${i}"><span class="dot"></span><i data-lucide="${s.type==='python'?'file-code':'file-json'}"></i><b>${esc(s.name)}</b><span class="mono">${s.type==='python'?'Python':'YAML'}</span></div>`).join('')}
  </div>`,
  footer:()=>`<span class="push"></span><button class="btn primary" id="pfpp-go" disabled>Fetch Picture<i data-lucide="user-round"></i></button>`,
  mount(b,f){
   icons();
   $$('.siterow[data-scr]',b).forEach(r=>r.addEventListener('click',()=>{$$('.siterow',b).forEach(x=>x.classList.remove('on'));r.classList.add('on');chosen=scrapers[+r.dataset.scr];$('#pfpp-go',f).disabled=false}));
   $('#pfpp-go',f)?.addEventListener('click',async()=>{
    if(!chosen)return;
    $('#pfpp-go',f).disabled=true;$('#pfpp-go',f).innerHTML='<i data-lucide="loader"></i>Fetching...';icons(f);
    try{
     const r=await fetch('/api/scrape',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind:'performer',mode:'scraper',scraper_id:chosen.id,title:name})});
     if(!r.ok)throw new Error('HTTP '+r.status);
     const raw=await r.json();
     if(raw&&(raw.notFound||raw.error))throw new Error(raw.error||'No Match Found');
     const m=normResult('performer',raw);
     if(!m||!m.photo)throw new Error('No Picture Found');
     setPhoto(m.photo);
     toast(onDone?'Picture Updated':'Picture Fetched - Save The Form To Keep It','user-round');
     if(onDone)onDone(m.photo);
     modalSteps=null;closeModal();
    }catch(err){
     toast('Picture Fetch Failed: '+err.message,'alert-triangle');
     $('#pfpp-go',f).disabled=false;$('#pfpp-go',f).innerHTML='Fetch Picture<i data-lucide="user-round"></i>';icons(f);
    }
   });
  }}],0,520);
}
function applyToPerfForm(R,u){
 if(!u)return;
 if(u.name!=null)R.nameEl.value=u.name;
 const map={birth:'#pf-birth',ethnicity:'#pf-eth',nationality:'#pf-nat',hair:'#pf-hair',eyes:'#pf-eyes',piercings:'#pf-pierce',tattoos:'#pf-tat',measurements:'#pf-meas',twitter:'#pf-twitter',instagram:'#pf-instagram',onlyfans:'#pf-onlyfans'};
 for(const k in map){if(u[k]!=null){const el=$(map[k]);el&&(el.value=u[k])}}
 if(u.height!=null)$('#pf-h').value=u.height;
 if(u.weight!=null)$('#pf-w').value=u.weight;
 if(u.careerStart!=null)$('#pf-cs').value=u.careerStart;
 if(u.boobs!=null){const r=$$('input[name=pfb]').find(x=>x.value===u.boobs);if(r){r.checked=true}else{const n=$$('input[name=pfb]')[0];n&&(n.checked=true)}}
 if(u.gender){const r=$$('input[name=pfg]').find(x=>x.value===u.gender);if(r){r.checked=true;r.dispatchEvent(new Event('change'))}}
 if(u.photo)R.photo.set(u.photo);
 toast('Information Applied To Form','cloud-download');
}

/* ===== WIKIPEDIA DESCRIPTIONS ===== */
const WIKI_ADULT=/\b(porn(?:o|ography|ographic)?|adult (?:film|movie|video|studio|entertainment|industry|performer|actress|actor|star|model)|erot(?:ic|ica)|xxx|hardcore|glamour model|fetish|webcam model|cam model|stripper|exotic dancer|nude model|sex film|avn award|iafd)\b/i;
async function wikiFetchDesc(name){
 if(Sync.on){
  try{const r=await fetch('/api/wikipedia?q='+encodeURIComponent(name));if(r.ok){const d=await r.json();if(d&&d.extract)return d}}catch(e){}
 }
 let hits=[];
 try{
  const r=await fetch('https://en.wikipedia.org/w/rest.php/v1/search/page?q='+encodeURIComponent(name)+'&limit=8');
  if(r.ok){const j=await r.json();hits=(j.pages||[]).map(p=>({title:p.title,meta:(p.description||'')+' '+(p.excerpt||'')})).filter(h=>h.title)}
 }catch(e){}
 if(!hits.length){
  try{
   const s=await fetch('https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch='+encodeURIComponent(name)+'&srlimit=8&format=json&origin=*').then(r=>r.ok?r.json():null);
   hits=((s&&s.query&&s.query.search)||[]).map(h=>({title:h.title,meta:h.snippet||''})).filter(h=>h.title);
  }catch(e){}
 }
 for(const h of hits.slice(0,6)){
  let e=null;try{e=await fetch('https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&exintro=1&redirects=1&titles='+encodeURIComponent(h.title)+'&format=json&origin=*').then(r=>r.ok?r.json():null)}catch(e2){}
  const pages=(e&&e.query&&e.query.pages)||{};const pg=pages[Object.keys(pages)[0]]||{};
  const ext=String(pg.extract||'').trim();
  const title=pg.title||h.title;
  if(ext&&!/may refer to/i.test(ext.split('\n')[0])&&WIKI_ADULT.test(h.meta+' '+ext+' '+title))return {title,extract:ext,url:'https://en.wikipedia.org/wiki/'+encodeURIComponent(title.replace(/ /g,'_'))};
 }
 return null;
}

/* ===== STUDIO / CATEGORY FORM ===== */
function studioCategoryForm(kind,item){
 const isSt=kind==='studio';
 const ICONS=['film','heart','camera','gem','tv','flame','feather','tag','gamepad-2','glasses'];
 const body=isSt?`
  <div class="fw"><label class="flab">Name *</label><input class="field" id="sf-name" value="${esc(item?.name||'')}"></div>
  <div class="frow"><div class="fw"><label class="flab">Website</label><input class="field" id="sf-url" value="${esc(item?.url||'')}" placeholder="studio.com"></div>
  <div class="fw"><label class="flab">Country</label><input class="field" id="sf-country" value="${esc(item?.country||'')}"></div></div>
  <div class="fw"><div style="display:flex;align-items:baseline;justify-content:space-between;gap:8px"><label class="flab">Description</label><button class="btn sm" type="button" id="sf-wiki"><i data-lucide="globe"></i>Get From Wikipedia</button></div><textarea class="field" id="sf-desc" rows="3">${esc(item?.desc||'')}</textarea></div>
  <div class="frow"><div class="fw"><label class="flab">X (Twitter)</label><input class="field" id="sf-twitter" placeholder="@handle" value="${esc(item?.twitter||'')}"></div>
  <div class="fw"><label class="flab">Instagram</label><input class="field" id="sf-instagram" placeholder="@handle" value="${esc(item?.instagram||'')}"></div></div>
  <div class="fw"><label class="flab">Mother Website (Series Rolls Up Under It)</label><select class="field" id="sf-parent"><option value="">— None (Top Level Studio) —</option>${DB.studios.filter(x=>x.id!==(item?.id||'')).sort((a,b)=>a.name.localeCompare(b.name)).map(x=>`<option value="${x.id}" ${item?.parentId===x.id?'selected':''}>${esc(x.name)}</option>`).join('')}</select></div>
  <div id="slot-logo"></div>`
 :`
  <div class="fw"><label class="flab">Name *</label><input class="field" id="sf-name" value="${esc(item?.name||'')}"></div>
  <div class="fw"><label class="flab">Icon</label><select class="field" id="sf-icon">${ICONS.map(i=>`<option value="${i}" ${item?.icon===i?'selected':''}>${i}</option>`).join('')}</select></div>
  <div class="fw"><label class="flab">Description</label><textarea class="field" id="sf-desc" rows="3">${esc(item?.desc||'')}</textarea></div>`;
 let slotLogo=null;
 openDrawer({title:(item?'Edit ':'Add ')+(isSt?'Studio':'Category'),sub:isSt?'Studio Record':'Category Record',body,
  onMount(){if(isSt){slotLogo=bindSlot('slot-logo','sq',item?.logo||'');
   const wb=$('#sf-wiki');
   wb&&wb.addEventListener('click',async()=>{
    const nm=$('#sf-name').value.trim();
    if(!nm){toast('Enter The Studio Name First','alert-triangle');return}
    wb.disabled=true;toast('Looking Up Wikipedia…','search');
    try{
     const d=await wikiFetchDesc(nm);
     if(d&&d.extract){$('#sf-desc').value=d.extract;toast('Description Filled From Wikipedia · '+(d.title||nm),'globe')}
     else{toast('No Adult-Related Wikipedia Article Found For '+nm,'alert-triangle')}
    }catch(e){toast('Wikipedia Lookup Failed','alert-triangle')}
    wb.disabled=false;
   });
  }},
  onSave(){
   const name=titleCase($('#sf-name').value.trim());
   if(!name){$('#sf-name').classList.add('err');toast('Name Is Required','alert-triangle');return false}
   if(isSt){
    const logoVal=(slotLogo&&slotLogo.get())||'';
    const rec=item||{id:uid('st')};
    Object.assign(rec,{name,url:$('#sf-url').value.trim(),country:titleCase($('#sf-country').value.trim()),desc:$('#sf-desc').value.trim(),twitter:$('#sf-twitter').value.trim()||null,instagram:$('#sf-instagram').value.trim()||null,parentId:$('#sf-parent').value||null,logo:(logoVal&&!logoVal.startsWith('blob:'))?logoVal:(item?.logo||'')});
    if(!item)DB.studios.push(rec);
    Sync.push('studios',item?'update':'create',rec);
   }else{
    const rec=item||{id:uid('c')};
    Object.assign(rec,{name,icon:$('#sf-icon').value,desc:$('#sf-desc').value.trim()});
    if(!item)DB.categories.push(rec);
    Sync.push('categories',item?'update':'create',rec);
   }
   toast('Saved');render();
  }});
 }

/* ===== BULK FETCH (all or selected items) ===== */
function bulkFetchItems(tab){
 const items=bulkSel.active&&bulkSel.selected.size?[...bulkSel.selected].map(id=>byId(tab.slice(0,-1),id)).filter(Boolean):[...DB[tab]];
 if(!items.length)toast('Nothing To Process In This Section','alert-triangle');
 return items;
}
function bulkRunFetch(tab,items,op,scraperId){
 /* op 'info': try scrapers until match, apply all fields. op 'pic': first result with a photo. */
 const kind=tab.slice(0,-1),kindPl=tab;
 const label=op==='pic'?'Picture':'Information';
 const scrapers=settings.scrapers.filter(s=>kindHas(s.kind,kind)&&s.enabled);
 const order=scraperId?scrapers.filter(s=>s.id===scraperId):scrapers;
 openModal([{title:`Bulk Get ${label}`,html:()=>`
  <div class="cmsg" style="margin-bottom:14px">Fetching ${label} For ${items.length===1?'1 Item':items.length+' Items'} sequentially - This Can Take A While.</div>
  <div style="max-height:320px;overflow:auto">
  ${items.map((it,i)=>`<div class="siterow" id="bfr-${i}"><span class="dot"></span><b>${esc(it.title||it.name||'')}</b><span class="mono" data-st style="color:var(--faint)">Queued</span></div>`).join('')}
  </div>`,
  footer:()=>`<span class="push"></span><span class="mono" id="bfr-sum">0/${items.length}</span> <button class="btn" data-mclose="1">Close</button>`,
  mount(){
   (async()=>{
    let ok=0;
    for(let i=0;i<items.length;i++){
     const it=items[i],row=$(`#bfr-${i}`);if(!row)break;
     const st=row.querySelector('[data-st]');st.textContent='Searching...';
     let done=false,reason='';
     for(const s of order){
      try{
       const r=await fetch('/api/scrape',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind,mode:'scraper',scraper_id:s.id,title:it.title||it.name||'',gallery_count:0})});
       if(!r.ok){reason='HTTP '+r.status;continue}
       const raw=await r.json();
       if(raw&&(raw.notFound||raw.error)){reason=raw.error||'Not Found';continue}
       const m=normResult(kind,raw);
       if(!m){reason='Empty Result';continue}
       if(op==='pic'){
        // first scraper that answers AND yields a photo wins
        if(!m.photo){reason='No Picture';continue}
        it.photo=m.photo;Sync.push(kindPl,'update',it);done=true;break;
       }
       applyFetchTo(kind,it,m,true);done=true;break;
      }catch(err){reason=err.message||'Error'}
     }
     st.textContent=done?'Found':(reason||'Not Found');
     st.style.color=done?'var(--ok)':'var(--faint)';
     done&&ok++;
     const sum=$('#bfr-sum');if(sum)sum.textContent=`${ok}/${i+1}${ok===i+1?'':' · '+(i+1-ok)+' Missed'}`;
    }
    const row=$('#bfr-0');
    if(row){
     modalSteps=null;closeModal();
     toast(`Bulk Fetch Done - ${ok} Of ${items.length} Got ${label}`,'cloud-download');render();icons();
    }
   })();
  }}],0,560);
}
function openBulkFetchMenu(tab){
 const kind=tab.slice(0,-1);
 const items=bulkFetchItems(tab);
 if(!items.length)return;
 const scrapers=settings.scrapers.filter(s=>kindHas(s.kind,kind)&&s.enabled);
 let op='info';
 const pickScraper=scraperId=>{modalSteps=null;closeModal();bulkRunFetch(tab,items,op,scraperId)};
 const s1={title:`Bulk Get ${op==='pic'?'Picture':'Information'} - Choose Source`,html:()=>`
  <div class="cmsg" style="margin-bottom:14px">Using <b>${op==='pic'?'Picture':'Information'}</b> For ${items.length===1?'1 Item':items.length+' Items'}. Pick How To Fetch: Go Through All Websites, Or Choose One Certain Scraper.</div>
  <div style="display:flex;flex-direction:column;gap:8px">
   <div class="siterow" data-bulkscr="all"><span class="dot"></span><i data-lucide="globe"></i><b>Go Through All Websites</b><span class="mono">Try Each Until A Match</span></div>
   ${scrapers.map((s,i)=>`<div class="siterow scraper" data-bulkscr="${i}"><span class="dot"></span><i data-lucide="${s.type==='python'?'file-code':'file-json'}"></i><b>${esc(s.name)}</b><span class="mono">${s.type==='python'?'Python':'YAML'}</span></div>`).join('')||''}
  </div>`,
  footer:()=>`<span class="push"></span><button class="btn" data-mclose="1">Cancel</button>`,
  mount(b){
   $$('.siterow[data-bulkscr]',b).forEach(r=>r.addEventListener('click',()=>{
    const idx=r.dataset.bulkscr;pickScraper(idx==='all'?null:scrapers[+idx].id);
   }));
  }};
 if(kind==='performer'){
  const s0={title:'Get Information Or Picture',html:()=>`
   <div class="cmsg" style="margin-bottom:14px">Performers: ${items.length===1?'1 Item':items.length+' Items'}. Choose What To Fetch:</div>
   <div style="display:flex;flex-direction:column;gap:8px">
    <div class="siterow" data-bfop="info"><span class="dot"></span><i data-lucide="cloud-download"></i><b>Get Information</b></div>
    <div class="siterow" data-bfop="pic"><span class="dot"></span><i data-lucide="user-round"></i><b>Get Picture</b></div>
   </div>`,
   footer:()=>`<span class="push"></span><button class="btn" data-mclose="1">Cancel</button>`,
   mount(b){
    $$('.siterow[data-bfop]',b).forEach(r=>r.addEventListener('click',()=>{
     op=r.dataset.bfop;
     s1.title=`Bulk Get ${op==='pic'?'Picture':'Information'} - Choose Source`;
     modalIdx=1;renderModal();
    }));
   }};
  openModal([s0,s1],0,560);
  return;
 }
 openModal([s1],0,560);
}
