"use strict";
/* ===== ABOUT PAGE ===== */
function renderAbout(){
 const counts=[['Movies',DB.movies.length],['Scenes',DB.scenes.length],['Performers',DB.performers.length],['Studios',DB.studios.length],['Categories',DB.categories.length]];
 const totalItems=counts.reduce((s,c)=>s+c[1],0);
 const favs=DB.movies.filter(m=>m.fav).length+DB.scenes.filter(s=>s.fav).length;
 const syncStatus=Sync.on?'Active · Backend Connected':'Local Only';
 let storageSize='-';
 try{const raw=localStorage.getItem('obscura:v1');if(raw)storageSize=((new Blob([raw]).size)/1024).toFixed(1)+' KB'}catch(e){}
 const stats=[['Version','0.9'],['Total Items',totalItems],['Favorites',favs],['Storage',storageSize],
  ...counts.map(c=>[c[0],c[1]])];
 $('#main').innerHTML=`<div class="page">
  ${pageHeadHTML('about')}
  <div class="scat" id="cat-about"><div class="scat-head"><i data-lucide="info"></i><span>About</span></div>
   <div class="ssec"><div class="shead"><i data-lucide="aperture"></i><h2>Obscura</h2><span class="mono">Private Media Manager</span></div>
    <div style="padding:4px 0 16px;color:var(--muted);font-size:13px;line-height:1.6">A self-hosted, private media library for organizing movies, scenes, performers, and studios. Your data stays on your device${Sync.on?' and synced via your backend':''}.</div>
    <div class="counts" style="margin-bottom:20px">${stats.map(s=>`<div class="cnt"><div class="mono">${s[0]}</div><div class="cv">${s[1]}</div></div>`).join('')}</div>
    <div style="margin-bottom:16px"><div class="flab">Sync</div><div style="font-size:13px;color:var(--muted)">${syncStatus}</div></div>
    <div style="margin-bottom:16px"><div class="flab">Theme</div><div style="font-size:13px;color:var(--muted)">${settings.theme==='dark'?'Dark':'Light'}${settings.adv?.accent?' · Accent: '+esc(settings.adv.accent):''}</div></div>
    <div style="margin-bottom:16px"><div class="flab">Image Protection</div><div style="font-size:13px;color:var(--muted)">${settings.imgProt?.on?'Encrypted':'Off'}</div></div>
    <div class="flab">Data</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px">
     <button class="btn" data-action="export-data"><i data-lucide="download"></i>Export Library</button>
     <button class="btn" data-action="clear-data"><i data-lucide="trash-2"></i>Clear All Data</button>
    </div>
    <p class="note" style="margin-top:16px">Obscura stores everything in your browser's local storage. Export regularly to keep backups. No telemetry, no accounts, no cloud - unless you set up sync.</p>
   </div>
  </div>
 </div>`;
 icons();
 $$('[data-action=export-data]').forEach(b=>b.addEventListener('click',()=>{
  const data={movies:DB.movies,scenes:DB.scenes,performers:DB.performers,studios:DB.studios,categories:DB.categories,settings};
  const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='obscura-library.json';a.click();URL.revokeObjectURL(a.href);toast('Library Exported','download');
 }));
 $$('[data-action=clear-data]').forEach(b=>b.addEventListener('click',()=>{
  if(!confirm('Clear All Data? This Cannot Be Undone.'))return;
  localStorage.removeItem('obscura:v1');location.reload();
 }));
}

/* ===== DRAWER ===== */
function closeDrawer(){$('#drawer-root').innerHTML=''}
function openDrawer({title,sub,body,onMount,onSave}){
 closeDrawer();
 $('#drawer-root').innerHTML=`<div class="overlay" data-dclose="1"></div><div class="drawer">
  <div class="dhead"><div><div class="dttl">${esc(title)}</div><div class="dsub mono">${esc(sub||'')}</div></div><button class="btn icon ghost" data-dclose="1"><i data-lucide="x"></i></button></div>
  <div class="dbody">${body}</div>
  <div class="dfoot"><span class="push"></span><button class="btn" data-dclose="1">Cancel</button><button class="btn primary" id="drawer-save"><i data-lucide="save"></i>Save</button></div></div>`;
 icons();
 $$('#drawer-root [data-dclose]').forEach(b=>b.addEventListener('click',closeDrawer));
 const refs=onMount?onMount():{};
 $('#drawer-save').addEventListener('click',()=>{if(onSave(refs)!==false)closeDrawer()});
 return refs;
}

/* ===== TAG INPUT ===== */
function tagInput(box,vals,sugs,opts={}){
 box.classList.add('tagbox');
 function draw(){
  box.innerHTML=vals.map((v,i)=>`<span class="tag"><span>${esc(v)}</span><button class="tx" data-i="${i}" type="button"><i data-lucide="x"></i></button></span>`).join('')+`<input class="tag-in" placeholder="${esc(opts.ph||'Add...')}">`;
  icons();
  const inp=box.querySelector('.tag-in');
  inp.addEventListener('keydown',e=>{
   if((e.key==='Enter'||e.key===',')&&inp.value.trim()){e.preventDefault();add(titleCase(inp.value.trim()))}
   else if(e.key==='Backspace'&&!inp.value&&vals.length){vals.pop();draw();notify()}
  });
  inp.addEventListener('input',()=>sugs2(inp.value));
 }
 function add(v){if(opts.single)vals.length=0;if(!vals.includes(v))vals.push(v);draw();notify()}
 function notify(){opts.onChange&&opts.onChange(vals.slice())}
 function sugs2(q){
  $$('.sugs',box.parentElement).forEach(d=>d.remove());
  if(!q)return;
  const list=(sugs||[]).filter(s=>s.toLowerCase().includes(q.toLowerCase())&&!vals.includes(s)).slice(0,6);
  if(!list.length)return;
  const d=document.createElement('div');d.className='sugs';
  d.innerHTML=list.map(s=>`<button class="sug" type="button">${esc(s)}</button>`).join('');
  $$('button',d).forEach(b=>b.addEventListener('click',()=>{add(b.textContent);d.remove()}));
  box.parentElement.appendChild(d);
 }
 box.addEventListener('click',e=>{const tx=e.target.closest('.tx');if(tx){vals.splice(+tx.dataset.i,1);draw();notify()}});
 draw();
 return {get:()=>vals.slice(),set:nv=>{vals.length=0;vals.push(...(nv||[]));draw();notify()},
  // Text typed into the box but never committed (no Enter/comma/suggestion click)
  // is still in the input, not in vals — commit it so a Save can't drop it.
  flush(){const inp=box.querySelector('.tag-in');if(!inp||!inp.value.trim())return false;add(titleCase(inp.value.trim()));return true}};
}
/* ===== CATEGORY PICKER ===== */
function openCategoryPicker(selected,onApply){
 const sel=new Set(selected);
 const MANY=12,POPN=8;
 const chip=c=>`<button type="button" class="chip ${sel.has(c.name)?'on':''}" data-cat="${esc(c.name)}">${esc(c.name)}</button>`;
 const s={title:'Select Categories',html:()=>`
  <input class="field" id="cp-q" placeholder="Search Or Create Category..." style="margin-bottom:12px">
  <div class="cplist" id="cp-list"></div>`,
  footer:()=>`<span class="push"></span><button class="btn" data-mclose="1">Cancel</button><button class="btn primary" id="cp-ok"><i data-lucide="check"></i>Apply</button>`,
  mount(b,f){
   const q=$('#cp-q'),list=$('#cp-list');
   const draw=()=>{
    const query=q.value.trim().toLowerCase();
    if(query){
     const items=DB.categories.filter(c=>c.name.toLowerCase().includes(query)).sort((a,b)=>a.name.localeCompare(b.name));
     list.innerHTML=items.map(chip).join('')
      +(query&&!DB.categories.some(c=>c.name.toLowerCase()===query)?`<div style="margin-top:12px"><button type="button" class="chip" id="cp-create"><i data-lucide="plus" style="width:11px;height:11px"></i> Create "${esc(titleCase(query))}"</button></div>`:'');
    }else{
     const byAlpha=[...DB.categories].sort((a,b)=>a.name.localeCompare(b.name));
     if(DB.categories.length>MANY){
      const popular=[...DB.categories].sort((a,b)=>catUsage(b)-catUsage(a)||a.name.localeCompare(b.name)).slice(0,POPN);
      list.innerHTML=`<div class="flab" style="margin:0 0 8px">Popular</div><div class="chiprow" style="margin-bottom:16px">${popular.map(chip).join('')}</div><div class="flab" style="margin:0 0 8px">All Categories</div><div class="chiprow">${byAlpha.map(chip).join('')}</div>`;
     }else{
      list.innerHTML=`<div class="chiprow">${byAlpha.map(chip).join('')}</div>`;
     }
    }
    icons();
    $$('[data-cat]',list).forEach(ch=>ch.addEventListener('click',()=>{const n=ch.dataset.cat;sel.has(n)?sel.delete(n):sel.add(n);ch.classList.toggle('on')}));
    const cr=$('#cp-create',list);
    cr&&cr.addEventListener('click',()=>{
     const n=titleCase(query);
     if(!DB.categories.some(c=>c.name.toLowerCase()===n.toLowerCase())){const c={id:uid('c'),name:n,icon:'tag',desc:''};DB.categories.push(c);Sync.push('categories','create',c)}
     sel.add(n);q.value='';draw();
    });
   };
   q.addEventListener('input',draw);draw();
   setTimeout(()=>q.focus(),50);
   $('#cp-ok',f).addEventListener('click',()=>{onApply([...sel]);closeModal()});
  }};
 openModal([s],0,560);
}
/* ===== STUDIO PICKER ===== */
function openStudioPicker(selected,onApply){
 const sel=new Set(selected);
 const chip=c=>`<button type="button" class="chip ${sel.has(c.name)?'on':''}" data-st="${esc(c.name)}">${esc(c.name)}</button>`;
 const s={title:'Select Studio',html:()=>`
  <input class="field" id="sp-q" placeholder="Search Or Create Studio..." style="margin-bottom:12px">
  <div class="cplist" id="sp-list"></div>`,
  footer:()=>`<span class="push"></span><button class="btn" data-mclose="1">Cancel</button><button class="btn primary" id="sp-ok"><i data-lucide="check"></i>Apply</button>`,
  mount(b,f){
   const q=$('#sp-q'),list=$('#sp-list');
   const draw=()=>{
    const query=q.value.trim().toLowerCase();
    if(query){
     const items=DB.studios.filter(c=>c.name.toLowerCase().includes(query)).sort((a,b)=>a.name.localeCompare(b.name));
     list.innerHTML=items.map(chip).join('')
      +(query&&!DB.studios.some(c=>c.name.toLowerCase()===query)?`<div style="margin-top:12px"><button type="button" class="chip" id="sp-create"><i data-lucide="plus" style="width:11px;height:11px"></i> Create "${esc(titleCase(query))}"</button></div>`:'');
    }else{
     const byAlpha=[...DB.studios].sort((a,b)=>a.name.localeCompare(b.name));
     list.innerHTML=`<div class="chiprow">${byAlpha.map(chip).join('')}</div>`;
    }
    icons();
    $$('[data-st]',list).forEach(ch=>ch.addEventListener('click',()=>{sel.clear();sel.add(ch.dataset.st);$$('[data-st]',list).forEach(c=>c.classList.remove('on'));ch.classList.toggle('on')}));
    const cr=$('#sp-create',list);
    cr&&cr.addEventListener('click',()=>{
     const n=titleCase(query);
     if(!DB.studios.some(c=>c.name.toLowerCase()===n.toLowerCase())){const c={id:uid('st'),name:n,url:'',country:'',desc:'',logo:'',twitter:null,instagram:null};DB.studios.push(c);Sync.push('studios','create',c)}
     sel.clear();sel.add(n);q.value='';draw();
    });
   };
   q.addEventListener('input',draw);draw();
   setTimeout(()=>q.focus(),50);
   $('#sp-ok',f).addEventListener('click',()=>{onApply([...sel]);closeModal()});
  }};
 openModal([s],0,560);
}
/* ===== ACTOR PICKER ===== */
function openActorPicker(selected,onApply){
 const sel=new Set(selected);
 const chip=c=>`<button type="button" class="chip ${sel.has(c.name)?'on':''}" data-ac="${esc(c.name)}">${esc(c.name)}</button>`;
 const s={title:'Select Actors',html:()=>`
  <input class="field" id="ap-q" placeholder="Search Or Create Actor..." style="margin-bottom:12px">
  <div class="cplist" id="ap-list"></div>`,
  footer:()=>`<span class="push"></span><button class="btn" data-mclose="1">Cancel</button><button class="btn primary" id="ap-ok"><i data-lucide="check"></i>Apply</button>`,
  mount(b,f){
   const q=$('#ap-q'),list=$('#ap-list');
   const draw=()=>{
    const query=q.value.trim().toLowerCase();
    if(query){
     const items=DB.performers.filter(c=>c.name.toLowerCase().includes(query)).sort((a,b)=>a.name.localeCompare(b.name));
     list.innerHTML=items.map(chip).join('')
      +(query&&!DB.performers.some(c=>c.name.toLowerCase()===query)?`<div style="margin-top:12px"><button type="button" class="chip" id="ap-create"><i data-lucide="plus" style="width:11px;height:11px"></i> Create "${esc(titleCase(query))}"</button></div>`:'');
    }else{
     const byAlpha=[...DB.performers].sort((a,b)=>a.name.localeCompare(b.name));
     list.innerHTML=`<div class="chiprow">${byAlpha.map(chip).join('')}</div>`;
    }
    icons();
    $$('[data-ac]',list).forEach(ch=>ch.addEventListener('click',()=>{sel.has(ch.dataset.ac)?sel.delete(ch.dataset.ac):sel.add(ch.dataset.ac);ch.classList.toggle('on')}));
    const cr=$('#ap-create',list);
    cr&&cr.addEventListener('click',()=>{
     const n=titleCase(query);
     if(!DB.performers.some(c=>c.name.toLowerCase()===n.toLowerCase())){const c={id:uid('p'),name:n,gender:'f',photo:img('perf-'+slug(n),600,800)};DB.performers.push(c);Sync.push('performers','create',c)}
     sel.add(n);q.value='';draw();
    });
   };
   q.addEventListener('input',draw);draw();
   setTimeout(()=>q.focus(),50);
   $('#ap-ok',f).addEventListener('click',()=>{onApply([...sel]);closeModal()});
  }};
 openModal([s],0,560);
}
/* ===== POSTER / COVER SLOT ===== */
function bindSlot(rootId,ratio,initial){
 const root=document.getElementById(rootId);
 root.innerHTML=`<div class="slot-prev ${ratio}">${initial?`<img src="${esc(initial)}" alt="">`:'<span class="slot-empty">Empty</span>'}</div>
  <div class="slot-row"><button class="btn sm" type="button" data-b="file"><i data-lucide="hard-drive-upload"></i>Local</button><input class="field" data-b="url" placeholder="https://... URL" value="${/^https?:/.test(initial||'')?esc(initial):''}"></div>
  <input type="file" accept="image/*" data-b="filein" style="display:none">`;
 let cur=initial||'';
 const prev=$('.slot-prev',root),urlIn=$('[data-b=url]',root),fin=$('[data-b=filein]',root);
 function setVal(v){cur=v;prev.classList.toggle('filled',!!v);prev.innerHTML=v?`<img src="${esc(v)}" alt="">`:'<span class="slot-empty">Empty</span>';if(String(v).startsWith('enc://'))hydrateEncImages(root)}
 function localRead(f){
  if(settings.imgProt&&settings.imgProt.on&&HAS_SUBTLE){
   const r=new FileReader();
   r.onload=async()=>{
    const enc=await encryptLocalFile(r.result,f.type);
    if(enc){
     const id='i'+(++_seq)+Math.random().toString(36).slice(2,6);
     encStore[id]=enc;saveEncStore();
     setVal('enc://'+id);
     toast('Image Stored Encrypted','shield');
    }else toast('Image Not Stored - Image Protection Passphrase Required','alert-triangle');
   };
   r.readAsArrayBuffer(f);
  }else{
   const r=new FileReader();r.onload=()=>setVal(r.result);r.readAsDataURL(f);
  }
 }
 $('[data-b=file]',root).addEventListener('click',()=>fin.click());
 fin.addEventListener('change',()=>{
  const f=fin.files[0];if(!f)return;
  if(Sync.on){
   const fd=new FormData();fd.append('file',f,f.name);
   fetch('/api/images',{method:'POST',body:fd})
    .then(r=>{if(!r.ok)throw 0;return r.json()})
    .then(j=>{if(j&&j.url)setVal(j.url);else localRead(f)})
    .catch(()=>localRead(f));
   return;
  }
  localRead(f);
 });
 urlIn.addEventListener('change',()=>{if(urlIn.value.trim())setVal(urlIn.value.trim())});
 return {get:()=>cur,set:v=>{setVal(v);if(/^https?:/.test(v||''))urlIn.value=v}};
}
function wireFetchToggle(refs,titleEl){
 const upd=()=>refs.fetchBtn.classList.toggle('hide',!(titleEl.value.trim()&&refs.getStudio().trim()));
 titleEl.addEventListener('input',upd);
 refs.updFetch=upd;
 upd();
}

/* ===== DATA SOURCES / SCRAPERS ===== */
function parseSourceName(url){
 try{const u=new URL(url.startsWith('http')?url:'https://'+url);return u.hostname.replace(/^www\./,'')}catch(e){return url.slice(0,32)}
}
function detectStructure(html){
 const out={detected:[],title:null,poster:null,desc:null};
 const grab=re=>{const m=re.exec(html);return m?m[1].trim():null};
 out.title=grab(/<meta[^>]+property=["']og:title["'][^>]+content=["']([^"']+)/i)||grab(/<title[^>]*>([^<]{2,150})<\/title>/i);
 out.poster=grab(/<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)/i);
 out.desc=grab(/<meta[^>]+property=["']og:description["'][^>]+content=["']([^"']+)/i)||grab(/<meta[^>]+name=["']description["'][^>]+content=["']([^"']+)/i);
 if(/<h1[^>]*class=["'][^"']*(title|name)[^"']*["']/i.test(html))out.detected.push('H1 Title Block');
 if(/itemprop="(name|actor|director)"/i.test(html))out.detected.push('Schema.org Microdata');
 if(/application\/ld\+json/i.test(html))out.detected.push('JSON-LD Structured Data');
 if(/class=["'][^"']*(poster|cover|thumb)[^"']*["']/i.test(html))out.detected.push('Poster / Cover Class');
 if(/class=["'][^"']*(cast|actor|performer)[^"']*["']/i.test(html))out.detected.push('Cast List');
 if(/data-(original|src|lazy)[-=]/i.test(html))out.detected.push('Lazy-Loaded Images');
 return out;
}
