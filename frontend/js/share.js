"use strict";
/* ===== SHARE DIALOG ===== */
function resolveSocialHandle(kind,item){
 let perf=null;
 if(kind==='performer')perf=item;
 else if(Array.isArray(item.actorIds)&&item.actorIds.length)perf=DB.performers.find(p=>p.id===item.actorIds[0]);
 return (perf&&(perf.twitter||perf.instagram))||'';
}
function fillCaptionTemplate(tpl,vars){
 let s=tpl;
 for(const k in vars)s=s.split('{'+k+'}').join(vars[k]||'');
 return s.replace(/[ \t]{2,}/g,' ').trim();
}
function openShareDialog(){
 const v=state.view;if(v.name!=='detail')return;
 const item=byId(v.kind,v.id);if(!item)return;
 const label=item.title||item.name;
 const kindLabel=v.kind.charAt(0).toUpperCase()+v.kind.slice(1);
 const platforms=[
  {id:'x',name:'X (Twitter)',icon:'twitter',url:(t)=>`https://x.com/intent/tweet?text=${encodeURIComponent(t)}`},
  {id:'reddit',name:'Reddit',icon:'globe',url:(t)=>`https://reddit.com/submit?title=${encodeURIComponent(t)}`},
  {id:'telegram',name:'Telegram',icon:'send',url:(t)=>`https://t.me/share/url?url=${encodeURIComponent('\u200B')}&text=${encodeURIComponent(t)}`},
  {id:'whatsapp',name:'WhatsApp',icon:'message-circle',url:(t)=>`https://wa.me/?text=${encodeURIComponent(t)}`}
 ];
 const sh=settings.share||{};
 const socialHandle=resolveSocialHandle(v.kind,item);
 // Resolve studio name (movies use studioId, scenes use siteId)
 let studioName='';
 const stId=item.studioId||item.siteId;
 if(stId)studioName=(DB.studios.find(s=>s.id===stId)||{}).name||'';
 // Resolve year/date/desc
 const yearVal=item.year||'';
 const dateVal=item.date||'';
 const descVal=(item.desc||'').slice(0,100);
 const templateVars={kind:kindLabel,name:label,social:socialHandle,studio:studioName,year:String(yearVal),date:dateVal,desc:descVal};
 function captionFor(platId){
  // Per-kind caption > per-platform caption > global default > fallback
  const kindCap=(sh.defaultCaptions&&sh.defaultCaptions[v.kind])||'';
  const tpl=kindCap||(sh.captions&&sh.captions[platId])||sh.defaultCaption||'{kind}: {name}';
  return fillCaptionTemplate(tpl,templateVars);
 }
 const enabledPlats=platforms.filter(p=>!(sh.platforms&&!sh.platforms.includes(p.id)));
 const captionDefault=captionFor(enabledPlats[0]?.id||'x');
 openModal([{title:'Share '+kindLabel,html:()=>`
  <div style="margin-bottom:16px">
   <label class="flab">Caption</label>
   <textarea class="field" id="sh-caption" rows="2" style="width:100%;resize:vertical">${esc(captionDefault)}</textarea>
  </div>
  <div style="margin-bottom:16px">
   <button class="btn primary" id="sh-native-share" style="width:100%;justify-content:center"><i data-lucide="share-2"></i>Share Screenshot</button>
  </div>
  <div style="margin-bottom:16px"><label class="flab">Or Share Directly To</label>
   <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:8px">
    ${enabledPlats.map(p=>`<a href="javascript:void(0)" class="btn icon" data-share-plat="${p.id}" title="${p.name}" style="color:var(--accent);border-color:var(--line2)"><i data-lucide="${p.icon}"></i></a>`).join('')}
   </div>
  </div>
  <div id="sh-preview" style="display:none;margin-bottom:16px">
   <label class="flab">Screenshot Preview</label>
   <div id="sh-preview-img" style="max-height:300px;overflow:auto;border:1px solid var(--line2);border-radius:8px;margin-top:8px"></div>
   <div style="display:flex;gap:8px;margin-top:8px">
    <button class="btn" id="sh-download"><i data-lucide="download"></i>Download Image</button>
    <button class="btn" id="sh-copy"><i data-lucide="copy"></i>Copy To Clipboard</button>
   </div>
  </div>
  <p class="note">"Share Screenshot" Hands The Image Straight To Your Device's Share Sheet - Pick Any App Installed. The Icons Below Open A Specific Platform's Compose Page Instead, With The Screenshot Downloaded For You To Attach.</p>
  `,mount(bl,f){
   icons(bl);
   let capturedCanvases=null;
   let captionEdited=false;
   $('#sh-caption',bl)?.addEventListener('input',()=>{captionEdited=true});

   // --- Pagination helpers ---
   function _getPagerState(){
    const tab=state.view.tab||state.view.kind;
    const Tt=T[tab];
    if(!Tt)return null;
    const items=filtered(tab);
    const pp=(settings.perPage&&settings.perPage[tab])||24;
    const total=items.length;
    const pages=Math.ceil(total/pp);
    return {tab,Tt,items,pp,total,pages};
   }

   async function _capturePageEl(pageEl,pageNum,totalPages){
    if(typeof modernScreenshot==='undefined'){console.error('modern-screenshot not loaded');return null;}
    const hideEls=[...pageEl.querySelectorAll('.dacts,.backlink')];
    const prevDisplay=hideEls.map(el=>el.style.display);
    hideEls.forEach(el=>el.style.display='none');
    const cs=getComputedStyle(document.documentElement);
    const cssVars=['--bg','--bg2','--surface','--surface2','--line','--line2','--text','--muted','--faint','--accent','--accent-ink','--danger','--ok'];
    const prevInline={};
    cssVars.forEach(v=>{prevInline[v]=pageEl.style.getPropertyValue(v);pageEl.style.setProperty(v,cs.getPropertyValue(v).trim())});
    const bgColor=cs.getPropertyValue('--bg').trim()||'#100e0a';
    const prevBg=pageEl.style.background;
    if(!pageEl.style.background)pageEl.style.background=bgColor;
    let canvas=null;
    const ss=settings.screenshot||{};
    const ssScale=ss.scale||2;
    try{
     canvas=await modernScreenshot.domToCanvas(pageEl,{scale:ssScale,backgroundColor:bgColor,style:{transform:'none'}});
     const ctx=canvas.getContext('2d');
     if(ctx){
      const pad=48;
      ctx.save();
      // OBSCURA watermark
      if(ss.watermark!==false){
       ctx.font='bold 44px "JetBrains Mono",monospace';
       ctx.textBaseline='bottom';
       ctx.shadowColor='rgba(0,0,0,0.65)';ctx.shadowBlur=8;
       ctx.fillStyle='rgba(255,255,255,0.9)';
       ctx.fillText('OBSCURA',pad,canvas.height-pad*0.6);
      }
      // Page indicator label when multiple pages
      if(totalPages>1&&ss.pageLabel!==false){
       ctx.font='bold 36px "JetBrains Mono",monospace';
       ctx.textAlign='right';
       ctx.textBaseline='top';
       ctx.shadowColor='rgba(0,0,0,0.65)';ctx.shadowBlur=8;
       ctx.fillStyle='rgba(255,255,255,0.9)';
       ctx.fillText('PAGE '+pageNum+'/'+totalPages,canvas.width-pad,pad*0.5);
       ctx.textAlign='left';
      }
      ctx.restore();
     }
    }catch(e){console.error('Screenshot error:',e.message,e);}
    cssVars.forEach(v=>{if(prevInline[v]!=null&&prevInline[v]!=='')pageEl.style.setProperty(v,prevInline[v]);else pageEl.style.removeProperty(v)});
    if(prevBg!=null)pageEl.style.background=prevBg;else pageEl.style.removeProperty('background');
    hideEls.forEach((el,i)=>el.style.display=prevDisplay[i]);
    return canvas;
   }

   async function captureAllPages(){
    if(capturedCanvases)return capturedCanvases;
    const pageEl=document.querySelector('.page');
    if(!pageEl){console.error('No .page found');return [];}
    const ps=_getPagerState();
    if(!ps||ps.pages<=1){
     // Single page — simple capture
     const c=await _capturePageEl(pageEl,1,1);
     capturedCanvases=c?[c]:[];
     return capturedCanvases;
    }
    // Multi-page: iterate through each page
    const originalPage=ps.Tt.page;
    const canvases=[];
    for(let p=1;p<=ps.pages;p++){
     ps.Tt.page=p;
     refreshList(ps.tab);
     // Wait for DOM to settle
     await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
     // Re-query the .page element since refreshList may replace innerHTML
     const freshPageEl=document.querySelector('.page');
     if(!freshPageEl)continue;
     const c=await _capturePageEl(freshPageEl,p,ps.pages);
     if(c)canvases.push(c);
    }
    // Restore original page
    ps.Tt.page=originalPage;
    refreshList(ps.tab);
    capturedCanvases=canvases;
    return canvases;
   }

   function showPreview(canvases){
    const preview=$('#sh-preview',bl);const previewImg=$('#sh-preview-img',bl);
    preview.style.display='block';
    previewImg.innerHTML='';
    if(!canvases||!canvases.length)return;
    canvases.forEach((canvas,i)=>{
     if(canvases.length>1){
      const lbl=document.createElement('div');
      lbl.className='mono dim';
      lbl.style.cssText='font-size:11px;letter-spacing:.1em;margin-top:'+(i>0?'12px':'0')+';margin-bottom:4px';
      lbl.textContent='PAGE '+(i+1)+'/'+canvases.length;
      previewImg.appendChild(lbl);
     }
     const img=new Image();
     img.src=canvas.toDataURL(_ssMime(),_ssQuality());
     img.style.cssText='width:100%;height:auto;display:block;border-radius:6px';
     previewImg.appendChild(img);
    });
   }

   function _ssMime(){const ss=settings.screenshot||{};return ss.format==='jpg'?'image/jpeg':'image/png';}
   function _ssQuality(){const ss=settings.screenshot||{};return ss.format==='jpg'?((ss.quality||92)/100):0.92;}
   function _ssExt(){const ss=settings.screenshot||{};return ss.format==='jpg'?'.jpg':'.png';}

   function _downloadCanvas(canvas,filename){
    canvas.toBlob(blob=>{
     if(!blob)return;
     const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=filename;a.click();
     setTimeout(()=>URL.revokeObjectURL(a.href),4000);
    },_ssMime(),_ssQuality());
   }

   $('#sh-native-share',bl)?.addEventListener('click',async()=>{
    const shareBtn=$('#sh-native-share',bl);
    const caption=$('#sh-caption',bl).value||captionDefault;
    shareBtn.disabled=true;shareBtn.style.opacity='0.5';
    const canvases=await captureAllPages();
    shareBtn.disabled=false;shareBtn.style.opacity='';
    if(!canvases.length){toast('Screenshot Failed - Check Console For Details','alert-triangle');return}
    showPreview(canvases);
    const autoDl=(settings.screenshot&&settings.screenshot.autoDownload)===true;
    const _autoDlAll=async()=>{for(let i=0;i<canvases.length;i++){_downloadCanvas(canvases[i],`share-${slug(label)}${canvases.length>1?'-page'+(i+1):''}${_ssExt()}`);if(i<canvases.length-1)await new Promise(r=>setTimeout(r,300));}};
    if(canvases.length===1){
     const blob=await new Promise(r=>canvases[0].toBlob(r,_ssMime(),_ssQuality()));
     if(!blob)return;
     const file=new File([blob],`share-${slug(label)}${_ssExt()}`,{type:_ssMime()});
     if(navigator.share&&navigator.canShare&&navigator.canShare({files:[file]})){
      try{await navigator.share({title:caption,text:caption,files:[file]});toast('Shared!','check-circle');if(autoDl)await _autoDlAll();closeModal();return;}
      catch(e){if(e.name==='AbortError')return;console.error('Native share failed:',e);}
     }
     _downloadCanvas(canvases[0],file.name);
     toast('Your Browser Doesn\u2019t Support Native Sharing - Screenshot Downloaded Instead','image');
    }else{
     for(let i=0;i<canvases.length;i++){
      _downloadCanvas(canvases[i],`share-${slug(label)}-page${i+1}${_ssExt()}`);
      await new Promise(r=>setTimeout(r,300));
     }
     toast(canvases.length+' Page Screenshots Downloaded','check-circle');
    }
   });
   $$('[data-share-plat]',bl).forEach(btn=>btn.addEventListener('click',async()=>{
    const platId=btn.dataset.sharePlat;
    const plat=enabledPlats.find(p=>p.id===platId);
    if(!plat)return;
    if(!captionEdited){const capEl=$('#sh-caption',bl);capEl.value=captionFor(platId)}
    const caption=$('#sh-caption',bl).value||captionFor(platId);
    btn.disabled=true;btn.style.opacity='0.5';
    const canvases=await captureAllPages();
    btn.disabled=false;btn.style.opacity='';
    if(!canvases.length){toast('Screenshot Failed - Check Console For Details','alert-triangle');return}
    showPreview(canvases);
    for(let i=0;i<canvases.length;i++){
     _downloadCanvas(canvases[i],`share-${slug(label)}-page${i+1}${_ssExt()}`);
     await new Promise(r=>setTimeout(r,300));
    }
    window.open(plat.url(caption),'_blank');
    toast(canvases.length+' Screenshots Downloaded - Attach On The '+plat.name+' Tab','image');
   }));
   $('#sh-download',bl)?.addEventListener('click',async()=>{
    const canvases=await captureAllPages();
    if(!canvases.length){toast('Screenshot Failed - Check Console For Details','alert-triangle');return}
    for(let i=0;i<canvases.length;i++){
     _downloadCanvas(canvases[i],`share-${slug(label)}-page${i+1}${_ssExt()}`);
     await new Promise(r=>setTimeout(r,300));
    }
    if(canvases.length>1)toast(canvases.length+' Page Screenshots Downloaded','image');
   });
   $('#sh-copy',bl)?.addEventListener('click',async()=>{
    const canvases=await captureAllPages();
    if(!canvases.length){toast('Screenshot Failed - Check Console For Details','alert-triangle');return}
    try{
     const items=await Promise.all(canvases.map(async c=>{
      const blob=await new Promise(r=>c.toBlob(r,'image/png'));
      return new ClipboardItem({'image/png':blob});
     }));
     await navigator.clipboard.write(items);
     toast(canvases.length===1?'Copied To Clipboard':canvases.length+' Pages Copied To Clipboard','check-circle');
    }catch(e){
     // Fallback: copy first page only
     try{
      const blob=await new Promise(r=>canvases[0].toBlob(r,'image/png'));
      await navigator.clipboard.write([new ClipboardItem({'image/png':blob})]);
      toast('Copied First Page To Clipboard','check-circle');
     }catch(e2){toast('Copy Failed','alert-triangle');}
    }
   });
  }}],0,600);
}

/* ===== SCAN IMPORT MODAL ===== */
// Module-level on purpose: the "Mark Unimported" handler puts a candidate back
// into the modal as an editable card, so a wrong Movie/Scene guess can be fixed
// and re-imported now instead of waiting for the next scan.
function importCardHTML(c){
  const isMovie=c.guess_kind==='movie';
  const basis=c.duration_min?fmtDur(c.duration_min):(c.size?fmtBytes(c.size):'');
  return `<div class="impcard" data-path="${esc(c.path)}" data-kind="${c.guess_kind}" data-guesstitle="${esc(c.guess_title)}">
   <div class="imp-head"><i data-lucide="${isMovie?'film':'clapperboard'}"></i>
    <span class="imp-path">${esc(c.name)}</span>
    <span class="kind">Auto${basis?' · '+basis:''}</span>
    <button type="button" class="btn sm" data-action="imp-kind" data-kind="${c.guess_kind}"><i data-lucide="${isMovie?'film':'clapperboard'}"></i><span>${isMovie?'Movie':'Scene'}</span></button>
   </div>
   <div class="imp-path2">${esc(c.path)}${c.size?' · '+fmtBytes(c.size):''}${c.posters&&c.posters.length?` · ${c.posters.length} Poster${c.posters.length===1?'':'s'} Found`:''}</div>
   <div class="imp-grid">
    <div><label class="flab">Title</label><input class="field imp-title" value="${esc(c.guess_title)}"></div>
    <div class="imp-yearwrap" style="${isMovie?'':'display:none'}"><label class="flab">Year</label><input class="field imp-year" type="number" placeholder="2023"></div>
    <div class="imp-datewrap" style="${isMovie?'none':''}"><label class="flab">Date</label><input class="field imp-date" type="date"></div>
    <div><label class="flab">Duration (Min)</label><input class="field imp-dur" type="number" min="1" value="${c.duration_min||''}"></div>
    <div><label class="flab">Director</label><input class="field imp-dir" list="dl-imp-dir"><datalist id="dl-imp-dir">${DIRECTORS.map(d=>`<option value="${esc(d)}">`).join('')}</datalist></div>
   </div>
   <div style="display:flex;align-items:center;gap:14px;margin-top:10px;flex-wrap:wrap">
    <label class="ckrow"><input type="checkbox" class="imp-fav">Favorite</label>
    <span class="dim" style="font-size:11.5px">Sibling Posters Are Imported Automatically.</span>
    <span style="flex:1"></span>
    <button class="btn primary sm" data-action="imp-do"><i data-lucide="download"></i>Import</button>
   </div></div>`;
}
function openImportModal(candidates){
 const pending=(candidates||[]).filter(c=>!c.imported);
 const done=(candidates||[]).filter(c=>c.imported);
 openModal([{title:'Import From Scan',html:()=>`
  <div class="cmsg" style="margin-bottom:14px">${pending.length} New File${pending.length===1?'':'s'} Found - ${done.length} Already Imported. Edit The Suggestions, Then Import Each One.</div>
  ${pending.map(importCardHTML).join('')||`<div class="empty" style="padding:34px 16px"><i data-lucide="inbox"></i><span>No New Files To Import.</span></div>`}
  ${done.length?`<div class="divider" style="display:flex;align-items:center;gap:12px;margin:20px 0 12px;color:var(--faint)"><span class="mono" style="font-size:9px;letter-spacing:.14em">Already Imported</span></div>
   <div class="cplist" style="max-height:180px">${done.map(c=>`<div class="srcrow"><i data-lucide="badge-check"></i><span>${esc(c.name)}</span><button class="tx" data-action="imp-undone" data-path="${esc(c.path)}" data-cand="${esc(JSON.stringify(c))}" title="Mark Unimported"><i data-lucide="rotate-ccw"></i></button></div>`).join('')}</div>`:''}`,
  footer:()=>`<span class="push"></span><button class="btn" data-action="imp-all"><i data-lucide="download"></i>Import All</button><button class="btn" data-mclose="1">Close</button>`}],0,760);
}
