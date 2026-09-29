"use strict";
/* ===== SEED DATA ===== */
const DIRECTORS=['M. Castellane','A. Voss','J. Devereaux','R. Okada','L. Marchetti','S. Kane','P. Lindqvist','D. Aris'];
const ETH=['Caucasian','Latina','East Asian','Black','Mixed','South Asian'];
const HAIR=['Black','Brunette','Blonde','Auburn','Red','Brown'];
const EYES=['Brown','Hazel','Blue','Green','Grey'];
const BOOBS=['Natural','Enhanced'];
const CATS_POOL=['Cinematic','Romance','Amateur','Professional','VR','Classic'];
const DESCS=[
 t=>`${t} is a feature shot on location over five nights. Natural light, a slow-building score and long unbroken takes carry the story from dusk to early morning.`,
 t=>`Shot on 35mm with a reduced crew, ${t} keeps its focus on atmosphere: practical sets, lived-in rooms, and a soundtrack recorded live on set.`,
 t=>`${t} collects three connected vignettes set in the same apartment across a single year. Minimal dialogue, textured sound design, a restrained palette.`,
 t=>`A four-chapter feature produced for a limited run. ${t} was later reissued with restored color grading and a new cut.`,
];
const SITES={
 movie:[['Aurelia Network','aurelia.network'],['NoirPass','noirpass.com'],['VelvetLine','velvetline.tv'],['Luma Studios','lumastudios.tv'],['PrivateCinema','privatecinema.io']],
 scene:[['Aurelia Network','aurelia.network'],['NoirPass','noirpass.com'],['VelvetLine','velvetline.tv'],['Luma Studios','lumastudios.tv'],['PrivateCinema','privatecinema.io']],
 performer:[['PerfDB','perfdb.net'],['Performer Index','performerindex.com'],['Scene Archive','scenearchive.io']],
};
const AI_PROVIDERS={
 openai:['OpenAI','https://api.openai.com/v1'],
 anthropic:['Anthropic','https://api.anthropic.com/v1'],
 gemini:['Google Gemini','https://generativelanguage.googleapis.com/v1'],
 custom:['Custom / Local (OpenAI-Compatible)','http://localhost:11434/v1'],
};
const DB={movies:[],scenes:[],performers:[],studios:[],categories:[]};

/* ===== STATE ===== */
const DEF_SETTINGS={
  theme:'dark',player:'internal',dirs:[],catLimit:10,cwLimit:4,perPage:{movies:24,scenes:24,performers:24,studios:24,categories:24},
  cardWidths:{movies:220,scenes:250,performers:180,studios:200,categories:200},
  adv:{accent:'',background:'',font:'',radius:null,border:'1'},
  sources:{movie:[],scene:[],performer:[]},
  scrapers:[],pyScrapers:false,
  proxy:{on:false,proto:'http',host:'',port:'',auth:false,user:'',pass:''},
  ai:{on:false,provider:'openai',endpoint:'https://api.openai.com/v1',model:'gpt-4o-mini',key:''},
  lock:{on:false,hash:''},
  imgProt:{on:false,salt:'',hash:''},
  share:{platforms:['x','reddit','telegram','whatsapp'],watermark:true,caption:true,defaultCaption:'',captions:{},defaultCaptions:{movie:'',scene:'',performer:'',studio:''}}
};
let settings=JSON.parse(JSON.stringify(DEF_SETTINGS));
try{
 const s=JSON.parse(localStorage.getItem('obscura:v1')||'null');
 if(s)settings={...settings,...s,
  adv:{...settings.adv,...(s.adv||{})},
  sources:{movie:[],scene:[],performer:[],...(s.sources||{})},
  scrapers:Array.isArray(s.scrapers)?s.scrapers:[],
  pyScrapers:!!s.pyScrapers,
  proxy:{...settings.proxy,...(s.proxy||{})},
  ai:{...settings.ai,...(s.ai||{})},
  lock:{...settings.lock,...(s.lock||{})},
  imgProt:{...settings.imgProt,...(s.imgProt||{})},
  share:{...settings.share,...(s.share||{})}};
 if(!settings.catLimit)settings.catLimit=10;
 if(!settings.cwLimit)settings.cwLimit=4;
 if(typeof settings.perPage==='number')settings.perPage={movies:settings.perPage,scenes:settings.perPage,performers:settings.perPage,studios:settings.perPage,categories:settings.perPage};
 if(!settings.perPage||typeof settings.perPage!=='object')settings.perPage={};
 ['movies','scenes','performers','studios','categories'].forEach(k=>{if(!settings.perPage[k])settings.perPage[k]=24});
 if(!settings.proxy.proto)settings.proxy.proto='http';
 if(!settings.adv)settings.adv={accent:'',background:'',font:'',radius:null,border:'1'};
}catch(e){}
function saveSettings(){try{localStorage.setItem('obscura:v1',JSON.stringify(settings))}catch(e){}Sync.pushSettings()}
async function refreshScrapers(){
 if(!Sync.on)return;
 try{
  const r=await fetch('/api/scrapers');
  if(!r.ok)return;
  const list=await r.json();
  if(Array.isArray(list))settings.scrapers=list;
 }catch(e){}
}
function applyTheme(){document.documentElement.dataset.theme=settings.theme}
applyTheme();
applyAdvanced();

const T={
  movies:{q:'',view:'grid',cw:settings.cardWidths?.movies||220,page:1,f:{studios:new Set(),cats:new Set(),performers:new Set(),ymin:'',ymax:'',sort:'new'}},
  scenes:{q:'',view:'grid',cw:settings.cardWidths?.scenes||250,page:1,f:{studios:new Set(),cats:new Set(),performers:new Set(),ymin:'',ymax:'',sort:'new'}},
  performers:{q:'',view:'grid',cw:settings.cardWidths?.performers||180,page:1,f:{gender:'',nationalities:new Set(),hairColors:new Set(),ethnicities:new Set(),boobType:'',piercings:'',tattoos:'',csMin:'',csMax:'',heightMin:'',heightMax:'',sort:'az'}},
  studios:{q:'',view:'grid',cw:settings.cardWidths?.studios||200,page:1},categories:{q:'',view:'grid',cw:settings.cardWidths?.categories||200,page:1}
};
const state={view:{name:'tab',tab:'movies'},history:[],profileTab:'favorites'};
const catExpand={};const castExpand={};const descExpand={};const infoExpand={};let lastScanDir=null;
const bulkSel={active:false,selected:new Set()};
const byId=(kind,id)=>({movie:DB.movies,scene:DB.scenes,performer:DB.performers,studio:DB.studios,category:DB.categories}[kind]||[]).find(x=>x.id===id);
const KIND_SING={movies:'movie',scenes:'scene',performers:'performer',studios:'studio',categories:'category'};
const byIdKind=(tab,id)=>{for(const k of['movies','scenes','performers','studios','categories']){if(DB[k].find(x=>x.id===id))return KIND_SING[k]}return null};
const byTabId=(tab,id)=>byId(KIND_SING[tab]||tab,id);
const kindPlural=k=>({movie:'movies',scene:'scenes',performer:'performers',studio:'studios',category:'categories'})[k];
const kindLabel=k=>({movie:'Movie',scene:'Scene',performer:'Performer',studio:'Studio',category:'Category'})[k]||k;
const catUsage=c=>DB.movies.filter(m=>ensureArr(m.categoryIds).includes(c.id)).length+DB.scenes.filter(s=>ensureArr(s.categoryIds).includes(c.id)).length;
const favCount=()=>DB.movies.filter(m=>m.fav).length+DB.scenes.filter(s=>s.fav).length;
const TABS={
 movies:{crumb:'Library',title:'Movies',icon:'film',ph:'Search Movies, Studios, Cast...'},
 scenes:{crumb:'Library',title:'Scenes',icon:'clapperboard',ph:'Search Scenes, Studios...'},
 performers:{crumb:'Library',title:'Performers',icon:'users',ph:'Search Performers...'},
 studios:{crumb:'Library',title:'Studios',icon:'building-2',ph:'Search Studios...'},
 categories:{crumb:'Library',title:'Categories',icon:'tag',ph:'Search Categories...'},
 profile:{crumb:'Library',title:'Profile',icon:'user'},
 playlists:{crumb:'Profile',title:'Playlists',icon:'list-music'},
 settings:{crumb:'System',title:'Settings',icon:'settings'},
 about:{crumb:'System',title:'About',icon:'info'}
};
function go(v){state.history.push(state.view);state.view=v;render();$('#main').scrollTop=0}
function goBack(){const p=state.history.pop();if(p){state.view=p;render();$('#main').scrollTop=0}}
function smartBack(kind){if(state.history.length)goBack();else{state.view={name:'tab',tab:kindPlural(kind)};render()}}
function resolvePerformer(name){const n=titleCase(name.trim());const q=n.toLowerCase();let p=DB.performers.find(p=>p.name.toLowerCase()===q);if(!p){p={id:uid('p'),name:n,gender:'f',photo:img('perf-'+slug(n),600,800)};DB.performers.push(p);Sync.push('performers','create',p)}return p.id}
function resolveCategory(name){const n=titleCase(name.trim());const q=n.toLowerCase();let c=DB.categories.find(c=>c.name.toLowerCase()===q);if(!c){c={id:uid('c'),name:n,icon:'tag',desc:''};DB.categories.push(c);Sync.push('categories','create',c)}return c.id}
function resolveStudio(name){const n=titleCase(name.trim());const q=n.toLowerCase();let s=DB.studios.find(s=>s.name.toLowerCase()===q);if(!s){s={id:uid('st'),name:n,url:'',country:'',desc:'',logo:'',twitter:null,instagram:null};DB.studios.push(s);Sync.push('studios','create',s)}return s.id}
function findMovieByTitle(name){if(!name)return null;const q=name.trim().toLowerCase();return DB.movies.find(m=>m.title.toLowerCase()===q)||null}
function resolveMovie(name,studioId){
 const n=titleCase((name||'').trim());if(!n)return null;
 let m=findMovieByTitle(n);
 if(!m){m={id:uid('mv'),title:n,studioId:studioId||null,year:null,durationMin:0,scenes:0,director:'',actorIds:[],categoryIds:[],fav:false,desc:'',posterF:'',posterB:''};DB.movies.push(m);Sync.push('movies','create',m)}
 return m;
}
const catsOf=it=>ensureArr(it.categoryIds).map(cid=>DB.categories.find(c=>c.id===cid)?.name).filter(Boolean);
const actorsOf=it=>ensureArr(it.actorIds).map(id=>DB.performers.find(p=>p.id===id)?.name).filter(Boolean);
