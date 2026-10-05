"use strict";
/* ===== PLAYER ===== */
const RES_OPTS=['4K (2160p)','1080p (FHD)','720p (HD)'];
const AUDIO_POOL=['English 5.1','English Stereo','Japanese 2.0','Director\u2019s Commentary'];
const SUB_POOL=['English','English (SDH)','Spanish'];
const SUB_LINES=['( Soft Ambient Music )','- You Came Back.','- I Never Left.','( Door Creaks )','- Give Me One Reason To Stay.','- The Night Is Still Young.','( Distant Thunder )','- Then Stay. Just For Tonight.'];
function mediaInfo(item,kind){
 const r=mulberry32(hashStr(kind+'::'+item.id));
 const codec=r()<0.5?'x265 / HEVC':'x264 / AVC';
 const res=RES_OPTS[Math.floor(r()*RES_OPTS.length)];
 const audio=AUDIO_POOL.slice(0,1+Math.floor(r()*3));
 const subs=SUB_POOL.slice(0,Math.floor(r()*3));
 return {codec,res,audio,subs};
}
function rawImg(src){return new Promise(res=>{const i=new Image();i.onload=()=>res(i);i.onerror=()=>res(null);i.src=src})}
function loadImg(src){
 if(String(src).startsWith('enc://'))return encToObjectURL(src).then(u=>u?rawImg(u):null);
 return rawImg(src);
}
function playerSrcs(item,kind){
 if(kind==='movie')return [item.posterB,item.posterF];
 const c=[...(item.covers||[])].filter(Boolean);
 if(c.length>=2&&c[0]===c[1])c.length=1;
 if(c.length<=1)return c;
 const ti=Math.min(item.thumb||0,c.length-1);
 return [c[1-ti]];
}
function drawGlued(cx,W,H,imgs,progressFrac){
 cx.fillStyle='#070604';cx.fillRect(0,0,W,H);
 const valid=imgs.filter(Boolean);
 if(!valid.length){cx.fillStyle='#6e6450';cx.font='16px JetBrains Mono, monospace';cx.textAlign='center';cx.fillText('No Thumbnail',W/2,H/2);cx.textAlign='left';return}
 const per=W/valid.length;
 valid.forEach((im,i)=>{
  const r=Math.max(per/im.width,H/im.height),dw=im.width*r,dh=im.height*r;
  cx.save();cx.beginPath();cx.rect(i*per,0,per,H);cx.clip();
  cx.drawImage(im,i*per+(per-dw)/2,(H-dh)/2,dw,dh);cx.restore();
 });
 if(progressFrac>0){
  const accent=getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()||'#e0a43e';
  const bh=Math.max(3,Math.round(H*0.012));
  cx.fillStyle='rgba(255,255,255,.18)';cx.fillRect(0,H-bh,W,bh);
  cx.fillStyle=accent;cx.fillRect(0,H-bh,W*progressFrac,bh);
 }
}
function playerHTML(par){
 return `<div class="player" style="--par:${par}"><div class="p-stage"><canvas></canvas><div class="p-subs" data-p="subsbox"></div><button class="p-big" aria-label="Play"><i data-lucide="play"></i></button></div>
  <div class="p-menu" hidden></div>
  <div class="p-bar"><button class="btn icon" data-p="skip-back" title="-10s"><i data-lucide="rewind"></i></button>
   <button class="btn icon" data-p="play"><i data-lucide="play"></i></button>
   <button class="btn icon" data-p="skip-fwd" title="+10s"><i data-lucide="fast-forward"></i></button>
   <div class="p-seek"><input type="range" data-p="seek" value="0"><div class="p-pop"><canvas></canvas><div class="p-pt" data-p="pt">0:00</div></div></div>
   <span class="p-time mono" data-p="cur">0:00 / 0:00</span>
   <button class="btn icon" data-p="mute" data-on="1" title="Mute"><i data-lucide="volume-2"></i></button>
   <button class="btn icon" data-p="subs" title="Subtitles"><i data-lucide="captions"></i></button>
   <button class="btn icon" data-p="audio" title="Audio Track"><i data-lucide="languages"></i></button>
   <button class="btn icon" data-p="quality" title="Quality"><i data-lucide="monitor"></i></button>
   <button class="btn icon" data-p="fs" title="Fullscreen"><i data-lucide="maximize"></i></button></div></div>`;
}
function realPlayerHTML(par,item,kind){
  const src=`/api/media/${kind}/${item.id}`;
  const resumed=Positions.get(kind,item.id)>5;
  if(kind==='movie'){
   const a=item.posterF||'',b=item.posterB||'';
   const showCover=(a||b)&&!resumed;
   const posters=showCover?`<div class="p-poster-pair">${b?`<img class="p-poster" src="${esc(b)}" alt="">`:''}${a&&a!==b?`<img class="p-poster" src="${esc(a)}" alt="">`:''}</div>`:'';
   return `<div class="player" style="--par:${par}"><div class="p-stage"><video preload="metadata" playsinline style="aspect-ratio:${par}" src="${src}"></video>${posters}<button class="p-big" aria-label="Play"><i data-lucide="play"></i></button></div>
   <div class="p-menu" hidden></div>
   <div class="p-bar"><button class="btn icon" data-p="skip-back" title="-10s"><i data-lucide="rewind"></i></button>
    <button class="btn icon" data-p="play"><i data-lucide="play"></i></button>
    <button class="btn icon" data-p="skip-fwd" title="+10s"><i data-lucide="fast-forward"></i></button>
    <div class="p-seek"><input type="range" data-p="seek" value="0"></div>
    <span class="p-time mono" data-p="cur">0:00 / 0:00</span>
    <button class="btn icon" data-p="mute" data-on="1" title="Mute"><i data-lucide="volume-2"></i></button>
    <button class="btn icon" data-p="subs" title="Subtitles"><i data-lucide="captions"></i></button>
    <button class="btn icon" data-p="audio" title="Audio Track"><i data-lucide="languages"></i></button>
    <button class="btn icon" data-p="quality" title="Quality"><i data-lucide="monitor"></i></button>
    <button class="btn icon" data-p="fs" title="Fullscreen"><i data-lucide="maximize"></i></button></div></div>`;
  }
  const covers=(item.covers||[]).filter((v,i,a)=>v&&(i===0||v!==a[0]));
  const ti=Math.min(item.thumb||0,Math.max(0,covers.length-1));
  const poster=covers.length>1?covers[1-ti]:(covers[0]||'');
  const showCover=poster&&!resumed;
  return `<div class="player" style="--par:${par}"><div class="p-stage"><video preload="metadata" playsinline style="aspect-ratio:${par}" src="${src}"></video>${showCover?`<img class="p-poster" src="${esc(poster)}" alt="" style="display:block">`:''}<button class="p-big" aria-label="Play"><i data-lucide="play"></i></button></div>
   <div class="p-menu" hidden></div>
   <div class="p-bar"><button class="btn icon" data-p="skip-back" title="-10s"><i data-lucide="rewind"></i></button>
    <button class="btn icon" data-p="play"><i data-lucide="play"></i></button>
    <button class="btn icon" data-p="skip-fwd" title="+10s"><i data-lucide="fast-forward"></i></button>
    <div class="p-seek"><input type="range" data-p="seek" value="0"></div>
    <span class="p-time mono" data-p="cur">0:00 / 0:00</span>
    <button class="btn icon" data-p="mute" data-on="1" title="Mute"><i data-lucide="volume-2"></i></button>
    <button class="btn icon" data-p="subs" title="Subtitles"><i data-lucide="captions"></i></button>
    <button class="btn icon" data-p="audio" title="Audio Track"><i data-lucide="languages"></i></button>
    <button class="btn icon" data-p="quality" title="Quality"><i data-lucide="monitor"></i></button>
    <button class="btn icon" data-p="fs" title="Fullscreen"><i data-lucide="maximize"></i></button></div></div>`;
 }
function mountRealPlayer(host,item,kind){
  const stage=$('.p-stage',host),vid=$('video',stage),big=$('.p-big',host),btnPlay=$('[data-p=play]',host);
  const seek=$('[data-p=seek]',host),tCur=$('[data-p=cur]',host),menuEl=$('.p-menu',host);
  let menuType=null,curAudio=0,info={available:false,audio:[],subs:[]};
  const resLabel=h=>h>=2160?'4K (2160p)':h>=1080?'1080p (FHD)':h>=720?'720p (HD)':h+'p';
  const isMovie=kind==='movie';
  const posterA=isMovie?(item.posterF||''):(item.covers||[]).filter((v,i,a)=>i===0||v!==a[0])[1]||(item.covers||[])[0]||'';
  const posterB=isMovie?(item.posterB||''):'';
  const hasPair=isMovie&&(posterA||posterB);
  function removePoster(){
   const pair=$('.p-poster-pair',stage);
   if(pair){
    pair.classList.add('hide');
    pair.addEventListener('transitionend',()=>{if(pair.classList.contains('hide'))pair.remove()},{once:true});
   }
   const el=$('.p-poster',stage);if(!el||el.classList.contains('hide'))return;
   el.classList.add('hide');
   el.addEventListener('transitionend',()=>{if(el.classList.contains('hide'))el.remove()},{once:true});
  }
  function showPoster(instant){
   if(hasPair){
    const existing=$('.p-poster-pair',stage);
    if(existing){
     if(instant){
      const prev=existing.style.transition;
      existing.style.transition='none';
      existing.classList.remove('hide');
      void existing.offsetWidth;
      existing.style.transition=prev;
     }else existing.classList.remove('hide');
     return;
    }
    const div=document.createElement('div');
    div.className='p-poster-pair'+(instant?'':' hide');
    if(posterA)div.innerHTML+=`<img class="p-poster" src="${esc(posterA)}" alt="">`;
    if(posterB&&posterB!==posterA)div.innerHTML+=`<img class="p-poster" src="${esc(posterB)}" alt="">`;
    stage.insertBefore(div,stage.firstChild);
    if(!instant)requestAnimationFrame(()=>requestAnimationFrame(()=>div.classList.remove('hide')));
    return;
   }
   if(!posterA)return;
   const existing=$('.p-poster',stage);
   if(existing){
    if(instant){
     const prev=existing.style.transition;
     existing.style.transition='none';
     existing.classList.remove('hide');
     void existing.offsetWidth;
     existing.style.transition=prev;
    }else existing.classList.remove('hide');
    return;
   }
   const img=document.createElement('img');
   img.className='p-poster'+(instant?'':' hide');
   img.src=posterA;img.alt='';
   stage.insertBefore(img,stage.firstChild);
   if(!instant)requestAnimationFrame(()=>requestAnimationFrame(()=>img.classList.remove('hide')));
  }
  function setPlaying(p){
    stage.classList.toggle('playing',p);
    btnPlay.innerHTML=`<i data-lucide="${p?'pause':'play'}"></i>`;icons();
    if(p){removePoster();vid.play().catch(()=>setPlaying(false))}
    else vid.pause();
   }
  function updateBar(){
   if(vid.duration&&isFinite(vid.duration)){
    seek.max=vid.duration;seek.value=vid.currentTime;
    tCur.textContent=fmtTime(vid.currentTime)+' / '+fmtTime(vid.duration);
   }
  }
  function renderMenu(){
   if(!menuType){menuEl.hidden=true;return}
   menuEl.hidden=false;
   const row=(k,v,sel)=>`<button class="pm-i ${sel?'on':''}" data-k="${k}" data-v="${esc(v)}"><span>${esc(v)}</span>${sel?'<i data-lucide="check"></i>':''}</button>`;
   if(menuType==='subs'){
    const tracks=[...vid.textTracks].filter(t=>t.kind==='subtitles');
    let html='<div class="pm-t">Subtitles</div>'+row('subs','Off',!tracks.some(t=>t.mode==='showing'));
    tracks.forEach(t=>{html+=row('subs',t.label||'Subtitle',t.mode==='showing')});
    menuEl.innerHTML=html+((info.subs||[]).length?'':`<div class="pm-t" style="letter-spacing:0">No Sidecar Subtitle Files Found Next To The Video</div>`);
   }else if(menuType==='audio'){
    let html='<div class="pm-t">Audio Track</div>';
    if((info.audio||[]).length>1){
     info.audio.forEach((a,i)=>{const lbl=[a.lang,a.title,a.codec].filter(Boolean).join(' · ')||('Track '+(i+1));html+=row('audio',lbl,i===curAudio)});
     html+=`<div class="pm-t">Track Switching Depends On Your Browser's Codec Support</div>`;
    }else{
     html+=row('audio','Default Track',true,true)
      +`<div class="pm-t">Single Audio Track${(info.audio||[]).length?' · '+esc((info.audio||[])[0]?.codec||''):''}</div>`;
    }
    menuEl.innerHTML=html;
   }else{
    let html='<div class="pm-t">Quality</div>';
    if(info.height)html+=row('quality',resLabel(info.height)+' · '+esc((info.vcodec||'').toUpperCase()),true,true);
    html+=`<div class="pm-t">${info.available?'Single Source File - No Alternate Encodes':'Install FFmpeg For Real Source Details'}</div>`;
    menuEl.innerHTML=html;
   }
   icons();
  }
  big.addEventListener('click',e=>{
   e.stopPropagation();
   if(settings.player==='external'){
    fetch(`/api/media/${kind}/${item.id}/open`,{method:'POST'})
     .then(()=>toast('Opened In OS Default Player','external-link'))
     .catch(()=>toast('Could Not Open Externally','alert-triangle'));
    return;
   }
   setPlaying(vid.paused);
  });
  stage.addEventListener('click',e=>{if(!e.target.closest('.p-big'))setPlaying(vid.paused)});
  btnPlay.addEventListener('click',()=>setPlaying(vid.paused));
  $('[data-p=skip-back]',host).addEventListener('click',()=>{vid.currentTime=Math.max(0,vid.currentTime-10)});
  $('[data-p=skip-fwd]',host).addEventListener('click',()=>{vid.currentTime=Math.min(vid.duration||0,vid.currentTime+10)});
  vid.addEventListener('playing',()=>{setPlaying(true);removePoster()});
  vid.addEventListener('pause',()=>{
   if(!vid.ended){
    setPlaying(false);
    if(vid.currentTime>3)Positions.saveNow(kind,item.id,vid.currentTime);
   }
  });
  function revealFrame(){
   if(vid.readyState<2){vid.addEventListener('loadeddata',revealFrame,{once:true});return}
   requestAnimationFrame(()=>requestAnimationFrame(removePoster));
  }
  vid.addEventListener('seeked',()=>{
   if(!vid.paused)return;
   if(vid.currentTime<=1)showPoster();
   else revealFrame();
  });
  vid.addEventListener('ended',()=>{setPlaying(false);showPoster(true);vid.currentTime=0;});
  let lastSave=0,posCleared=false;
  vid.addEventListener('timeupdate',()=>{
   updateBar();
   if(vid.duration&&vid.currentTime>vid.duration-15){
    if(!posCleared){posCleared=true;Positions.clear(kind,item.id)}
   }else{
    posCleared=false;
    if(Math.abs(vid.currentTime-lastSave)>=5){lastSave=vid.currentTime;Positions.save(kind,item.id,vid.currentTime)}
   }
  });
  vid.addEventListener('loadedmetadata',()=>{
   updateBar();
   const saved=Positions.get(kind,item.id);
   if(saved>5&&vid.duration&&saved<vid.duration-15){
    vid.currentTime=saved;
    toast('Resumed From '+fmtTime(saved),'history');
   }
  });
  window.addEventListener('pagehide',()=>{if(vid.currentTime>3&&!vid.ended)Positions.saveNow(kind,item.id,vid.currentTime)});
  window.addEventListener('beforeunload',()=>{if(vid.currentTime>3&&!vid.ended)Positions.saveNow(kind,item.id,vid.currentTime)});
  vid.addEventListener('error',()=>{
   toast('Codec Not Supported By This Browser - Falling Back To Thumbnail Player','alert-triangle');
   host.innerHTML=playerHTML(kind==='movie'?'16/9':'16/9');
   mountPlayer(host,item,kind);icons();
  });
 seek.addEventListener('input',()=>{if(vid.duration)vid.currentTime=+seek.value});
 $('[data-p=mute]',host).addEventListener('click',e=>{const b=e.currentTarget;vid.muted=!vid.muted;b.dataset.on=vid.muted?'0':'1';b.innerHTML=`<i data-lucide="${vid.muted?'volume-x':'volume-2'}"></i>`;icons()});
 $('[data-p=fs]',host).addEventListener('click',()=>{document.fullscreenElement?document.exitFullscreen():(host.requestFullscreen&&host.requestFullscreen())});
 ['subs','audio','quality'].forEach(k=>{
  const b=$(`[data-p=${k}]`,host);
  b&&b.addEventListener('click',e=>{e.stopPropagation();menuType=menuType===k?null:k;renderMenu()});
 });
 menuEl.addEventListener('click',e=>{
  const btn=e.target.closest('.pm-i');if(!btn||btn.disabled)return;
  const k=btn.dataset.k,v=btn.dataset.v;
  if(k==='subs'){
   [...vid.textTracks].filter(t=>t.kind==='subtitles').forEach(t=>{t.mode=(v==='Off'||t.label!==v)?'hidden':'showing'});
   toast(v==='Off'?'Subtitles Off':'Subtitles: '+v,'captions');
  }else if(k==='audio'){
   curAudio=Math.max(0,(info.audio||[]).findIndex(a=>{const lbl=[a.lang,a.title,a.codec].filter(Boolean).join(' · ')||('Track '+(a.index+1));return lbl===v}));
   if(vid.audioTracks&&vid.audioTracks.length>1){
    for(let i=0;i<vid.audioTracks.length;i++)vid.audioTracks[i].enabled=(i===curAudio);
    toast('Audio: '+v,'languages');
   }else toast('Track Noted - Your Browser Handles Switching For This Container','languages');
  }else if(k==='quality'){toast('Playing Source Quality','monitor')}
  renderMenu();
 });
 fetch(`/api/media/${kind}/${item.id}/info`).then(r=>r.ok?r.json():null).then(j=>{
  if(!j)return;
  info={...{available:false,audio:[],subs:[]},...j};
  const badge=$('.pinfo');
  if(badge&&j.available){
   badge.textContent=[j.height?resLabel(j.height):null,
    j.vcodec?(j.vcodec.toUpperCase()==='hevc'?'X265':j.vcodec.toUpperCase()):null,
    (j.audio&&j.audio.length)?j.audio.length+' Audio':null].filter(Boolean).join(' · ')||badge.textContent;
  }
  (j.subs||[]).forEach(s=>{
   const tr=document.createElement('track');
   tr.kind='subtitles';tr.label=s.label;tr.src=s.url;
   vid.appendChild(tr);
  });
 }).catch(()=>{});
}
function mountPlayer(host,item,kind){
 const realVid=$('video',host);
 if(realVid){mountRealPlayer(host,item,kind);return}
 const stage=$('.p-stage',host),cvs=$('canvas',stage),cx=cvs.getContext('2d');
 const seek=$('[data-p=seek]',host),pop=$('.p-pop',host),popCvs=$('canvas',pop),popCx=popCvs.getContext('2d');
 const tCur=$('[data-p=cur]',host),big=$('.p-big',host),btnPlay=$('[data-p=play]',host);
 const subEl=$('[data-p=subsbox]',host),menuEl=$('.p-menu',host);
 const info=mediaInfo(item,kind);
 let quality=info.res,audioTrack=(info.audio||[])[0]||'-',subTrack='Off';
 let menuType=null;
 const srcs=playerSrcs(item,kind);
 const dur=Math.max(60,(item.durationMin||30)*60);
 let t=0,playing=false,timer=null,imgs=[];
 const dpr=()=>window.devicePixelRatio||1;
 function size(){cvs.width=stage.clientWidth*dpr();cvs.height=stage.clientHeight*dpr();draw()}
 function draw(){drawGlued(cx,cvs.width,cvs.height,imgs,playing||t>0?t/dur:0)}
 function updateSubs(){
  if(!subEl)return;
  if(subTrack!=='Off'){
   subEl.textContent=SUB_LINES[Math.floor(t/4)%SUB_LINES.length];
   subEl.classList.add('show');
  }else subEl.classList.remove('show');
 }
 popCvs.width=260;popCvs.height=150;
 function drawPop(frac){
  popCx.fillStyle='#0a0806';popCx.fillRect(0,0,260,150);
  const valid=imgs.filter(Boolean);if(!valid.length)return;
  const per=260/valid.length;
  valid.forEach((im,i)=>{const r=Math.max(per/im.width,150/im.height),dw=im.width*r,dh=im.height*r;popCx.save();popCx.beginPath();popCx.rect(i*per,0,per,150);popCx.clip();popCx.drawImage(im,i*per+(per-dw)/2,(150-dh)/2,dw,dh);popCx.restore()});
  popCx.fillStyle='#e0a43e';popCx.fillRect(frac*260-1,0,2,150);
 }
 function setT(v){t=Math.max(0,Math.min(dur,v));seek.value=t;tCur.textContent=fmtTime(t)+' / '+fmtTime(dur);draw();updateSubs()}
 function setPlaying(p){
  playing=p;stage.classList.toggle('playing',p);
  btnPlay.innerHTML=`<i data-lucide="${p?'pause':'play'}"></i>`;icons();
  clearInterval(timer);
  if(p)timer=setInterval(()=>{if(t>=dur){setPlaying(false);setT(0);return}setT(t+1)},250);
 }
 function renderMenu(){
  if(!menuType){menuEl.hidden=true;return}
  menuEl.hidden=false;
  const row=(k,v,sel)=>`<button class="pm-i ${sel?'on':''}" data-k="${k}" data-v="${esc(v)}"><span>${esc(v)}</span>${sel?'<i data-lucide="check"></i>':''}</button>`;
  if(menuType==='subs'){
   const opts=['Off',...info.subs];
   menuEl.innerHTML=`<div class="pm-t">Subtitles</div>`+opts.map(o=>row('subs',o,o===subTrack)).join('')
    +(info.subs.length?'':`<div class="pm-t" style="letter-spacing:0">No Subtitle Tracks On This Title</div>`);
  }else if(menuType==='audio'){
   menuEl.innerHTML=`<div class="pm-t">Audio Track</div>`+info.audio.map(o=>row('audio',o,o===audioTrack)).join('')+`<div class="pm-t">Source · ${esc(info.codec)}</div>`;
  }else{
   menuEl.innerHTML=`<div class="pm-t">Quality</div>`+RES_OPTS.map(o=>row('quality',o,o===quality)).join('')+`<div class="pm-t">Source · ${esc(info.res)} · ${esc(info.codec)}</div>`;
  }
  icons();
 }
 ['subs','audio','quality'].forEach(k=>{
  const b=$(`[data-p=${k}]`,host);
  b&&b.addEventListener('click',e=>{e.stopPropagation();menuType=menuType===k?null:k;renderMenu()});
 });
 menuEl.addEventListener('click',e=>{
  const btn=e.target.closest('.pm-i');if(!btn)return;
  const k=btn.dataset.k,v=btn.dataset.v;
  if(k==='subs'){subTrack=v;updateSubs();toast(v==='Off'?'Subtitles Off':'Subtitles: '+v,'captions')}
  else if(k==='audio'){audioTrack=v;toast('Audio: '+v,'languages')}
  else if(k==='quality'){quality=v;toast('Quality: '+v,'monitor')}
  renderMenu();
 });
 big.addEventListener('click',e=>{e.stopPropagation();setPlaying(!playing)});
 stage.addEventListener('click',e=>{if(!e.target.closest('.p-big'))setPlaying(!playing)});
 btnPlay.addEventListener('click',()=>setPlaying(!playing));
 $('[data-p=skip-back]',host).addEventListener('click',()=>{setT(Math.max(0,t-10))});
 $('[data-p=skip-fwd]',host).addEventListener('click',()=>{setT(Math.min(dur,t+10))});
 seek.max=dur;seek.step='1';seek.addEventListener('input',()=>setT(+seek.value));
 seek.addEventListener('mousemove',e=>{
  const r=seek.getBoundingClientRect();const f=Math.max(0,Math.min(1,(e.clientX-r.left)/r.width));
  pop.classList.add('show');pop.style.left=(r.width*f)+'px';drawPop(f);$('[data-p=pt]',host).textContent=fmtTime(f*dur);
 });
 seek.addEventListener('mouseleave',()=>pop.classList.remove('show'));
 $('[data-p=fs]',host).addEventListener('click',()=>{document.fullscreenElement?document.exitFullscreen():(host.requestFullscreen&&host.requestFullscreen())});
 $('[data-p=mute]',host).addEventListener('click',e=>{const b=e.currentTarget;const on=b.dataset.on!=='1';b.dataset.on=on?'1':'0';b.innerHTML=`<i data-lucide="${on?'volume-2':'volume-x'}"></i>`;icons()});
 Promise.all(srcs.map(loadImg)).then(r=>{imgs=r;size();drawPop(0)});
 size();
 if(window.ResizeObserver){const ro=new ResizeObserver(size);ro.observe(stage)}
 window.addEventListener('resize',size);
}
