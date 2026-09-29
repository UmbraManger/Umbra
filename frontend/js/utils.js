"use strict";
/* ===== UTILS ===== */
const $=(s,c=document)=>c.querySelector(s);
const $$=(s,c=document)=>[...c.querySelectorAll(s)];
const esc=s=>String(s??'').replace(/[&<>"]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]));
const img=(seed,w,h)=>`https://picsum.photos/seed/${encodeURIComponent(seed)}/${w}/${h}.jpg`;
const slug=s=>String(s).toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/(^-|-$)/g,'');
let _seq=0;const uid=p=>p+'-'+(++_seq)+'-'+Math.random().toString(36).slice(2,5);
const pad=n=>String(Math.floor(n)).padStart(2,'0');
const fmtDur=m=>{if(!m)return '-';const h=Math.floor(m/60);return h?`${h}h ${pad(m%60)}m`:`${m}m`};
const fmtTime=s=>{s=Math.max(0,s|0);const h=Math.floor(s/3600),m=Math.floor(s%3600/60);return h?`${h}:${pad(m)}:${pad(s%60)}`:`${m}:${pad(s%60)}`};
const fmtDate=s=>{if(!s)return '-';const d=new Date(s+'T00:00:00');return isNaN(d)?s:d.toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'})};
const ageOf=b=>{if(!b)return null;const a=Math.floor((Date.now()-new Date(b))/31557600000);return a>=0&&a<120?a:null};
const ftIn=cm=>`${Math.floor(cm/30.48)}′${Math.round(cm/2.54%12)}′′`;
const fmtBytes=b=>{if(b<1024)return Math.round(b)+' B';if(b<1048576)return (b/1024).toFixed(1)+' KB';return (b/1048576).toFixed(2)+' MB'};
const titleCase=s=>String(s??'').replace(/\w\S*/g,w=>w[0].toUpperCase()+w.slice(1).toLowerCase());
function hashStr(s){let h=7;for(const c of String(s))h=(h*31+c.charCodeAt(0))|0;return Math.abs(h)}
function mulberry32(a){return function(){a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296}}
function icons(){try{window.lucide&&lucide.createIcons({attrs:{'stroke-width':1.8}})}catch(e){}
 if(document.body&&document.body.dataset.booted&&typeof hydrateEncImages==='function')hydrateEncImages(document);}
function toast(msg,icon='check'){const d=document.createElement('div');d.className='toast';d.innerHTML=`<i data-lucide="${icon}"></i><span>${esc(msg)}</span>`;$('#toast-root').appendChild(d);icons();setTimeout(()=>{d.classList.add('out');setTimeout(()=>d.remove(),260)},3200)}
async function sha256(s){
 try{
  const b=await crypto.subtle.digest('SHA-256',new TextEncoder().encode('obscura::'+s));
  return [...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,'0')).join('');
 }catch(e){
  let h=5381;for(let i=0;i<7;i++){for(const c of String(s)+i)h=((h<<5)+h+c.charCodeAt(0))|0}
  return 'fb'+Math.abs(h).toString(16).padStart(14,'0');
 }
}

/* ===== ADVANCED APPEARANCE ===== */
function inkFor(hex){
 const n=parseInt(hex.slice(1),16);
 const r=(n>>16&255),g=(n>>8&255),b=(n&255);
 const L=(0.299*r+0.587*g+0.114*b)/255;
 return L>0.6?'#1c1408':'#fff6e0';
}
function colorMix(hex,f){
 const n=parseInt(hex.slice(1),16);
 let r=(n>>16&255),g=(n>>8&255),b=(n&255);
 if(f<0){r*=(1+f);g*=(1+f);b*=(1+f)}
 else{r+=(255-r)*f;g+=(255-g)*f;b+=(255-b)*f}
 return '#'+[r,g,b].map(v=>Math.round(Math.max(0,Math.min(255,v))).toString(16).padStart(2,'0')).join('');
}
function applyAdvanced(){
 const a=settings.adv||{};
 const s=document.documentElement.style;
 if(a.accent){
  s.setProperty('--accent',a.accent);
  s.setProperty('--accent-ink',inkFor(a.accent));
 }else{
  s.removeProperty('--accent');
  s.removeProperty('--accent-ink');
 }
 if(a.background){
  s.setProperty('--bg',a.background);
  s.setProperty('--bg2',colorMix(a.background,-0.06));
  s.setProperty('--surface',colorMix(a.background,0.04));
  s.setProperty('--surface2',colorMix(a.background,0.07));
 }else{
  ['--bg','--bg2','--surface','--surface2'].forEach(v=>s.removeProperty(v));
 }
 s.setProperty('--radius',(a.radius??12)+'px');
 s.setProperty('--bw',({'0':'0px','1':'1px','2':'2px'})[a.border||'1']||'1px');
 const fonts={
  grotesk:'"Space Grotesk",sans-serif',
  system:'system-ui,-apple-system,"Segoe UI",Roboto,sans-serif',
  mono:'"JetBrains Mono",monospace',
  serif:'Georgia,"Times New Roman",serif'
 };
 s.setProperty('--font-main',fonts[a.font||'grotesk']);
}

/* ===== IMAGE PROTECTION ===== */
const HAS_SUBTLE=!!(window.crypto&&crypto.subtle&&crypto.subtle.deriveKey);
let encKey=null,encPending=null;
const encStore=(()=>{try{return JSON.parse(localStorage.getItem('obscura:encimgs')||'{}')}catch(e){return {}}})();
const activeURLs=[];
function saveEncStore(){try{localStorage.setItem('obscura:encimgs',JSON.stringify(encStore))}catch(e){toast('Local Storage Is Full - Encrypted Image Not Persisted','alert-triangle')}}
const b2h=b=>[...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,'0')).join('');
const h2b=h=>new Uint8Array(h.match(/../g).map(x=>parseInt(x,16)));
async function deriveKey(pass,saltHex){
 const km=await crypto.subtle.importKey('raw',new TextEncoder().encode(pass),'PBKDF2',false,['deriveKey']);
 return crypto.subtle.deriveKey({name:'PBKDF2',salt:h2b(saltHex),iterations:150000,hash:'SHA-256'},km,{name:'AES-GCM',length:256},false,['encrypt','decrypt']);
}
async function ensureKey(){
 if(encKey)return encKey;
 if(!settings.imgProt||!settings.imgProt.on||!settings.imgProt.hash)return null;
 if(encPending)return encPending;
 encPending=new Promise(res=>{
  openModal([{title:'Image Protection - Passphrase',html:()=>`
   <div class="cmsg" style="margin-bottom:12px">Enter The Image Protection Passphrase To View Protected Images.</div>
   <input class="field" id="ip-pass" type="password" placeholder="Passphrase">`,
   footer:()=>`<span class="push"></span><button class="btn primary" id="ip-ok"><i data-lucide="unlock"></i>Unlock</button>`,
   mount(b,f){
    const inp=$('#ip-pass');setTimeout(()=>inp.focus(),50);
    const go=async()=>{
     const chk=await sha256(inp.value);
     if(chk!==settings.imgProt.hash){inp.classList.add('err');toast('Wrong Passphrase','alert-triangle');return}
     encKey=await deriveKey(inp.value,settings.imgProt.salt);
     closeModal();res(encKey);hydrateEncImages(document);
    };
    $('#ip-ok',f).addEventListener('click',go);
    inp.addEventListener('keydown',e=>{if(e.key==='Enter')go()});
   }}],0,460);
 }).finally(()=>{encPending=null});
 return encPending;
}
async function encryptLocalFile(buf,mime){
 if(!HAS_SUBTLE)return null;
 const k=await ensureKey();if(!k)return null;
 const iv=crypto.getRandomValues(new Uint8Array(12));
 const ct=new Uint8Array(await crypto.subtle.encrypt({name:'AES-GCM',iv},k,buf));
 return {iv:b2h(iv),data:b2h(ct),t:mime||'image/jpeg'};
}
async function encToObjectURL(id){
 const rec=encStore[id];if(!rec)return null;
 const k=await ensureKey();if(!k)return null;
 try{
  const pt=await crypto.subtle.decrypt({name:'AES-GCM',iv:h2b(rec.iv)},k,h2b(rec.data));
  const url=URL.createObjectURL(new Blob([pt],{type:rec.t||'image/jpeg'}));
  activeURLs.push(url);
  return url;
 }catch(e){return null}
}
function encBytes(){let n=0;for(const id in encStore){const r=encStore[id];n+=(r.iv.length+r.data.length)/2}return n}
function clearImageCache(rehydrate){
 activeURLs.splice(0).forEach(u=>{try{URL.revokeObjectURL(u)}catch(e){}});
 encKey=null;
 if(rehydrate&&settings.imgProt&&settings.imgProt.on)hydrateEncImages(document);
}
const hydrating=new Set();
function hydrateEncImages(root){
 const imgs=$$('img[src^="enc://"]',root);
 if(!imgs.length)return;
 [...new Set(imgs.map(im=>im.getAttribute('src').slice(5)))].forEach(id=>{
  if(hydrating.has(id))return;
  hydrating.add(id);
  encToObjectURL(id).then(url=>{
   $$(`img[src="enc://${id}"]`,document).forEach(im=>{
    if(url)im.src=url;else im.removeAttribute('src');
   });
  }).finally(()=>setTimeout(()=>hydrating.delete(id),50));
 });
}
