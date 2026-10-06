"use strict";
/* ===== SETTINGS ===== */
const PROXY_PROTOS=[['http','HTTP'],['https','HTTPS'],['socks5','SOCKS5']];
const ACCENTS=[['#e0a43e','Amber'],['#8fb573','Sage'],['#d3705f','Clay'],['#7aa2cf','Slate'],['#a78bfa','Violet'],['#c9c3b4','Mono']];
const BACKGROUNDS=[['#141210','Onyx'],['#1b1420','Plum'],['#10141a','Midnight'],['#151a14','Forest'],['#f1ecdf','Parchment']];
const FONTS=[['grotesk','Space Grotesk'],['system','System UI'],['mono','JetBrains Mono'],['serif','Serif']];
const BORDERS=[['1','Hairline'],['2','Bold'],['0','None']];
const KIND_LIST=['movie','scene','performer'];
const kindIcon=k=>({movie:'film',scene:'clapperboard',performer:'users'})[k];
function renderSettings(){
 const counts=[['Movies',DB.movies.length],['Scenes',DB.scenes.length],['Performers',DB.performers.length],['Studios',DB.studios.length],['Categories',DB.categories.length]];
 const ai=settings.ai,lk=settings.lock,ip=settings.imgProt,px=settings.proxy,adv=settings.adv,sh=settings.share||{};
 const encN=Object.keys(encStore).length;
 const protoPills=PROXY_PROTOS.map(([v,lb])=>`<label class="radioline"><input type="radio" name="pxproto" value="${v}" ${(px.proto||'http')===v?'checked':''}><span class="dot"></span>${lb}</label>`).join('');
 const accentSwatches=ACCENTS.map(([c,lb])=>`<button type="button" class="swatch ${adv.accent===c?'on':''}" style="--sw:${c};--swi:${inkFor(c)}" data-action="adv-accent" data-v="${c}" title="${lb}"><i data-lucide="${adv.accent===c?'check':'x'}" style="${adv.accent===c?'':'display:none'}"></i></button>`).join('');
 const bgSwatches=BACKGROUNDS.map(([c,lb])=>`<button type="button" class="swatch sq ${adv.background===c?'on':''}" style="--sw:${c};--swi:${inkFor(c)}" data-action="adv-bg" data-v="${c}" title="${lb}"><i data-lucide="${adv.background===c?'check':'x'}" style="${adv.background===c?'':'display:none'}"></i></button>`).join('');
 const fontPills=FONTS.map(([v,lb])=>`<label class="radioline"><input type="radio" name="advfont" value="${v}" ${(adv.font||'grotesk')===v?'checked':''} data-action="adv-font"><span class="dot"></span>${lb}</label>`).join('');
 const borderPills=BORDERS.map(([v,lb])=>`<label class="radioline"><input type="radio" name="advborder" value="${v}" ${(adv.border||'1')===v?'checked':''} data-action="adv-border"><span class="dot"></span>${lb}</label>`).join('');
 const srcRows=KIND_LIST.flatMap(kind=>(settings.sources[kind]||[]).map(s=>`
  <div class="srcrow"><i data-lucide="${kindIcon(kind)}"></i><span>${esc(s.name)}<span class="dim"> · ${esc(s.url)}</span></span><span class="kind">${kindLabel(kind)}</span><button class="tx" data-action="src-del" data-kind="${kind}" data-i="${s.i}"><i data-lucide="x"></i></button></div>`)).join('');
 const scraperRows=settings.scrapers.map(s=>`
  <div class="srcrow"><i data-lucide="${s.type==='python'?'file-code':'file-json'}"></i><span>${esc(s.name)}<span class="dim"> · ${(s.size/1024).toFixed(1)} KB</span></span><span class="kind">${kindLabel(s.kind)} · ${s.type==='python'?'Python':'YAML'}</span><button class="tx" data-action="scr-toggle" data-id="${s.id}" title="${s.enabled?'Disable':'Enable'}"><i data-lucide="${s.enabled?'toggle-right':'toggle-left'}"></i></button><button class="tx" data-action="scr-del" data-id="${s.id}"><i data-lucide="x"></i></button></div>`).join('');
 $('#main').innerHTML=`<div class="page narrow">
  ${pageHeadHTML('settings')}
 <nav class="snav"><a href="#cat-general" class="snav-item"><i data-lucide="sliders-horizontal"></i>General</a><a href="#cat-playback" class="snav-item"><i data-lucide="monitor-play"></i>Playback & Media</a><a href="#cat-scraping" class="snav-item"><i data-lucide="search"></i>Scraping & Metadata</a><a href="#cat-privacy" class="snav-item"><i data-lucide="shield"></i>Privacy & Security</a><a href="#cat-storage" class="snav-item"><i data-lucide="hard-drive"></i>Storage & Data</a><a href="#cat-danger" class="snav-item"><i data-lucide="skull"></i>Danger Zone</a><a href="#cat-about" class="snav-item"><i data-lucide="info"></i>About</a></nav>
 <div class="scat" id="cat-general"><div class="scat-head"><i data-lucide="sliders-horizontal"></i><span>General</span></div>
  <div class="ssec"><div class="shead"><i data-lucide="database"></i><h2>Library</h2><span class="mono">Counts${Sync.on?' · Synced':''}</span></div>
   <div class="counts">${counts.map(c=>`<div class="cnt"><div class="mono">${c[0]}</div><div class="cv">${c[1]}</div></div>`).join('')}</div>
  </div>
  <div class="ssec"><div class="shead"><i data-lucide="palette"></i><h2>Theme</h2><span class="mono">Appearance & Layout</span></div>
   <div class="themerow" style="margin-bottom:20px">
    <button class="theme-card ${settings.theme==='dark'?'on':''}" data-action="set-theme" data-v="dark"><span class="tc-prev tc-dark"><span class="tc-bar"></span><span class="tc-line"></span><span class="tc-dot"></span></span><div><b>Dark</b><span class="mono">Ink & Amber</span></div><span class="ck"><i data-lucide="check-circle-2"></i></span></button>
    <button class="theme-card ${settings.theme==='light'?'on':''}" data-action="set-theme" data-v="light"><span class="tc-prev tc-light"><span class="tc-bar"></span><span class="tc-line"></span><span class="tc-dot"></span></span><div><b>Light</b><span class="mono">Paper & Bronze</span></div><span class="ck"><i data-lucide="check-circle-2"></i></span></button>
   </div>
   <div style="margin-bottom:16px"><label class="flab">Accent Color</label>
    <div class="radiogroup" style="gap:10px">${accentSwatches}</div></div>
   <div style="margin-bottom:16px"><label class="flab">Background Color</label>
    <div class="radiogroup" style="gap:10px">${bgSwatches}<button type="button" class="swatch sq ${!adv.background?'on':''}" style="--sw:var(--bg2);--swi:var(--text)" data-action="adv-bg" data-v="" title="Theme Default"><i data-lucide="${!adv.background?'check':''}" style="${!adv.background?'':'display:none'}"></i></button></div></div>
   <div style="margin-bottom:16px"><label class="flab">Font</label>
    <div class="radiogroup">${fontPills}</div></div>
   <div style="margin-bottom:16px"><label class="flab">Card Radius</label>
    <div style="display:flex;align-items:center;gap:12px;max-width:320px">
     <input type="range" id="adv-radius" min="0" max="24" step="1" value="${adv.radius??12}" style="flex:1">
     <span class="mono" id="adv-rv" style="min-width:40px;text-align:right">${adv.radius??12}px</span>
    </div></div>
   <div style="margin-bottom:16px"><label class="flab">Card Border</label>
    <div class="radiogroup">${borderPills}</div></div>
   <button class="btn" data-action="adv-reset"><i data-lucide="rotate-ccw"></i>Reset Theme Options</button>
   <p class="note" style="margin-top:12px">Theme, Accent, Background, Radius And Border Apply Across The Whole App Instantly And Are Saved Automatically. Background Tints The App Shell And Surfaces; Choose Theme Default To Revert.</p></div>
  <div class="ssec"><div class="shead"><i data-lucide="list"></i><h2>Pagination</h2><span class="mono">Items Per Page</span></div>
   ${[{id:'movies',name:'Movies'},{id:'scenes',name:'Scenes'},{id:'performers',name:'Performers'},{id:'studios',name:'Studios'},{id:'categories',name:'Categories'}].map(t=>`<div class="setline"><span>${t.name}</span><span class="stepper"><button type="button" data-action="per-page" data-tab="${t.id}" data-d="-1" title="Decrease"><i data-lucide="minus"></i></button><span class="mono stv" id="pp-${t.id}">${(settings.perPage&&settings.perPage[t.id])||24}</span><button type="button" data-action="per-page" data-tab="${t.id}" data-d="1" title="Increase"><i data-lucide="plus"></i></button></span></div>`).join('')}
   <p class="note" style="margin-top:10px">How Many Items Show Per Page For Each Tab. Range 6-100.</p></div>
  <div class="ssec"><div class="shead"><i data-lucide="tag"></i><h2>Category Display</h2><span class="mono">Details</span></div>
   <div class="setline"><span>Categories Shown In Details</span>
    <span class="stepper"><button type="button" data-action="cat-limit" data-d="-1" title="Decrease"><i data-lucide="minus"></i></button><span class="mono stv" id="cl-v">${settings.catLimit}</span><button type="button" data-action="cat-limit" data-d="1" title="Increase"><i data-lucide="plus"></i></button></span></div>
   <p class="note" style="margin-top:10px">How Many Category Chips A Movie Or Scene Shows Before A "+N More" Expander. Range 1-50.</p></div>
 </div>
 <div class="scat" id="cat-playback"><div class="scat-head"><i data-lucide="monitor-play"></i><span>Playback & Media</span></div>
  <div class="ssec"><div class="shead"><i data-lucide="monitor-play"></i><h2>Playback</h2><span class="mono">Player</span></div>
   <label class="radioline"><input type="radio" name="pl" ${settings.player==='internal'?'checked':''} data-action="set-player" data-v="internal"><span class="dot"></span>Internal Player</label>
   <label class="radioline"><input type="radio" name="pl" ${settings.player==='external'?'checked':''} data-action="set-player" data-v="external"><span class="dot"></span>OS Default Player</label>
   <p class="note" style="margin-top:12px">The Internal Player Streams Real Video Files From The Backend (4K, x265/x264, Multiple Audio Tracks, Sidecar Subtitles). "OS Default Player" Hands The File To Your System Player. Install FFmpeg For Real Codec Details.</p></div>
  <div class="ssec"><div class="shead"><i data-lucide="play"></i><h2>Continue Watching</h2><span class="mono">Display</span></div>
   <div class="setline"><span>Items Shown In Continue Watching</span>
    <span class="stepper"><button type="button" data-action="cw-limit" data-d="-1" title="Decrease"><i data-lucide="minus"></i></button><span class="mono stv" id="cw-v">${settings.cwLimit||4}</span><button type="button" data-action="cw-limit" data-d="1" title="Increase"><i data-lucide="plus"></i></button></span></div>
   <p class="note" style="margin-top:10px">How Many Items Appear In The Continue Watching Row. Range 1-20.</p></div>
  <div class="ssec"><div class="shead"><i data-lucide="images"></i><h2>Gallery</h2><span class="mono">Scene Pictures</span></div>
   <div class="setline"><span>Show Gallery In Scene Details</span><label class="switch"><input type="checkbox" id="gl-on" ${(settings.gallery&&settings.gallery.enabled!==false)?'checked':''}><span class="knob"></span></label></div>
   <div class="setline"><span>Pictures To Fetch</span>
    <span class="stepper"><button type="button" data-action="gl-count" data-d="-1" title="Decrease"><i data-lucide="minus"></i></button><span class="mono stv" id="gl-count-v">${(settings.gallery&&settings.gallery.count)||12}</span><button type="button" data-action="gl-count" data-d="1" title="Increase"><i data-lucide="plus"></i></button></span></div>
   <div class="setline"><span>Pictures To Display</span>
    <span class="stepper"><button type="button" data-action="gl-show" data-d="-1" title="Decrease"><i data-lucide="minus"></i></button><span class="mono stv" id="gl-show-v">${(settings.gallery&&settings.gallery.show)||12}</span><button type="button" data-action="gl-show" data-d="1" title="Increase"><i data-lucide="plus"></i></button></span></div>
   <div style="margin-bottom:12px;max-width:520px;margin-top:10px"><label class="flab">Thumbnail Size</label>
    <div style="display:flex;gap:8px;margin-top:8px">
     <button type="button" class="btn ${!(settings.gallery&&settings.gallery.size==='large')?'primary':''}" data-action="gl-size" data-v="small" id="gl-sz-small">Small</button>
     <button type="button" class="btn ${(settings.gallery&&settings.gallery.size)==='large'?'primary':''}" data-action="gl-size" data-v="large" id="gl-sz-large">Large</button>
    </div></div>
   <button class="btn" data-action="gl-save" style="margin-top:14px"><i data-lucide="save"></i>Save Gallery Settings</button>
   <p class="note" style="margin-top:12px">"Pictures To Fetch" Controls How Many Gallery Images The Scraper Downloads When You Update Scene Information — More Pictures Use More Storage. "Pictures To Display" Limits How Many Show In The Detail Page Gallery. Re-Run "Update Information" After Changing Fetch Count. Gallery Requires A Scraper That Supports It (e.g. Sweet Pornstars).</p></div>
  <div class="ssec"><div class="shead"><i data-lucide="camera"></i><h2>Screenshot</h2><span class="mono">Capture Settings</span></div>
   <div class="setline"><span>Resolution Scale</span>
    <span class="stepper"><button type="button" data-action="ss-scale" data-d="-1" title="Decrease"><i data-lucide="minus"></i></button><span class="mono stv" id="ss-scale-v">${(settings.screenshot&&settings.screenshot.scale)||2}x</span><button type="button" data-action="ss-scale" data-d="1" title="Increase"><i data-lucide="plus"></i></button></span></div>
   <div class="setline"><span>Include OBSCURA Watermark</span><label class="switch"><input type="checkbox" id="ss-wm" ${(settings.screenshot&&settings.screenshot.watermark!==false)?'checked':''}><span class="knob"></span></label></div>
   <div class="setline"><span>Show Page Number On Multi-Page</span><label class="switch"><input type="checkbox" id="ss-pagelabel" ${(settings.screenshot&&settings.screenshot.pageLabel!==false)?'checked':''}><span class="knob"></span></label></div>
   <div class="setline"><span>Auto-Download After Capture</span><label class="switch"><input type="checkbox" id="ss-autodl" ${(settings.screenshot&&settings.screenshot.autoDownload)?'checked':''}><span class="knob"></span></label></div>
   <div style="margin-bottom:12px;max-width:520px;margin-top:10px"><label class="flab">Image Format</label>
    <div style="display:flex;gap:8px;margin-top:8px">
     <button type="button" class="btn ${(settings.screenshot&&settings.screenshot.format)!=='jpg'?'primary':''}" data-action="ss-format" data-v="png" id="ss-fmt-png">PNG</button>
     <button type="button" class="btn ${(settings.screenshot&&settings.screenshot.format)==='jpg'?'primary':''}" data-action="ss-format" data-v="jpg" id="ss-fmt-jpg">JPEG</button>
    </div></div>
   <div class="setline" id="ss-quality-row" style="${(settings.screenshot&&settings.screenshot.format)==='jpg'?'':'display:none'}"><span>JPEG Quality</span>
    <span class="stepper"><button type="button" data-action="ss-quality" data-d="-5" title="Decrease"><i data-lucide="minus"></i></button><span class="mono stv" id="ss-quality-v">${(settings.screenshot&&settings.screenshot.quality)||92}%</span><button type="button" data-action="ss-quality" data-d="5" title="Increase"><i data-lucide="plus"></i></button></span></div>
   <button class="btn" data-action="ss-save" style="margin-top:14px"><i data-lucide="save"></i>Save Screenshot Settings</button>
   <p class="note" style="margin-top:12px">Resolution Scale Controls Sharpness — 2x Is Default (Crisp On Most Screens), 3x Is Ultra-Sharp But Larger Files. PNG Is Lossless; JPEG Smaller But Lossy. Page Labels Stamp "PAGE X/Y" On Multi-Page Captures. Auto-Download Saves A Copy To Your Device Even When Using Native Share. Changes Apply To The Next Screenshot.</p></div>
  <div class="ssec"><div class="shead"><i data-lucide="share-2"></i><h2>Sharing</h2><span class="mono">Social Media</span></div>
   <div class="setline"><span>Include Watermark</span><label class="switch"><input type="checkbox" id="sh-wm" ${(sh.watermark!==false)?'checked':''}><span class="knob"></span></label></div>
   <div style="margin-bottom:12px;max-width:520px"><label class="flab">Default Caption <span class="dim">(Fallback For Any Platform Without Its Own)</span></label><input class="field" id="sh-defcap" value="${esc(sh.defaultCaption||'')}" placeholder="{kind}: {name}"></div>
   <div style="margin-bottom:12px;max-width:520px;margin-top:10px"><label class="flab">Per-Kind Default Captions <span class="dim">(Override Above Per Entity Type)</span></label>
    <div style="display:flex;flex-direction:column;gap:8px;margin-top:8px">
     ${[{id:'movie',name:'Movie',ph:'Check Out {name} ({year}) - {studio}'},{id:'scene',name:'Scene',ph:'{name} ({date}) - {studio}'},{id:'performer',name:'Performer',ph:'Check Out {name} - Follow {social}'},{id:'studio',name:'Studio',ph:'{name} - {desc}'}].map(k=>`<div><label class="flab" style="font-weight:400;font-size:11.5px">${k.name}</label><input class="field" id="sh-defcap-${k.id}" value="${esc((sh.defaultCaptions&&sh.defaultCaptions[k.id])||'')}" placeholder="${k.ph}"></div>`).join('')}
    </div></div>
   <div style="margin-top:10px"><label class="flab">Platforms</label>
    <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:8px">
     ${[{id:'x',name:'X (Twitter)',icon:'twitter'},{id:'reddit',name:'Reddit',icon:'globe'},{id:'telegram',name:'Telegram',icon:'send'},{id:'whatsapp',name:'WhatsApp',icon:'message-circle'}].map(p=>`<button type="button" class="btn icon ${(sh.platforms||[]).includes(p.id)?'on':''}" data-sh-plat="${p.id}" title="${p.name}" style="color:var(--accent);border-color:var(--line2)"><i data-lucide="${p.icon}"></i></button>`).join('')}
    </div></div>
   <div style="margin-top:14px"><label class="flab">Per-Platform Default Captions</label>
    <div style="display:flex;flex-direction:column;gap:10px;margin-top:8px;max-width:520px">
     ${[{id:'x',name:'X (Twitter)'},{id:'reddit',name:'Reddit'},{id:'telegram',name:'Telegram'}].map(p=>`<div><label class="flab" style="font-weight:400;font-size:11.5px">${p.name}</label><input class="field" id="sh-cap-${p.id}" value="${esc((sh.captions&&sh.captions[p.id])||'')}" placeholder="Hi Guys, This Is My Collection From {social}"></div>`).join('')}
    </div></div>
   <button class="btn" data-action="sh-save" style="margin-top:14px"><i data-lucide="save"></i>Save Sharing Settings</button>
   <p class="note" style="margin-top:12px">Select Which Social Platforms Appear In The Share Dialog. Each Can Have Its Own Default Caption — Leave One Blank To Fall Back To The Default Caption Above. Per-Kind Captions Override The Global Default. Placeholders: <span class="mono">{kind}</span> (Movie/Scene/Performer/Studio), <span class="mono">{name}</span> (Title Or Name), <span class="mono">{social}</span> (Performer's Twitter/Instagram — Blank If Unset), <span class="mono">{studio}</span> (Studio Name), <span class="mono">{year}</span> (Year), <span class="mono">{date}</span> (Date), <span class="mono">{desc}</span> (Description — First 100 Chars). Screenshot Is Captured Automatically.</p></div>
 </div>
 <div class="scat" id="cat-scraping"><div class="scat-head"><i data-lucide="search"></i><span>Scraping & Metadata</span></div>
  <div class="ssec"><div class="shead"><i data-lucide="rss"></i><h2>Data Sources</h2><span class="mono">Scraper Websites</span></div>
   <div class="frow" style="max-width:none;gap:10px">
    ${KIND_LIST.map(kind=>`<div><label class="flab">${kindLabel(kind)} Website</label>
     <div style="display:flex;gap:6px">
      <input class="field" id="src-${kind}" placeholder="https://.../title">
      <button class="btn primary" data-action="src-add" data-kind="${kind}" style="flex-shrink:0"><i data-lucide="plus"></i>Add</button>
     </div></div>`).join('')}
   </div>
   <div style="margin-top:14px">
    ${srcRows||'<div class="dim" style="font-size:12.5px;margin-bottom:4px">No Websites Added Yet - Add One Per Row Above.</div>'}
   </div>
   <p class="note" style="margin-top:12px">Each Kind Keeps Its Own Website List. Added Websites Appear In The "Get Information" Dialog Only For Their Kind. When The Backend Is Running, Lookups On These Sites Are Executed By Your Installed Scrapers.</p></div>
<div class="ssec"><div class="shead"><i data-lucide="file-code"></i><h2>External Scrapers</h2><span class="mono">Python · YAML</span></div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
     <button class="btn primary" data-action="scr-add"><i data-lucide="upload"></i>Add Scraper File</button>
     <button class="btn" data-action="scr-html"><i data-lucide="code"></i>Import HTML Structure</button>
     <button class="btn ${settings.pyScrapers?'primary':''}" data-action="py-toggle" title="Python scrapers execute as local code on this machine"><i data-lucide="shield-check"></i>Python Scrapers: ${settings.pyScrapers?'Allowed':'Blocked'}</button>
    </div>
    <div style="margin-top:14px">${scraperRows||'<div class="dim" style="font-size:12.5px;margin-bottom:4px">No External Scrapers Installed Yet.</div>'}</div>
    <p class="note" style="margin-top:12px">Install A Python (.py) Or YAML (.yml / .yaml) Scraper And Assign It To Movies, Scenes Or Performers - Enabled Scrapers Appear As Sources In The Lookup Dialog And Are Executed By The Backend. With "Import HTML Structure" You Can Paste A Page's HTML And The App Reads Its Meta Structure To Suggest A Field Mapping That Is Saved With The Scraper Definition.</p></div>
  <div class="ssec"><div class="shead"><i data-lucide="bot"></i><h2>AI Assistant</h2><span class="mono">Metadata Lookup</span></div>
   <div class="setline"><span>Enable AI</span><label class="switch"><input type="checkbox" id="ai-on" ${ai.on?'checked':''}><span class="knob"></span></label></div>
   <div class="aigrid">
    <div><label class="flab">Provider</label><select class="field" id="ai-provider">${Object.entries(AI_PROVIDERS).map(([k,v])=>`<option value="${k}" ${ai.provider===k?'selected':''}>${v[0]}</option>`).join('')}</select></div>
    <div><label class="flab">Model</label><input class="field" id="ai-model" value="${esc(ai.model)}" placeholder="gpt-4o-mini"></div>
   </div>
   <div style="margin-top:10px;max-width:520px"><label class="flab">Endpoint</label><input class="field" id="ai-endpoint" value="${esc(ai.endpoint)}" placeholder="https://.../v1"></div>
   <div style="margin-top:10px;max-width:520px"><label class="flab">API Key</label><input class="field" id="ai-key" type="password" value="${esc(ai.key)}" placeholder="Stored In The OS Credential Store"></div>
   <div style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap">
    <button class="btn primary" data-action="ai-save"><i data-lucide="save"></i>Save AI Settings</button>
    <button class="btn" data-action="ai-test"><i data-lucide="plug-zap"></i>Test Connection</button>
   </div>
   <p class="note" style="margin-top:12px">AI Appears As An Option Inside Every "Get Information" Dialog. With The Backend Running, Your API Key Is Stored In The Operating System's Credential Store - Never In The Backup Or Settings File - And Lookups Run Server-Side. Without It, Lookups Are Simulated Locally.</p></div>
 </div>
 <div class="scat" id="cat-privacy"><div class="scat-head"><i data-lucide="shield"></i><span>Privacy & Security</span></div>
  <div class="ssec"><div class="shead"><i data-lucide="lock"></i><h2>Password Protection</h2><span class="mono">App Lock</span></div>
   <div class="setline"><span>Enable App Lock</span><label class="switch"><input type="checkbox" id="lk-on" ${lk.on?'checked':''}><span class="knob"></span></label></div>
   <div style="max-width:520px">
    ${lk.pass_set?'<div style="margin-bottom:10px"><label class="flab">Current Password</label><input class="field" id="lk-cur" type="password" placeholder="Required To Change Or Disable"></div>':''}
    <div class="frow" style="max-width:none">
     <div><label class="flab">${lk.pass_set?'New Password':'Password'}</label><input class="field" id="lk-p1" type="password" placeholder="Min 4 Characters"></div>
     <div><label class="flab">Confirm Password</label><input class="field" id="lk-p2" type="password" placeholder="Repeat Password"></div>
    </div>
   </div>
   <div style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap">
    <button class="btn primary" data-action="lock-set"><i data-lucide="key-round"></i>${lk.pass_set?'Change Password':'Set Password'}</button>
    <button class="btn" data-action="lock-now" ${lk.on?'':'disabled'}><i data-lucide="lock"></i>Lock Now</button>
   </div>
   <p class="note" style="margin-top:12px">When Enabled, The Lock Screen Appears Every Time The App Starts. The Password Is Verified By The Server With A Slow Key Derivation Function - The Browser Never Stores Or Checks It.</p></div>
  <div class="ssec"><div class="shead"><i data-lucide="shield"></i><h2>Image Protection</h2><span class="mono">Posters & Covers</span></div>
   <div class="setline"><span>Enable Image Protection</span><label class="switch"><input type="checkbox" id="ip-on" ${ip.on?'checked':''}><span class="knob"></span></label></div>
   <div style="max-width:520px">
    ${ip.hash?'<div style="margin-bottom:10px"><label class="flab">Current Passphrase</label><input class="field" id="ip-cur" type="password" placeholder="Required To Change Or Disable"></div>':''}
    <div class="frow" style="max-width:none">
     <div><label class="flab">${ip.hash?'New Passphrase':'Passphrase'}</label><input class="field" id="ip-p1" type="password" placeholder="Min 4 Characters"></div>
     <div><label class="flab">Confirm Passphrase</label><input class="field" id="ip-p2" type="password" placeholder="Repeat Passphrase"></div>
    </div>
   </div>
   <div style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap">
    <button class="btn primary" data-action="ip-save"><i data-lucide="key-round"></i>${ip.hash?'Change Passphrase':'Set Passphrase'}</button>
   </div>
   <p class="note" style="margin-top:12px">When Enabled, Locally Uploaded Posters And Covers Are Encrypted With AES-256-GCM Before Being Stored - The OS Cannot Read Or Preview Them As Images. With The Backend Running, Encryption And Unlocking Are Handled Server-Side In The Data Folder. Fetched Poster URLs Remain Remote Links.</p></div>
  <div class="ssec"><div class="shead"><i data-lucide="globe"></i><h2>Proxy</h2><span class="mono">Network</span></div>
   <div class="setline"><span>Enable Proxy</span><label class="switch"><input type="checkbox" id="px-on" ${px.on?'checked':''}><span class="knob"></span></label></div>
   <div style="margin-bottom:12px"><label class="flab">Protocol</label><div class="radiogroup">${protoPills}</div></div>
   <div class="proxygrid">
    <input class="field" id="px-host" placeholder="Proxy Host" value="${esc(px.host)}">
    <input class="field" id="px-port" placeholder="Port" value="${esc(px.port)}">
   </div>
   <div class="setline" style="margin-top:12px"><span>Authentication</span><label class="switch"><input type="checkbox" id="px-auth" ${px.auth?'checked':''}><span class="knob"></span></label></div>
   <div class="proxygrid" id="px-authrow" style="${px.auth?'':'display:none'}"><input class="field" id="px-user" placeholder="Username" value="${esc(px.user)}"><input class="field" id="px-pass" type="password" placeholder="Password" value="${esc(px.pass)}"></div>
   <div style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap">
    <button class="btn" data-action="proxy-detect"><i data-lucide="scan-eye"></i>Detect System Proxy</button>
    <button class="btn primary" data-action="proxy-save"><i data-lucide="save"></i>Save Proxy Settings</button>
   </div>
   <p class="note" style="margin-top:12px">Supported Protocols: HTTP, HTTPS And SOCKS5. With The Backend Running, These Settings Are Used For Outgoing Scraper And Lookup Requests.</p></div>
 </div>
 <div class="scat" id="cat-storage"><div class="scat-head"><i data-lucide="hard-drive"></i><span>Storage & Data</span></div>
  <div class="ssec"><div class="shead"><i data-lucide="save"></i><h2>Backup & Restore</h2><span class="mono">Portable Data</span></div>
   <div style="display:flex;gap:8px;flex-wrap:wrap">
    <button class="btn primary" data-action="bk-export" ${Sync.on?'':'disabled'} title="${Sync.on?'':'Requires The Backend'}"><i data-lucide="download"></i>Export Backup</button>
    <button class="btn" data-action="bk-restore" ${Sync.on?'':'disabled'} title="${Sync.on?'':'Requires The Backend'}"><i data-lucide="upload"></i>Restore Backup</button>
   </div>
   <p class="note" style="margin-top:12px">Export Creates One .zip With The Database (Including Watch Positions), Encrypted Images, Installed Scrapers And Settings - The AI Key Is Not Included. Restore Replaces The Current Data With The Backup Contents And Reloads The App. Requires The Backend.</p></div>
  <div class="ssec"><div class="shead"><i data-lucide="archive"></i><h2>Cache</h2><span class="mono">Storage</span></div>
   <div class="counts two">
    <div class="cnt"><div class="mono">Protected Images</div><div class="cv" id="cache-count">${encN}</div></div>
    <div class="cnt"><div class="mono">Cache Used</div><div class="cv" id="cache-size" style="font-size:16px;line-height:1.5;padding-top:4px">-</div></div>
   </div>
   <div style="display:flex;gap:8px;margin-top:14px;flex-wrap:wrap">
    <button class="btn" data-action="cache-clear"><i data-lucide="eraser"></i>Clear Image Cache</button>
    <button class="btn danger" data-action="cache-purge" ${encN?'':'disabled'}><i data-lucide="trash-2"></i>Delete All Protected Images</button>
   </div>
   <p class="note" style="margin-top:12px">Clear Image Cache Releases Preview Memory And Locks Protected Images Again. Delete All Protected Images Permanently Removes The Encrypted Copies From Storage. This Cannot Be Undone.</p></div>
  <div class="ssec"><div class="shead"><i data-lucide="folder-search"></i><h2>Scan Directories</h2><span class="mono">Local Media</span></div>
   <div id="dirs">${settings.dirs.map((d,i)=>`<div class="dirrow"><i data-lucide="folder"></i><span>${esc(d)}</span><button class="tx" data-action="dir-del" data-i="${i}"><i data-lucide="x"></i></button></div>`).join('')||'<div class="dim" style="font-size:12.5px;margin-bottom:8px">No Directories Added Yet.</div>'}</div>
   <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap">
    <button class="btn" data-action="dir-add"><i data-lucide="folder-plus"></i>Add Directory</button>
    <button class="btn primary" data-action="scan" ${settings.dirs.length?'':'disabled'}><i data-lucide="scan-search"></i>Scan Now</button>
    <button class="btn" data-action="scan-import" ${settings.dirs.length?'':'disabled'}><i data-lucide="import"></i>Import From Scan</button>
   </div>
   <div class="scanprog" id="scanprog" style="display:none"><div class="sp-bar"><span id="sp-fill"></span></div><div class="mono" id="sp-txt"></div></div></div>
  <div class="ssec"><div class="shead"><i data-lucide="wrench"></i><h2>Maintenance</h2><span class="mono">Tools</span></div>
   <div class="maintrow"><div><b>Check Duplicates</b><span class="mono">Movies · Scenes · Performers · Studios · Categories</span></div><button class="btn" data-action="dup-check"><i data-lucide="copy-x"></i>Run Check</button></div>
   <div class="maintrow"><div><b>Title-Case All Titles</b><span class="mono">Capitalize First Letter Of Each Word</span></div><button class="btn" data-action="title-case"><i data-lucide="case-upper"></i>Apply</button></div>
   <div class="maintrow"><div><b>Clear Watch Positions</b><span class="mono">Reset Resume Points For All Movies & Scenes</span></div><button class="btn" data-action="pos-clear"><i data-lucide="history"></i>Clear Positions</button></div></div>
 </div>
 <div class="scat" id="cat-danger"><div class="scat-head"><i data-lucide="skull"></i><span>Danger Zone</span></div>
  <div class="ssec"><div class="shead"><i data-lucide="skull"></i><h2>Danger Zone</h2></div>
   <div class="maintrow"><div><b>Return To Default Settings</b><span class="mono">Reset Preferences · Library Is Kept</span></div><button class="btn" data-action="reset"><i data-lucide="history"></i>Return To Default Settings</button></div>
   <div class="maintrow"><div><b>Clear All Data</b><span class="mono">Delete Library · Favorites · Encrypted Images · Settings</span></div><button class="btn danger" data-action="wipe"><i data-lucide="trash-2"></i>Clear All Data</button></div>
   <div style="margin-top:14px"><label class="flab">Clear Individual Tabs</label>
    <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:8px">
     <button class="btn sm danger" data-action="clear-tab" data-tab="movies"><i data-lucide="trash-2"></i>Movies</button>
     <button class="btn sm danger" data-action="clear-tab" data-tab="scenes"><i data-lucide="trash-2"></i>Scenes</button>
     <button class="btn sm danger" data-action="clear-tab" data-tab="performers"><i data-lucide="trash-2"></i>Performers</button>
     <button class="btn sm danger" data-action="clear-tab" data-tab="studios"><i data-lucide="trash-2"></i>Studios</button>
     <button class="btn sm danger" data-action="clear-tab" data-tab="categories"><i data-lucide="trash-2"></i>Categories</button>
    </div>
    <p class="note" style="margin-top:8px">Clear Data For A Specific Tab Only. This Cannot Be Undone.</p>
   </div></div>
 </div>`;
 const cs=$('#cache-size');
 if(cs){
  cs.textContent=fmtBytes(encBytes());
  if(navigator.storage&&navigator.storage.estimate){
   navigator.storage.estimate().then(e=>{
    if(e&&e.usage!=null&&cs.isConnected)cs.textContent=fmtBytes(e.usage)+' ('+fmtBytes(encBytes())+' Encrypted)';
   }).catch(()=>{});
  }
 }
 const rad=$('#adv-radius'),radV=$('#adv-rv');
 if(rad){
  rad.addEventListener('input',()=>{
   const v=+rad.value;
   document.documentElement.style.setProperty('--radius',v+'px');
   if(radV)radV.textContent=v+'px';
  });
  rad.addEventListener('change',()=>{
   settings.adv.radius=+rad.value;
   saveSettings();
   toast('Card Radius: '+rad.value+'px','sliders-horizontal');
  });
 }
 const aiOn=$('#ai-on'),prov=$('#ai-provider');
 aiOn.addEventListener('change',()=>{settings.ai.on=aiOn.checked;saveSettings();toast(aiOn.checked?'AI Assistant Enabled':'AI Assistant Disabled','bot')});
 prov.addEventListener('change',()=>{$('#ai-endpoint').value=AI_PROVIDERS[prov.value][1]});
 $('#px-on').addEventListener('change',e=>{settings.proxy.on=e.target.checked;saveSettings()});
 $('#px-auth').addEventListener('change',e=>{settings.proxy.auth=e.target.checked;saveSettings();$('#px-authrow').style.display=e.target.checked?'':'none'});
  $('#lk-on').addEventListener('change',async e=>{
   const on=e.target.checked;
   if(on){
    if(!settings.lock.pass_set){e.target.checked=false;toast('Set A Password First','alert-triangle');const p=$('#lk-p1');p&&p.focus();return}
    settings.lock.on=true;saveSettings();toast('App Lock Enabled - Active On Next Start','lock');
   }else{
    const cur=$('#lk-cur');
    if(!cur||!cur.value){e.target.checked=true;toast('Enter Current Password To Disable','alert-triangle');cur&&cur.focus();return}
    const r=await fetch('/api/unlock',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({passphrase:cur.value})});
    if(!r.ok){const j=await r.json().catch(()=>({}));e.target.checked=true;toast(j.detail||'Wrong Current Password','alert-triangle');cur.classList.add('err');return}
    settings.lock.on=false;saveSettings();toast('App Lock Disabled','lock-open');
   }
  });
 $('#ip-on').addEventListener('change',async e=>{
  const on=e.target.checked;
  if(Sync.on){
   if(on){
    if(!settings.imgProt.hash){e.target.checked=false;toast('Set A Passphrase First','alert-triangle');$('#ip-p1').focus();return}
    const r=await fetch('/api/images/enabled',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({on:true})});
    if(r.ok){settings.imgProt.on=true;saveSettings();toast('Image Protection Enabled - Server-Side Encryption Active','shield')}
    else{e.target.checked=false;toast('Could Not Enable Image Protection','alert-triangle')}
   }else{
    const cur=$('#ip-cur');
    if(!cur||!cur.value){e.target.checked=true;toast('Enter Current Passphrase To Disable','alert-triangle');cur&&cur.focus();return}
    const u=await fetch('/api/images/unlock',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({passphrase:cur.value})});
    if(!u.ok){e.target.checked=true;toast('Wrong Passphrase','alert-triangle');return}
    const d=await fetch('/api/images/enabled',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({on:false})});
    if(!d.ok){e.target.checked=true;toast('Could Not Disable Image Protection - Is It Unlocked?','alert-triangle');return}
    settings.imgProt.on=false;saveSettings();toast('Image Protection Disabled','shield-off');
    reloadFailedBackendImages();   // blobs were just decrypted — retry any 423'd images
   }
   return;
  }
  if(on){
   if(!HAS_SUBTLE){e.target.checked=false;toast('WebCrypto Is Unavailable In This Context','alert-triangle');return}
   if(!settings.imgProt.hash){e.target.checked=false;toast('Set A Passphrase First','alert-triangle');$('#ip-p1').focus();return}
   settings.imgProt.on=true;saveSettings();toast('Image Protection Enabled','shield');
  }else{
   const cur=$('#ip-cur');
   if(!cur||!cur.value){e.target.checked=true;toast('Enter Current Passphrase To Disable','alert-triangle');cur&&cur.focus();return}
   if(!(await passMatches(cur.value,settings.imgProt.hash))){e.target.checked=true;toast('Wrong Passphrase','alert-triangle');cur.classList.add('err');return}
   settings.imgProt.on=false;encKey=null;saveSettings();toast('Image Protection Disabled','shield-off');
  }
 });
}
