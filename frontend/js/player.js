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
// Per-mount cleanup registry: the player attaches window listeners, a
// ResizeObserver and a 250ms interval — all must be released on re-mount or
// they accumulate (and the interval keeps drawing into detached canvases).
let _playerCleanups=[];
function playerTeardown(){_playerCleanups.forEach(f=>{try{f()}catch(e){}});_playerCleanups=[]}
/* Fullscreen is requested on the .player element (not the #pwrap wrapper):
   the fullscreen CSS (.player:fullscreen .p-stage{flex:1} etc.) only matches
   when .player itself is the fullscreen root. Going fullscreen on #pwrap left
   .player at its 16/9 stage height, pushing .p-bar below the viewport.
   When the native request is denied (iframe/permissions) we fall back to the
   fixed-position .fs-mode "fake fullscreen" so the player still fills the
   screen and the control bar reveal logic keeps working. */
let _fakeFsEl=null;
// Fullscreen entry/exit hooks owned by setupBarAutoHide. bindFs fires them on
// the fake-fullscreen paths, where no fullscreenchange event ever occurs.
let _fsEnterHook=null,_fsExitHook=null;
function fakeFsExit(){if(_fakeFsEl){_fakeFsEl.classList.remove('fs-mode');_fakeFsEl=null}}
function fakeFsEnter(el){if(!el)return;if(_fakeFsEl&&_fakeFsEl!==el)fakeFsExit();_fakeFsEl=el;el.classList.add('fs-mode')}
function fsRoot(host){return $('.player',host)||host}
function bindFs(host){
 const btn=$('[data-p=fs]',host),el=fsRoot(host);
 // The bar is a hidden overlay in .fs-mode — flip it with the mode itself since
 // no fullscreenchange event fires for the fallback path.
 const openBar=()=>{const b=$('.p-bar',host);b&&b.classList.add('is-open')};
 const closeBar=()=>{const b=$('.p-bar',host);b&&b.classList.remove('is-open')};
 const sync=()=>{if(!btn)return;const on=!!(document.fullscreenElement||_fakeFsEl===el);btn.innerHTML=`<i data-lucide="${on?'minimize':'maximize'}"></i>`;icons();};
 if(btn)btn.addEventListener('click',()=>{
   if(document.fullscreenElement){document.exitFullscreen&&document.exitFullscreen();return}
   if(_fakeFsEl===el){fakeFsExit();if(_fsExitHook)_fsExitHook();closeBar();sync();return}
   const req=el&&(el.requestFullscreen||el.webkitRequestFullscreen);
   let p=null;
   if(req){try{p=req.call(el)}catch(e){p=null}}
   if(p&&p.then){
    p.then(()=>{if(_fakeFsEl===el){fakeFsExit();if(_fsExitHook)_fsExitHook();sync()}}).catch(()=>{fakeFsEnter(el);openBar();if(_fsEnterHook)_fsEnterHook();sync()});
   }else if(!p){fakeFsEnter(el);openBar();if(_fsEnterHook)_fsEnterHook();sync()}
  });
  const onFs=()=>sync();
  const onKey=e=>{if((e.key==='Escape'||e.key==='Esc')&&_fakeFsEl===el){fakeFsExit();if(_fsExitHook)_fsExitHook();closeBar();sync()}};
  document.addEventListener('fullscreenchange',onFs);
  document.addEventListener('webkitfullscreenchange',onFs);
  document.addEventListener('keydown',onKey);
  _playerCleanups.push(()=>{document.removeEventListener('fullscreenchange',onFs);document.removeEventListener('webkitfullscreenchange',onFs);document.removeEventListener('keydown',onKey)});
  sync();
}
/* Fullscreen-only auto-hide control bar. In normal view the bar is a static row
   and stays always visible (CSS keeps it in place). In fullscreen it becomes a
   bottom overlay hidden by default, revealed when the pointer moves into the
   bottom reveal zone of the player or onto the bar itself, and it stays up while
   the pointer rests in that zone. Two things would otherwise keep it stuck open
   after entering fullscreen: (1) focus landing on the button that was just
   clicked - only keyboard-reached focus pins the bar; (2) the pointer coordinate
   left over from clicking that button - the zone only counts after the pointer
   has actually moved again (armed). Menu open / scrubbing / volume dragging pin
   it too. */
function setupBarAutoHide(host){
  const player=fsRoot(host),bar=$('.p-bar',host),menuEl=$('.p-menu',host);
  if(!player||!bar)return;
  const stage=$('.p-stage',player);
  // The stage is a plain div: give it tabindex="-1" so focus() can land on it
  // (programmatically focusable, but kept out of the Tab order).
  if(stage&&!stage.hasAttribute('tabindex'))stage.tabIndex=-1;
  const ZONE_MIN=150,ZONE_RATIO=.45,ZONE_MAX=280,IDLE=1400,LEAVE=240;
  let hideTimer=null,dragging=false,lastY=-1,armed=false,kbFocus=false;
  const fsEl=()=>document.fullscreenElement||document.webkitFullscreenElement||document.webkitCurrentFullScreenElement||document.mozFullScreenElement||null;
  const fsNative=()=>{
    try{ if(player.matches(':fullscreen')||player.matches(':-webkit-full-screen')||player.matches(':-moz-full-screen')) return true; }catch(e){}
    const f=fsEl(); return !!f&&(f===player||f===host||(f.contains&&f.contains(player))||(player.contains&&player.contains(f)));
  };
  // .fs-mode covers both native fullscreen (set by syncFsMode) and the
  // fake-fullscreen fallback (fakeFsEnter) — either way the bar is an overlay.
  const fsActive=()=>fsNative()||player.classList.contains('fs-mode');
  const syncFsMode=()=>{try{player.classList.toggle('fs-mode',fsNative()||_fakeFsEl===player)}catch(e){}};
  const clearHide=()=>{if(hideTimer){clearTimeout(hideTimer);hideTimer=null}};
  const menuOpen=()=>!!(menuEl&&!menuEl.hasAttribute('hidden'));
  const pinned=()=>dragging||menuOpen();
  // Keyboard-reached focus pins the bar; focus left behind by a mouse click does not.
  const focusPinned=()=>kbFocus&&bar.contains(document.activeElement);
  // Measure from the player's own bottom (falls back to the viewport) so the
  // zone tracks the element that is actually fullscreen, not a stale window size.
  const bottomY=()=>{const b=player.getBoundingClientRect().bottom;return b>0?b:(window.innerHeight||document.documentElement.clientHeight||0)};
  const zoneSize=()=>{const b=bottomY();return Math.min(ZONE_MAX,Math.max(ZONE_MIN,b*ZONE_RATIO))};
  const inZone=y=>y>=0&&y>=bottomY()-zoneSize();
  const overBar=e=>{const r=bar.getBoundingClientRect();return e.clientX>=r.left-8&&e.clientX<=r.right+8&&e.clientY>=r.top-10&&e.clientY<=r.bottom+6};
  const shouldHide=()=>{
    if(!fsActive())return true;
    if(pinned()||focusPinned())return false;   // menu / drag / keyboard focus pins it up
    if(!armed)return true;                     // no pointer movement since entering fullscreen: ignore stale coordinates
    return !(lastY>=0&&inZone(lastY));         // pointer parked in the reveal zone: stay
  };
  const reveal=()=>{player.classList.add('fs-mode');bar.classList.add('is-open')};
  const hide=()=>{bar.classList.remove('is-open')};
  const scheduleHide=ms=>{clearHide();hideTimer=setTimeout(()=>{if(shouldHide())hide()},ms)};
  const onMove=e=>{
    if(typeof e.clientY!=='number')return;
    lastY=e.clientY;armed=true;
    if(!fsActive()){hide();return}
    if(pinned()||overBar(e)||inZone(e.clientY))reveal();
    // The timer re-checks shouldHide() with the latest pointer position, so the
    // bar cannot vanish while the pointer is parked in the reveal zone.
    scheduleHide(IDLE);
  };
  const onLeave=()=>{
    if(!fsActive()||pinned()||!armed)return;
    // Left through the bottom edge (e.g. the OS taskbar covering the fullscreen
    // player): the pointer is exactly where the controls live — keep them up.
    if(lastY>=0&&inZone(lastY)){scheduleHide(IDLE);return}
    scheduleHide(LEAVE);
  };
  const onFocusIn=()=>{if(!fsActive())return;kbFocus?(reveal(),clearHide()):scheduleHide(IDLE)};
  const onFocusOut=()=>{if(fsActive())scheduleHide(IDLE)};
  const onDown=e=>{
    kbFocus=false;
    if(!fsActive()||dragging||!e.target||!e.target.closest)return;
    if(e.target.closest('[data-p=seek],[data-p=vol]')){dragging=true;reveal()}
  };
  const onUp=()=>{if(dragging){dragging=false;scheduleHide(IDLE)}};
  const onKeyNav=e=>{
    if(!e.key||e.key==='Shift'||e.key==='Control'||e.key==='Alt'||e.key==='Meta')return;
    kbFocus=true;
  };
  // Entering: flash the controls, then fade (armed=false defeats the stale
  // pointer position left over from clicking the fullscreen button).
  const onEnter=()=>{armed=false;clearHide();reveal();scheduleHide(IDLE)};
  // Leaving fullscreen hands focus back to the player itself while the video is
  // still playing — otherwise focus is dropped onto <body> and the player stops
  // receiving keyboard input. Only when something is actually playing.
  const focusPlayerIfPlaying=()=>{
    if(!stage||!stage.isConnected)return;
    const vid=$('video',player);
    const playing=vid?(vid.isConnected&&!vid.paused&&!vid.ended):stage.classList.contains('playing');
    if(!playing)return;
    try{stage.focus({preventScroll:true})}catch(e){try{stage.focus()}catch(e2){}}
  };
  const onExit=()=>{armed=false;clearHide();hide();focusPlayerIfPlaying()};
  const onFsChange=()=>{clearHide();syncFsMode();if(fsActive())onEnter();else onExit()};
  _fsEnterHook=onEnter;
  _fsExitHook=onExit;
  // Capture-phase on window: nothing can stopPropagation and block the reveal.
  window.addEventListener('mousemove',onMove,true);
  window.addEventListener('pointermove',onMove,true);
  window.addEventListener('keydown',onKeyNav,true);
  bar.addEventListener('focusin',onFocusIn);
  bar.addEventListener('focusout',onFocusOut);
  player.addEventListener('mouseleave',onLeave);
  document.addEventListener('mouseleave',onLeave);
  window.addEventListener('pointerdown',onDown,true);
  window.addEventListener('pointerup',onUp,true);
  document.addEventListener('fullscreenchange',onFsChange);
  document.addEventListener('webkitfullscreenchange',onFsChange);
  document.addEventListener('mozfullscreenchange',onFsChange);
  _playerCleanups.push(()=>{clearHide();if(_fsEnterHook===onEnter)_fsEnterHook=null;if(_fsExitHook===onExit)_fsExitHook=null;window.removeEventListener('mousemove',onMove,true);window.removeEventListener('pointermove',onMove,true);window.removeEventListener('keydown',onKeyNav,true);bar.removeEventListener('focusin',onFocusIn);bar.removeEventListener('focusout',onFocusOut);player.removeEventListener('mouseleave',onLeave);document.removeEventListener('mouseleave',onLeave);window.removeEventListener('pointerdown',onDown,true);window.removeEventListener('pointerup',onUp,true);document.removeEventListener('fullscreenchange',onFsChange);document.removeEventListener('webkitfullscreenchange',onFsChange);document.removeEventListener('mozfullscreenchange',onFsChange)});
  if(menuEl&&window.MutationObserver){
    const mo=new MutationObserver(()=>{if(!fsActive())return;menuOpen()?(reveal(),clearHide()):scheduleHide(IDLE)});
    mo.observe(menuEl,{attributes:true,attributeFilter:['hidden']});
    _playerCleanups.push(()=>mo.disconnect());
  }
  syncFsMode();
  hide();
  if(/(^|[#&])debug(&|$)/i.test(location.hash)){
    const d=document.createElement('div');
    d.style.cssText='position:fixed;top:8px;left:8px;z-index:2147483647;background:rgba(0,0,0,.88);color:#3f3;font:12px/1.5 monospace;padding:8px 10px;white-space:pre;pointer-events:none;border-radius:6px';
    if(document.body)document.body.appendChild(d);
    const onDbg=e=>{ if(!fsActive())return;
      d.textContent=`fs=${fsActive()} fsMode=${player.classList.contains('fs-mode')} | y=${Math.round(e.clientY)} bottom=${Math.round(bottomY())} zone=${Math.round(zoneSize())}\ninZone=${inZone(e.clientY)} overBar=${overBar(e)} open=${bar.classList.contains('is-open')} | barBottom=${Math.round(bar.getBoundingClientRect().bottom)} barH=${Math.round(bar.offsetHeight)}`;};
    window.addEventListener('mousemove',onDbg,true);
    _playerCleanups.push(()=>{window.removeEventListener('mousemove',onDbg,true);try{d.remove()}catch(e){}});
  }
}
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
 // Player poster = the cover that is NOT the thumbnail. The old c[1-ti]
 // resolved to undefined as soon as there were 3+ covers.
 return [c.find((_,i)=>i!==ti)||c[0]];
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
const VOL_KEY='obscura:vol';
function loadVol(){try{const v=parseFloat(localStorage.getItem(VOL_KEY));if(isFinite(v)&&v>0)return Math.min(1,v)}catch(e){}return 1}
function saveVol(v){try{if(v>0)localStorage.setItem(VOL_KEY,String(v))}catch(e){}}
/* Volume slider + mute button, shared by the real <video> player and the canvas
   fallback (where it only drives the UI state - nothing plays audio there).
   The slider is the source of truth for the level; the mute button flips
   muted state and restores the last level when unmuting from silence. */
function bindVolume(host,vid){
 const vol=$('[data-p=vol]',host),btn=$('[data-p=mute]',host);
 if(!vol||!btn)return;
 let level=loadVol(),muted=false;
 if(vid){try{vid.volume=level}catch(e){}muted=!!vid.muted}
 const cur=()=>vid?vid.volume:level;
 const isMuted=()=>vid?vid.muted:muted;
 function paint(){
  const m=isMuted()||cur()<=0,v=cur();
  btn.dataset.on=m?'0':'1';
  btn.title=m?'Unmute':'Mute';
  // Only touch the DOM (and re-run lucide) when the glyph actually changes —
  // this runs on every volumechange/scrub tick.
  const ic=m?'volume-x':(v<0.5?'volume-1':'volume-2');
  if(btn.dataset.ic!==ic){btn.dataset.ic=ic;btn.innerHTML=`<i data-lucide="${ic}"></i>`;icons()}
  const val=Math.round(Math.max(0,Math.min(1,v))*100);
  if(document.activeElement!==vol&&+vol.value!==val)vol.value=val;
 }
 function setLevel(v){
  level=Math.max(0,Math.min(1,v));
  if(vid){try{vid.volume=level}catch(e){}if(level>0&&vid.muted)vid.muted=false}
  else if(level>0)muted=false;
  saveVol(level);paint();
 }
 if(vid)vid.addEventListener('volumechange',paint);
 vol.addEventListener('input',()=>setLevel(+vol.value/100));
 btn.addEventListener('click',()=>{
  if(isMuted()||cur()<=0){
   if(vid){vid.muted=false;if(vid.volume<=0)vid.volume=level>0?level:loadVol()}
   else{muted=false;if(level<=0)level=loadVol()}
  }else if(vid)vid.muted=true;
  else muted=true;
  paint();
 });
 paint();
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
   <div class="p-vol"><input type="range" data-p="vol" min="0" max="100" step="1" value="100" title="Volume" aria-label="Volume"></div>
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
   return `<div class="player" style="--par:${par}"><div class="p-stage"><video preload="metadata" playsinline style="aspect-ratio:${par}" src="${esc(src)}"></video>${posters}<button class="p-big" aria-label="Play"><i data-lucide="play"></i></button></div>
   <div class="p-menu" hidden></div>
   <div class="p-bar"><button class="btn icon" data-p="skip-back" title="-10s"><i data-lucide="rewind"></i></button>
    <button class="btn icon" data-p="play"><i data-lucide="play"></i></button>
    <button class="btn icon" data-p="skip-fwd" title="+10s"><i data-lucide="fast-forward"></i></button>
    <div class="p-seek"><input type="range" data-p="seek" value="0"></div>
    <span class="p-time mono" data-p="cur">0:00 / 0:00</span>
    <button class="btn icon" data-p="mute" data-on="1" title="Mute"><i data-lucide="volume-2"></i></button>
    <div class="p-vol"><input type="range" data-p="vol" min="0" max="100" step="1" value="100" title="Volume" aria-label="Volume"></div>
    <button class="btn icon" data-p="subs" title="Subtitles"><i data-lucide="captions"></i></button>
    <button class="btn icon" data-p="audio" title="Audio Track"><i data-lucide="languages"></i></button>
    <button class="btn icon" data-p="quality" title="Quality"><i data-lucide="monitor"></i></button>
    <button class="btn icon" data-p="fs" title="Fullscreen"><i data-lucide="maximize"></i></button></div></div>`;
  }
  const covers=(item.covers||[]).filter((v,i,a)=>v&&(i===0||v!==a[0]));
  const ti=Math.min(item.thumb||0,Math.max(0,covers.length-1));
  // First cover that is not the thumbnail (the old 1-ti broke with 3+ covers).
  const poster=covers.length>1?(covers.find((_,i)=>i!==ti)||covers[0]):(covers[0]||'');
  const showCover=poster&&!resumed;
  return `<div class="player" style="--par:${par}"><div class="p-stage"><video preload="metadata" playsinline style="aspect-ratio:${par}" src="${esc(src)}"></video>${showCover?`<img class="p-poster" src="${esc(poster)}" alt="" style="display:block">`:''}<button class="p-big" aria-label="Play"><i data-lucide="play"></i></button></div>
   <div class="p-menu" hidden></div>
   <div class="p-bar"><button class="btn icon" data-p="skip-back" title="-10s"><i data-lucide="rewind"></i></button>
    <button class="btn icon" data-p="play"><i data-lucide="play"></i></button>
    <button class="btn icon" data-p="skip-fwd" title="+10s"><i data-lucide="fast-forward"></i></button>
    <div class="p-seek"><input type="range" data-p="seek" value="0"></div>
    <span class="p-time mono" data-p="cur">0:00 / 0:00</span>
    <button class="btn icon" data-p="mute" data-on="1" title="Mute"><i data-lucide="volume-2"></i></button>
    <div class="p-vol"><input type="range" data-p="vol" min="0" max="100" step="1" value="100" title="Volume" aria-label="Volume"></div>
    <button class="btn icon" data-p="subs" title="Subtitles"><i data-lucide="captions"></i></button>
    <button class="btn icon" data-p="audio" title="Audio Track"><i data-lucide="languages"></i></button>
    <button class="btn icon" data-p="quality" title="Quality"><i data-lucide="monitor"></i></button>
    <button class="btn icon" data-p="fs" title="Fullscreen"><i data-lucide="maximize"></i></button></div></div>`;
 }
function mountRealPlayer(host,item,kind){
  playerTeardown();
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
  $('[data-p=skip-fwd]',host).addEventListener('click',()=>{vid.currentTime=vid.duration?Math.min(vid.duration,vid.currentTime+10):vid.currentTime+10});
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
  const onUnload=()=>{if(vid.isConnected&&vid.currentTime>3&&!vid.ended)Positions.saveNow(kind,item.id,vid.currentTime)};
  window.addEventListener('pagehide',onUnload);
  window.addEventListener('beforeunload',onUnload);
  _playerCleanups.push(()=>{window.removeEventListener('pagehide',onUnload);window.removeEventListener('beforeunload',onUnload)});
  vid.addEventListener('error',()=>{
   toast('Codec Not Supported By This Browser - Falling Back To Thumbnail Player','alert-triangle');
   host.innerHTML=playerHTML(kind==='movie'?'16/9':'16/9');
   mountPlayer(host,item,kind);icons();
  });
 seek.addEventListener('input',()=>{if(vid.duration)vid.currentTime=+seek.value});
 bindVolume(host,vid);
 bindFs(host);
 setupBarAutoHide(host);
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
 playerTeardown();
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
 function size(){if(!host.isConnected){playerTeardown();return}cvs.width=stage.clientWidth*dpr();cvs.height=stage.clientHeight*dpr();draw()}
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
  if(p)timer=setInterval(()=>{if(!host.isConnected){playerTeardown();return}if(t>=dur){setPlaying(false);setT(0);return}setT(t+1)},250);
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
 bindFs(host);
 setupBarAutoHide(host);
  bindVolume(host,null);
 Promise.all(srcs.map(loadImg)).then(r=>{imgs=r;size();drawPop(0)});
 size();
 let ro=null;
 if(window.ResizeObserver){ro=new ResizeObserver(size);ro.observe(stage)}
 window.addEventListener('resize',size);
 _playerCleanups.push(()=>{clearInterval(timer);if(ro)ro.disconnect();window.removeEventListener('resize',size)});
}
