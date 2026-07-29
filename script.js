let SITES = [], cache = {}, charts = {};
let curSite = null, curMonth = "2026-07", activeDim = "brand";

const C = { teal:"#0e6f56", orange:"#e8892e", blue:"#5b7fd4", slate:"#c7cbc8", red:"#d9534f" };
const PALETTE = [C.teal, C.orange, C.blue, "#8b6fd6", "#3fb6c9", "#c9a227", C.red, "#9aa39c"];

const BRAND_DOMAINS = {
  "OPEL":"opel.com","PEUGEOT":"peugeot.com","RENAULT":"renault.com","CITROEN":"citroen.com",
  "VOLKSWAGEN":"volkswagen.com","BMW":"bmw.com","MERCEDES":"mercedes-benz.com","FORD":"ford.com",
  "DACIA":"dacia.com","NISSAN":"nissan.com","SEAT":"seat.com","FIAT":"fiat.com","AUDI":"audi.com",
  "TOYOTA":"toyota.com","SKODA":"skoda-auto.com","DS AUTOMOBILES":"dsautomobiles.com",
  "HYUNDAI":"hyundai.com","KIA":"kia.com","VOLVO":"volvocars.com","MINI":"mini.com",
  "SUZUKI":"suzuki.com","MAZDA":"mazda.com","HONDA":"honda.com","JEEP":"jeep.com",
  "LAND ROVER":"landrover.com","PORSCHE":"porsche.com"
};
function logo(n){ const d = BRAND_DOMAINS[(n||"").trim().toUpperCase()]; return d ? "https://logo.clearbit.com/"+d+"?size=64" : null; }

const ICONS = {
  droplet:'<path d="M12 2.69s5.66 5.86 5.66 10a5.66 5.66 0 0 1-11.32 0C6.34 8.55 12 2.69 12 2.69Z"/>',
  fuel:'<line x1="3" x2="15" y1="22" y2="22"/><line x1="4" x2="14" y1="9" y2="9"/><path d="M14 22V4a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v18"/><path d="M14 13h2a2 2 0 0 1 2 2v2a2 2 0 0 0 2 2a2 2 0 0 0 2-2V9.83a2 2 0 0 0-.59-1.42L18 5"/>',
  zap:'<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
  leaf:'<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/><path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>',
  wind:'<path d="M12.8 19.6A2 2 0 1 0 14 16H2"/><path d="M17.5 8a2.5 2.5 0 1 1 2 4H2"/><path d="M9.8 4.4A2 2 0 1 1 11 8H2"/>'
};
function fuelKey(n){ const f=(n||"").toUpperCase();
  if(f.includes("HIBRIDO")||f.includes("HYBRIDE"))return"leaf";
  if(f.includes("ELECTRI"))return"zap";
  if(f.includes("GASOLEO")||f.includes("DIESEL"))return"droplet";
  if(f.includes("GPL")||f.includes("GNV"))return"wind";
  return"fuel"; }
function icon(k,c){ return '<svg viewBox="0 0 24 24" fill="none" stroke="'+c+'" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'+(ICONS[k]||ICONS.fuel)+'</svg>'; }


/* ---- marqueur de lancement V2 : trait vertical date + zone teintee ---- */
const V2_MARK = {
  id: "v2mark",
  beforeDatasetsDraw(chart){
    const o = chart.options.plugins && chart.options.plugins.v2mark;
    if(!o || !o.on) return;
    const a = chart.chartArea, ctx = chart.ctx, xs = chart.scales.x;
    if(!a) return;
    ctx.save();
    const px = (o.index != null && xs) ? xs.getPixelForValue(o.index) : a.left;
    ctx.fillStyle = "rgba(14,111,86,.07)";
    ctx.fillRect(px, a.top, a.right - px, a.bottom - a.top);
    if(o.index != null){
      ctx.setLineDash([5,4]); ctx.lineWidth = 1.6; ctx.strokeStyle = "#0e6f56";
      ctx.beginPath(); ctx.moveTo(px, a.top); ctx.lineTo(px, a.bottom); ctx.stroke();
      ctx.setLineDash([]);
    }
    if(o.label){
      ctx.font = '600 10.5px -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif';
      const w = ctx.measureText(o.label).width + 14;
      let lx = (o.index != null) ? px + 6 : a.right - w - 2;
      if(lx + w > a.right - 2) lx = a.right - w - 2;
      if(lx < a.left) lx = a.left;
      ctx.fillStyle = "#0e6f56";
      ctx.fillRect(lx, a.top + 4, w, 18);
      ctx.fillStyle = "#fff"; ctx.textBaseline = "middle"; ctx.textAlign = "left";
      ctx.fillText(o.label, lx + 7, a.top + 13);
    }
    ctx.restore();
  }
};
Chart.register(V2_MARK);

function v2DateFR(d){ const s = d.v2_date; return s ? s.slice(8,10)+"/"+s.slice(5,7) : ""; }
/* axisDates : tableau "MM-DD" correspondant a l'axe X du graphe */
function v2Mark(d, axisDates){
  const iso = d.v2_date; if(!iso || !axisDates.length) return { on:false };
  const key = iso.slice(5,7)+"-"+iso.slice(8,10), dd = v2DateFR(d);
  const i = axisDates.indexOf(key);
  if(i >= 0) return { on:true, index:i, label:"V2 \u2014 "+dd };
  if(axisDates[0] > key) return { on:true, index:null, label:"Post-V2 (depuis le "+dd+")" };
  return { on:false };
}
function monthAxis(mk, days){
  const mm = mk.slice(5,7), a = [];
  for(let i=1;i<=days;i++) a.push(mm+"-"+String(i).padStart(2,"0"));
  return a;
}

function kill(k){ if(charts[k]){ charts[k].destroy(); delete charts[k]; } }
function fmt(n){ return (n==null||isNaN(n)) ? "—" : Number(n).toLocaleString("fr-FR",{maximumFractionDigits:1}); }
function pct(n){ return fmt(n)+" %"; }
function esc(s){ return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;"); }
function slug(s){ return s.toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/(^-|-$)/g,""); }
function badge(v,unit){ const c=v>=0?"up":"down", a=v>=0?"↑":"↓";
  return '<span class="badge '+c+'">'+a+" "+fmt(Math.abs(v))+" "+unit+"</span>"; }
function prevMonth(m){ if(m==="total") return null;
  const i=(cache[curSite].months||[]).indexOf(m); return i>0 ? cache[curSite].months[i-1] : null; }

/* ==================== INIT ==================== */
async function init(){
  SITES = (await (await fetch("data/index.json")).json()).sites;
  document.getElementById("siteTabs").innerHTML = SITES.map((s,i)=>
    '<button class="site-tab'+(i===0?" active":"")+'" data-site="'+esc(s)+'"><span class="dot"></span>'+esc(s)+'</button>').join("");
  document.querySelectorAll(".site-tab").forEach(b=>b.addEventListener("click",async()=>{
    document.querySelectorAll(".site-tab").forEach(x=>x.classList.remove("active"));
    b.classList.add("active"); await load(b.dataset.site);
  }));
  document.querySelectorAll(".section-tab").forEach(b=>b.addEventListener("click",()=>{
    document.querySelectorAll(".section-tab").forEach(x=>x.classList.remove("active"));
    b.classList.add("active");
    document.querySelectorAll(".panel").forEach(p=>p.classList.remove("active"));
    document.getElementById("panel-"+b.dataset.section).classList.add("active");
  }));
  await load(SITES[0]);
}

async function load(site){
  curSite = site;
  document.getElementById("pageTitle").textContent = site;
  document.getElementById("crumbSite").textContent = site;
  if(!cache[site]) cache[site] = await (await fetch("data/"+slug(site)+".json")).json();
  const d = cache[site];
  const per = d.periods || d.months;
  if(per.indexOf(curMonth)<0) curMonth = per[per.length-1];
  document.getElementById("monthTabs").innerHTML = per.map(m=>
    '<button class="month-tab'+(m===curMonth?" active":"")+(m==="total"?" month-tab-total":"")+'" data-m="'+m+'">'+
    (m==="total" ? "Total" : d.meta[m].label.replace(" 2026",""))+'</button>').join("");
  document.querySelectorAll(".month-tab").forEach(b=>b.addEventListener("click",()=>{
    curMonth = b.dataset.m;
    document.querySelectorAll(".month-tab").forEach(x=>x.classList.remove("active"));
    b.classList.add("active"); render();
  }));
  render();
}

function render(){
  const d = cache[curSite];
  document.getElementById("pageSub").textContent = (isTotal(curMonth)? "Cumul avril → juillet 2026" : d.meta[curMonth].label) + " · leads, trafic et parcours de reprise";
  const pn=document.getElementById("partialNotice");
  pn.hidden = !d.meta[curMonth].partial;
  if(!pn.hidden){
    pn.querySelector("p").innerHTML = isTotal(curMonth)
      ? "La période cumule <strong>119 jours</strong> (01/04 → 28/07). Juillet n'en compte que 28 : ce mois pèse donc un peu moins que les autres dans les totaux."
      : "Juillet ne couvre que <strong>28 jours</strong> au lieu de 30 ou 31. Les totaux mensuels ne sont donc pas comparables tels quels — toutes les évolutions affichées sont calculées en <strong>moyenne par jour</strong>.";
  }
  const vd=document.getElementById("v2DateLabel");
  if(vd) vd.textContent = "Lancement V2 : " + (d.v2_date ? d.v2_date.slice(8,10)+"/"+d.v2_date.slice(5,7)+"/"+d.v2_date.slice(0,4) : "—");
  renderLeads(d); renderTraffic(d); renderFunnel(d);
}

/* helpers periode */
function isTotal(mk){ return mk==="total"; }
function monthIdx(d,mk){ if(isTotal(mk)) return d.daily.d.map((_,i)=>i);
  const r=[]; d.daily.d.forEach((x,i)=>{ if("2026-"+x.slice(0,2)===mk) r.push(i); }); return r; }
function leadsPerDay(d,mk){ const L=d.leads[mk]; return L ? L.total/d.meta[mk].days : null; }
function convOf(d,mk){ const L=d.leads[mk], R=d.repriseMonth[mk];
  return (L&&R&&R.sessions) ? L.total/R.sessions*100 : null; }

/* ==================== LEADS ==================== */
function renderLeads(d){
  const mk=curMonth, L=d.leads[mk], meta=d.meta[mk], R=d.repriseMonth[mk];
  const pm=prevMonth(mk);
  const conv=convOf(d,mk), convPrev=pm?convOf(d,pm):null;
  const lpd=leadsPerDay(d,mk), lpdPrev=pm?leadsPerDay(d,pm):null;

  document.getElementById("leadsHero").innerHTML =
    '<div class="hero-card"><div class="hero-icon">'+icon("zap","#fff")+'</div><div class="hero-body">'+
    '<p class="hero-label">Taux de conversion — sessions outil de reprise → leads</p>'+
    '<p class="hero-value">'+pct(conv)+'<span class="hero-sub">'+meta.label+'</span>'+
    (convPrev!=null ? '<span class="hero-badge">'+(conv-convPrev>=0?"↑":"↓")+" "+fmt(Math.abs(conv-convPrev))+' pts vs '+d.meta[pm].label.replace(" 2026","")+'</span>' : '')+
    '</p><p class="hero-note">'+fmt(L.total)+' leads pour '+fmt(R.sessions)+' sessions sur l\'outil de reprise · '+
    fmt(lpd)+' leads / jour sur '+meta.days+' jours</p></div></div>';

  document.getElementById("leadsKpis").innerHTML =
    kpi(isTotal(mk)?"Leads sur la période":"Leads du mois", fmt(L.total), meta.days+" jours de données") +
    kpi("Leads / jour", fmt(lpd), null, lpdPrev!=null?badge((lpd-lpdPrev)/lpdPrev*100,"%"):null) +
    kpi("Sessions outil de reprise", fmt(R.sessions), fmt(R.sessions/R.rdays)+" / jour") +
    kpi("Conversion", pct(conv), null, convPrev!=null?badge(conv-convPrev,"pts"):null);

  // graphe quotidien du mois
  document.getElementById("leadsDailySub").textContent = isTotal(mk) ? "01/04 → 28/07 · 119 jours" : meta.label;
  kill("ld");
  charts.ld=new Chart(document.getElementById("leadsDailyChart"),{type:"line",
    data:{labels:(isTotal(mk)? d.daily.d.map(x=>x.slice(3)+"/"+x.slice(0,2)) : L.daily.map((_,i)=>String(i+1))),
      datasets:[{label:"Leads",data:L.daily,
      borderColor:C.teal,backgroundColor:grad(C.teal),fill:true,tension:.35,pointRadius:0,pointHoverRadius:5,borderWidth:2.4}]},
    options:(()=>{ const o=lineOpt(isTotal(mk)?12:14);
      o.plugins.v2mark=v2Mark(d, isTotal(mk)? d.daily.d : monthAxis(mk, meta.days)); return o; })()});

  // tendance 4 mois
  const ms=d.months.filter(m=>d.leads[m]);
  kill("lt");
  charts.lt=new Chart(document.getElementById("leadsTrendChart"),{
    data:{labels:ms.map(m=>d.meta[m].label.replace(" 2026","")),
      datasets:[
        {type:"bar",label:"Leads / jour",data:ms.map(m=>leadsPerDay(d,m)),
         backgroundColor:ms.map(m=>m===mk?C.teal:"#cfdbd6"),borderRadius:6,maxBarThickness:46,yAxisID:"y"},
        {type:"line",label:"Conversion (%)",data:ms.map(m=>convOf(d,m)),borderColor:C.orange,
         backgroundColor:"transparent",tension:.3,pointRadius:4,pointBackgroundColor:C.orange,borderWidth:2.4,yAxisID:"y1"}
      ]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false},tooltip:tip()},
      scales:{x:{grid:{display:false},border:{display:false},ticks:tk()},
        y:{beginAtZero:true,grid:{color:"#eef0ee"},border:{display:false},ticks:tk(),title:{display:true,text:"Leads / jour",color:"#949a94",font:{size:10.5}}},
        y1:{position:"right",beginAtZero:true,grid:{display:false},border:{display:false},
            ticks:{...tk(),callback:v=>v+" %"}}}}});

  buildDims(d,L);
  donut("entryChart","dEntry","entryLegend","entryCenter",Object.entries(L.entry).sort((a,b)=>b[1]-a[1]));
  donut("projectChart","dProj","projectLegend","projectCenter",L.project);
}

function kpi(label,val,sub,extra){
  return '<div class="kpi"><p class="label">'+label+'</p><p class="value">'+val+'</p>'+
    '<div class="kpi-foot">'+(extra||"")+(sub?'<span class="sub">'+sub+'</span>':"")+'</div></div>';
}

const DIMS=[
  {k:"brand",l:"Marque reprise",g:L=>L.brand,logo:true},
  {k:"fuel",l:"Carburant",g:L=>L.fuel,fuel:true},
  {k:"source",l:"Source",g:L=>L.source},
  {k:"code",l:"Code marketing",g:L=>L.code}
];
function buildDims(d,L){
  document.getElementById("dimSub").textContent="Répartition par dimension · "+d.meta[curMonth].label;
  const el=document.getElementById("dimTabs");
  el.innerHTML=DIMS.map(x=>'<button class="dim-tab'+(x.k===activeDim?" active":"")+'" data-d="'+x.k+'">'+x.l+'</button>').join("");
  el.querySelectorAll(".dim-tab").forEach(b=>b.addEventListener("click",()=>{
    activeDim=b.dataset.d;
    el.querySelectorAll(".dim-tab").forEach(x=>x.classList.remove("active"));
    b.classList.add("active"); dimList(L);
  }));
  dimList(L);
}
function dimList(L){
  const dim=DIMS.find(x=>x.k===activeDim)||DIMS[0];
  const pairs=(dim.g(L)||[]).slice();
  const total=pairs.reduce((s,p)=>s+p[1],0)||1;
  const top=pairs.slice(0,8), max=top.length?top[0][1]:1;
  document.getElementById("dimList").innerHTML=top.map((p,i)=>{
    const col=PALETTE[i%PALETTE.length], ini=(p[0]||"?").trim().charAt(0).toUpperCase();
    let b;
    if(dim.logo&&logo(p[0])) b='<span class="rank-badge" style="background:#fff;border:1px solid var(--border)"><img src="'+logo(p[0])+'" alt="" loading="lazy" onerror="this.parentElement.style.background=\''+col+'\';this.parentElement.style.border=\'none\';this.parentElement.textContent=\''+ini+'\';"></span>';
    else if(dim.fuel) b='<span class="rank-badge" style="background:'+col+'22">'+icon(fuelKey(p[0]),col)+'</span>';
    else b='<span class="rank-badge" style="background:'+col+'">'+ini+'</span>';
    return '<div class="rank-row"><div class="rank-name"><span class="rank-idx">'+(i+1)+'</span>'+b+
      '<span class="rank-label" title="'+esc(p[0])+'">'+esc(p[0])+'</span></div>'+
      '<div class="rank-share"><span class="rank-track"><span class="rank-fill" style="width:'+(p[1]/max*100).toFixed(1)+'%;background:'+col+'"></span></span>'+
      '<span class="rank-pct">'+fmt(p[1]/total*100)+' %</span></div>'+
      '<div class="rank-value">'+fmt(p[1])+'</div></div>';
  }).join("");
  const shown=top.reduce((s,p)=>s+p[1],0), rest=pairs.length-top.length;
  document.getElementById("dimFoot").textContent=
    fmt(shown)+" leads affichés sur "+fmt(total)+" ("+fmt(shown/total*100)+" %)"+
    (rest>0?" · "+rest+" autre"+(rest>1?"s":"")+" valeur"+(rest>1?"s":""):"");
}
function donut(canvas,key,legendId,centerId,pairs){
  const top=pairs.slice(0,5), total=pairs.reduce((s,p)=>s+p[1],0);
  kill(key);
  charts[key]=new Chart(document.getElementById(canvas),{type:"doughnut",
    data:{labels:top.map(p=>p[0]),datasets:[{data:top.map(p=>p[1]),backgroundColor:PALETTE,borderColor:"#fff",borderWidth:3,hoverOffset:5}]},
    options:{responsive:true,maintainAspectRatio:false,cutout:"72%",plugins:{legend:{display:false},tooltip:tip()}}});
  document.getElementById(centerId).textContent=fmt(total);
  document.getElementById(legendId).innerHTML=top.map((p,i)=>
    '<div class="dl-row"><span class="dl-dot" style="background:'+PALETTE[i%PALETTE.length]+'"></span>'+
    '<span class="dl-name" title="'+esc(p[0])+'">'+esc(p[0])+'</span>'+
    '<span class="dl-value">'+fmt(p[1])+'</span><span class="dl-pct">'+fmt(p[1]/(total||1)*100)+' %</span></div>').join("");
}

/* ==================== TRAFIC ==================== */
function renderTraffic(d){
  const mk=curMonth, T=d.trafficMonth[mk], R=d.repriseMonth[mk], meta=d.meta[mk];
  const pm=prevMonth(mk);
  const spd=T.tdays?T.sessions/T.tdays:0;
  const rpd=R.rdays?R.sessions/R.rdays:0;
  const part=T.sessions?R.sessions/T.sessions*100:0;
  const L=d.leads[mk];
  const spdP=pm&&d.trafficMonth[pm].tdays?d.trafficMonth[pm].sessions/d.trafficMonth[pm].tdays:null;
  const rpdP=pm&&d.repriseMonth[pm].rdays?d.repriseMonth[pm].sessions/d.repriseMonth[pm].rdays:null;
  const partP=pm&&d.trafficMonth[pm].sessions?d.repriseMonth[pm].sessions/d.trafficMonth[pm].sessions*100:null;
  const per1k=T.sessions?L.total/T.sessions*1000:0;
  const per1kP=pm&&d.trafficMonth[pm].sessions?d.leads[pm].total/d.trafficMonth[pm].sessions*1000:null;

  document.getElementById("trafficKpis").innerHTML =
    kpi("Sessions site parent", fmt(T.sessions), fmt(spd)+" / jour",
        spdP!=null?badge((spd-spdP)/spdP*100,"%"):null) +
    kpi("Sessions outil de reprise", fmt(R.sessions), fmt(rpd)+" / jour",
        rpdP!=null?badge((rpd-rpdP)/rpdP*100,"%"):null) +
    kpi("Part vers la reprise", pct(part), "des sessions du site",
        partP!=null?badge(part-partP,"pts"):null) +
    kpi("Leads / 1 000 sessions site", fmt(per1k), "chaîne complète",
        per1kP!=null?badge((per1k-per1kP)/per1kP*100,"%"):null);

  const idx=monthIdx(d,mk);
  const lab=idx.map(i=> isTotal(mk) ? d.daily.d[i].slice(3)+"/"+d.daily.d[i].slice(0,2) : d.daily.d[i].slice(3));
  document.getElementById("trafficDailySub").textContent=(isTotal(mk)?"01/04 → 28/07":meta.label)+" · même échelle";
  document.getElementById("trafficLegend").innerHTML=
    '<div class="legend-item"><span class="swatch" style="background:'+C.teal+'"></span><span class="lname">Site parent</span><span class="lvalue">'+fmt(T.sessions)+'</span></div>'+
    '<div class="legend-item"><span class="swatch" style="background:'+C.orange+'"></span><span class="lname">Outil de reprise</span><span class="lvalue">'+fmt(R.sessions)+'</span></div>';
  kill("tr");
  charts.tr=new Chart(document.getElementById("trafficChart"),{type:"line",
    data:{labels:lab,datasets:[
      {label:"Site parent",data:idx.map(i=>d.daily.u[i]),borderColor:C.teal,backgroundColor:grad(C.teal),fill:true,tension:.3,pointRadius:0,pointHoverRadius:5,borderWidth:2.4},
      {label:"Outil de reprise",data:idx.map(i=>d.daily.rep[i]),borderColor:C.orange,backgroundColor:"transparent",tension:.3,pointRadius:0,pointHoverRadius:5,borderWidth:2.4}]},
    options:(()=>{ const o=lineOpt(isTotal(mk)?12:16);
      o.plugins.v2mark=v2Mark(d, idx.map(i=>d.daily.d[i])); return o; })()});

  const ms=d.months;
  kill("tt");
  charts.tt=new Chart(document.getElementById("trafficTrendChart"),{type:"bar",
    data:{labels:ms.map(m=>d.meta[m].label.replace(" 2026","")),datasets:[
      {label:"Site parent / jour",data:ms.map(m=>d.trafficMonth[m].tdays?d.trafficMonth[m].sessions/d.trafficMonth[m].tdays:0),backgroundColor:C.teal,borderRadius:6,maxBarThickness:32},
      {label:"Reprise / jour",data:ms.map(m=>d.repriseMonth[m].rdays?d.repriseMonth[m].sessions/d.repriseMonth[m].rdays:0),backgroundColor:C.orange,borderRadius:6,maxBarThickness:32,yAxisID:"y1"}]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:true,position:"top",align:"end",labels:leg()},tooltip:tip()},
      scales:{x:{grid:{display:false},border:{display:false},ticks:tk()},
        y:{beginAtZero:true,grid:{color:"#eef0ee"},border:{display:false},ticks:tk()},
        y1:{position:"right",beginAtZero:true,grid:{display:false},border:{display:false},ticks:tk()}}}});

  // part quotidienne vers la reprise, entierement calculee a partir des deux series de sessions
  document.getElementById("partSub").textContent=(isTotal(mk)?"01/04 → 28/07":meta.label)+" · moyenne "+pct(part);
  const serie=idx.map(i=>{ const u=d.daily.u[i], r=d.daily.rep[i];
    return (u&&u>0&&r!=null) ? r/u*100 : null; });
  kill("pa");
  charts.pa=new Chart(document.getElementById("partChart"),{type:"line",
    data:{labels:lab,datasets:[{label:"Part vers la reprise",data:serie,
      borderColor:C.blue,backgroundColor:grad(C.blue),fill:true,tension:.3,pointRadius:0,pointHoverRadius:5,borderWidth:2.2}]},
    options:(()=>{ const o=lineOpt(isTotal(mk)?12:16);
      o.plugins.v2mark=v2Mark(d, idx.map(i=>d.daily.d[i]));
      o.plugins.tooltip={...tip(),callbacks:{label:c=>pct(c.parsed.y)}};
      o.scales.y.ticks={...tk(),callback:v=>v+" %"};
      return o; })()});
}

/* ==================== FUNNEL ==================== */
function renderFunnel(d){
  const mk=curMonth, isJuly=(mk==="2026-07"&&d.v2), FM=d.funnelMonth[mk];

  // tendance : avril, mai, juin, juillet pre-V2, juillet post-V2
  const pts=[], vals=[], cols=[];
  d.months.forEach(m=>{
    if(m==="2026-07") return;
    if(d.funnelMonth[m]){
      pts.push(d.meta[m].label.replace(" 2026",""));
      vals.push(d.funnelMonth[m].conversion_pct);
      const post = d.v2_date && m >= d.v2_date.slice(0,7);
      cols.push(mk===m ? C.teal : (post ? "#9dc4b6" : "#cfdbd6"));
    }
  });
  if(d.v2){
    const sv=d.v2.is_v2_split;
    pts.push(sv?"Juil. pré-V2":"Juil. "+d.v2.pre_label);
    vals.push(d.v2.pre_conversion_pct); cols.push(isJuly?"#b9beba":"#cfdbd6");
    pts.push(sv?"Juil. post-V2":"Juil. "+d.v2.post_label);
    vals.push(d.v2.post_conversion_pct); cols.push(isJuly?C.teal:"#cfdbd6");
  }
  kill("ft");
  charts.ft=new Chart(document.getElementById("funnelTrendChart"),{type:"bar",
    data:{labels:pts,datasets:[{label:"Taux de complétion",data:vals,backgroundColor:cols,borderRadius:6,maxBarThickness:52}]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false},tooltip:{...tip(),callbacks:{label:c=>pct(c.parsed.y)}}},
      scales:{x:{grid:{display:false},border:{display:false},ticks:tk()},
        y:{beginAtZero:true,grid:{color:"#eef0ee"},border:{display:false},ticks:{...tk(),callback:v=>v+" %"}}}}});

  const wn=document.getElementById("funnelV2Notice"); if(wn) wn.hidden=true;
  if(isTotal(mk)){ funnelTotal(d); return; }
  if(isJuly){ funnelJuly(d); return; }
  if(!FM){
    document.getElementById("funnelHero").innerHTML="";
    document.getElementById("funnelKpis").innerHTML='<div class="kpi"><p class="label">Information</p><p class="sub">Pas de funnel disponible pour ce mois.</p></div>';
    document.getElementById("funnelViz").innerHTML="";
    document.getElementById("funnelVizLegend").innerHTML="";
    document.querySelector("#channelTable thead").innerHTML="";
    document.querySelector("#channelTable tbody").innerHTML="";
    return;
  }

  const pm=prevMonth(mk), prev=pm&&d.funnelMonth[pm]?d.funnelMonth[pm].conversion_pct:null;
  const st=FM.steps, first=st[0].users, last=st[st.length-1].users;

  document.getElementById("funnelHero").innerHTML=
    '<div class="hero-card"><div class="hero-icon">'+icon("zap","#fff")+'</div><div class="hero-body">'+
    '<p class="hero-label">Taux de complétion du funnel — utilisateurs actifs</p>'+
    '<p class="hero-value">'+pct(FM.conversion_pct)+'<span class="hero-sub">'+d.meta[mk].label+'</span>'+
    (prev!=null?'<span class="hero-badge">'+(FM.conversion_pct-prev>=0?"↑":"↓")+" "+fmt(Math.abs(FM.conversion_pct-prev))+' pts vs '+d.meta[pm].label.replace(" 2026","")+'</span>':'')+
    '</p><p class="hero-note">'+fmt(last)+' estimations terminées sur '+fmt(first)+' entrées de funnel · '+fmt(FM.users_per_day)+' entrées / jour</p></div></div>';

  document.getElementById("funnelKpis").innerHTML=
    kpi("Entrées de funnel", fmt(first), fmt(FM.users_per_day)+" / jour") +
    kpi("Estimations terminées", fmt(last), null) +
    kpi("Taux de complétion", pct(FM.conversion_pct), null, prev!=null?badge(FM.conversion_pct-prev,"pts"):null) +
    kpi("Perte étape 1 → 2", pct(first?(first-st[1].users)/first*100:0), "abandon le plus fort");

  document.getElementById("funnelVizSub").textContent="Utilisateurs actifs · "+d.meta[mk].label;
  document.getElementById("funnelVizLegend").innerHTML="";
  let h='<div class="fn-head fn-head-1"><span>Étape</span><span>Utilisateurs actifs</span></div>';
  st.forEach((s,i)=>{
    const ret=s.users/first*100, w=Math.max(ret,9);
    h+='<div class="fn-row fn-row-1"><div class="fn-step-label"><span class="fn-step-num">'+(i+1)+'</span>'+
       '<span class="fn-step-name">'+esc(s.step.replace(/^\d+\.\s*/,""))+'</span></div>'+
       '<div class="fn-cell"><div class="fn-bar post" style="width:'+w.toFixed(1)+'%">'+fmt(s.users)+'</div>'+
       '<div class="fn-meta">'+fmt(ret)+' % de l\'étape 1</div></div></div>';
    if(i<st.length-1){
      const dr=s.users?(st[i+1].users-s.users)/s.users*100:0;
      h+='<div class="fn-drop fn-drop-1"><span></span><span class="fn-drop-cell'+(dr>=0?" neutral":"")+'">↓ '+fmt(dr)+' %</span></div>';
    }
  });
  document.getElementById("funnelViz").innerHTML=h;

  document.getElementById("channelSub").textContent="Utilisateurs actifs à l'étape 1 · "+d.meta[mk].label;
  const ch=(FM.channels||[]).slice().sort((a,b)=>b.u-a.u);
  const tot=ch.reduce((s,x)=>s+x.u,0)||1;
  document.querySelector("#channelTable thead").innerHTML='<tr><th>Canal</th><th class="num">Utilisateurs</th><th class="num">Part</th></tr>';
  document.querySelector("#channelTable tbody").innerHTML=ch.map(x=>
    '<tr><td>'+esc(x.c)+'</td><td class="num">'+fmt(x.u)+'</td><td class="num">'+fmt(x.u/tot*100)+' %</td></tr>').join("");
}

function funnelTotal(d){
  const v2=d.v2, dd=v2DateFR(d);
  const warn=document.getElementById("funnelV2Notice");
  warn.hidden=false;
  warn.querySelector("p").innerHTML =
    "Le funnel <strong>ne peut pas être cumulé</strong> : GA4 dédoublonne les utilisateurs actifs, "+
    "additionner les mois compterait plusieurs fois une même personne. Voici donc le détail période par période, "+
    "avec le lancement V2 du <strong>"+dd+"</strong> comme repère.";

  document.getElementById("funnelHero").innerHTML="";

  const rows=[];
  d.months.forEach(m=>{
    const F=d.funnelMonth[m]; if(!F) return;
    const st=F.steps;
    rows.push({ nom:d.meta[m].label.replace(" 2026",""), post:(d.v2_date && m>=d.v2_date.slice(0,7)),
                e1:st[0].users, fin:st[st.length-1].users, conv:F.conversion_pct, jour:F.users_per_day });
  });
  if(v2){
    const sv=v2.is_v2_split;
    rows.push({ nom:"Juil. "+(sv?"pré-V2":v2.pre_label), post:!sv,
      e1:v2.pre_step1_total, fin:v2.pre_final_users, conv:v2.pre_conversion_pct, jour:v2.pre_users_per_day });
    rows.push({ nom:"Juil. "+(sv?"post-V2":v2.post_label), post:true,
      e1:v2.post_step1_total, fin:v2.post_final_users, conv:v2.post_conversion_pct, jour:v2.post_users_per_day });
  }

  const best=rows.reduce((a,b)=>b.conv>a.conv?b:a,rows[0]);
  const pre=rows.filter(r=>!r.post), post=rows.filter(r=>r.post);
  const moy=a=>a.length? a.reduce((s,r)=>s+r.conv,0)/a.length : null;
  const mPre=moy(pre), mPost=moy(post);

  document.getElementById("funnelKpis").innerHTML=
    kpi("Complétion moyenne avant V2", mPre!=null?pct(mPre):"—", pre.length+" période"+(pre.length>1?"s":"")) +
    kpi("Complétion moyenne après V2", mPost!=null?pct(mPost):"—", post.length+" période"+(post.length>1?"s":""),
        (mPre!=null&&mPost!=null)?badge(mPost-mPre,"pts"):null) +
    kpi("Meilleure période", pct(best.conv), best.nom) +
    kpi("Lancement V2", dd, "bascule de référence");

  document.getElementById("funnelVizSub").textContent="Détail par période · un funnel ne s’additionne pas";
  document.getElementById("funnelVizLegend").innerHTML=
    '<div class="legend-item"><span class="swatch" style="background:#c7cbc8"></span><span class="lname">Avant V2</span></div>'+
    '<div class="legend-item"><span class="swatch" style="background:'+C.teal+'"></span><span class="lname">Après V2</span></div>';

  const max=Math.max.apply(null,rows.map(r=>r.conv))||1;
  document.getElementById("funnelViz").innerHTML=
    '<div class="rank-head" style="padding:0 0 9px"><span>Période</span><span class="rh-share">Complétion</span><span class="rh-value">Estimations</span></div>'+
    rows.map(r=>{
      const col=r.post?C.teal:"#c7cbc8";
      return '<div class="rank-row" style="padding-left:0;padding-right:0">'+
        '<div class="rank-name"><span class="rank-badge" style="background:'+col+'"></span>'+
          '<span class="rank-label">'+esc(r.nom)+'</span>'+
          '<span class="rank-pct" style="width:auto;color:var(--text-muted)">'+fmt(r.jour)+' entrées / j</span></div>'+
        '<div class="rank-share"><span class="rank-track"><span class="rank-fill" style="width:'+(r.conv/max*100).toFixed(1)+'%;background:'+col+'"></span></span>'+
          '<span class="rank-pct">'+pct(r.conv)+'</span></div>'+
        '<div class="rank-value">'+fmt(r.fin)+' / '+fmt(r.e1)+'</div></div>';
    }).join("");

  document.getElementById("channelSub").textContent="Entrées de funnel par canal · juin 2026 (dernier mois complet)";
  const FM=d.funnelMonth["2026-06"];
  const ch=FM?(FM.channels||[]).slice().sort((a,b)=>b.u-a.u):[];
  const tot=ch.reduce((s,x)=>s+x.u,0)||1;
  document.querySelector("#channelTable thead").innerHTML='<tr><th>Canal</th><th class="num">Utilisateurs</th><th class="num">Part</th></tr>';
  document.querySelector("#channelTable tbody").innerHTML=ch.map(x=>
    '<tr><td>'+esc(x.c)+'</td><td class="num">'+fmt(x.u)+'</td><td class="num">'+fmt(x.u/tot*100)+' %</td></tr>').join("");
}

function funnelJuly(d){
  const v2=d.v2, steps=d.v2steps, sv=v2.is_v2_split, dd=v2DateFR(d);
  const A = sv ? "Pré-V2" : v2.pre_label, B = sv ? "Post-V2" : v2.post_label;
  const warn = document.getElementById("funnelV2Notice");
  if(sv){ warn.hidden = true; }
  else {
    warn.hidden = false;
    warn.querySelector("p").innerHTML =
      "La V2 de ce site a été lancée le <strong>"+dd+"</strong>. Les deux périodes de juillet ci-dessous ("+
      "<strong>"+v2.pre_label+"</strong> et <strong>"+v2.post_label+"</strong>) sont donc <strong>toutes deux "+
      "postérieures</strong> au lancement : ce n'est pas une comparaison avant/après. Pour mesurer l'effet de la V2, "+
      "comparer avril–mai à juin–juillet sur le graphe de tendance ci-dessus.";
  }
  document.getElementById("funnelHero").innerHTML=
    '<div class="hero-card"><div class="hero-icon">'+icon("zap","#fff")+'</div><div class="hero-body">'+
    '<p class="hero-label">Taux de complétion du funnel — utilisateurs actifs</p>'+
    '<p class="hero-value">'+pct(v2.post_conversion_pct)+'<span class="hero-sub">'+(sv ? "post-V2, depuis le "+dd : "période "+v2.post_label)+'</span>'+
    '<span class="hero-badge">'+(v2.delta_conversion_pts>=0?"↑":"↓")+" "+fmt(Math.abs(v2.delta_conversion_pts))+' pts vs '+A+'</span></p>'+
    '<p class="hero-note">'+A+' : '+pct(v2.pre_conversion_pct)+' ('+fmt(v2.pre_final_users)+' / '+fmt(v2.pre_step1_total)+') · '+
    B+' : '+pct(v2.post_conversion_pct)+' ('+fmt(v2.post_final_users)+' / '+fmt(v2.post_step1_total)+')</p></div></div>';

  document.getElementById("funnelKpis").innerHTML=
    kpi("Complétion "+A, pct(v2.pre_conversion_pct), v2.pre_days+" jours") +
    kpi("Complétion "+B, pct(v2.post_conversion_pct), v2.post_days+" jours", badge(v2.delta_conversion_pts,"pts")) +
    kpi("Entrées / jour "+A, fmt(v2.pre_users_per_day), null) +
    kpi("Entrées / jour "+B, fmt(v2.post_users_per_day), null, badge(v2.delta_users_per_day_pct,"%"));

  document.getElementById("funnelVizSub").textContent="Utilisateurs actifs · "+A+" vs "+B+" · largeur = rétention depuis l'étape 1";
  document.getElementById("funnelVizLegend").innerHTML=
    '<div class="legend-item"><span class="swatch" style="background:#b9beba"></span><span class="lname">'+A+'</span></div>'+
    '<div class="legend-item"><span class="swatch" style="background:'+C.teal+'"></span><span class="lname">'+B+'</span></div>';
  const pT=steps[0].a||1, qT=steps[0].b||1;
  let h='<div class="fn-head"><span>Étape</span><span>'+A+'</span><span>'+B+'</span></div>';
  steps.forEach((s,i)=>{
    const pr=s.a/pT*100, po=s.b/qT*100;
    h+='<div class="fn-row"><div class="fn-step-label"><span class="fn-step-num">'+(i+1)+'</span>'+
       '<span class="fn-step-name">'+esc(s.step.replace(/^\d+\.\s*/,""))+'</span></div>'+
       '<div class="fn-cell"><div class="fn-bar pre" style="width:'+Math.max(pr,9).toFixed(1)+'%">'+fmt(s.a)+'</div><div class="fn-meta">'+fmt(pr)+' %</div></div>'+
       '<div class="fn-cell"><div class="fn-bar post" style="width:'+Math.max(po,9).toFixed(1)+'%">'+fmt(s.b)+'</div><div class="fn-meta">'+fmt(po)+' %</div></div></div>';
    if(i<steps.length-1){
      const a=s.a?(steps[i+1].a-s.a)/s.a*100:0;
      const b=s.b?(steps[i+1].b-s.b)/s.b*100:0;
      h+='<div class="fn-drop"><span></span><span class="fn-drop-cell'+(a>=0?" neutral":"")+'">↓ '+fmt(a)+' %</span>'+
         '<span class="fn-drop-cell'+(b>=0?" neutral":"")+'">↓ '+fmt(b)+' %</span></div>';
    }
  });
  document.getElementById("funnelViz").innerHTML=h;

  const rows=(d.v2channels||[]).filter(r=>r.c!=="Total");
  const first=rows.map(r=>r.st).sort()[0];
  const chans=[]; rows.forEach(r=>{ if(r.st===first&&!chans.includes(r.c)) chans.push(r.c); });
  document.getElementById("channelSub").textContent="Utilisateurs actifs à l'étape 1 · "+A+" vs "+B;
  document.querySelector("#channelTable thead").innerHTML='<tr><th>Canal</th><th class="num">'+A+'</th><th class="num">'+B+'</th><th class="num">Évolution</th></tr>';
  document.querySelector("#channelTable tbody").innerHTML=chans.map(c=>{
    const p=rows.find(r=>r.p==="pre_v2"&&r.st===first&&r.c===c), q=rows.find(r=>r.p==="post_v2"&&r.st===first&&r.c===c);
    const pu=p?p.u:0, qu=q?q.u:0, dl=pu?(qu-pu)/pu*100:0;
    return '<tr><td>'+esc(c)+'</td><td class="num">'+fmt(pu)+'</td><td class="num">'+fmt(qu)+
      '</td><td class="num" style="color:'+(dl>=0?C.teal:C.red)+'">'+(dl>=0?"+":"")+fmt(dl)+' %</td></tr>';
  }).join("");
}

/* ==================== CHART HELPERS ==================== */
function grad(c){ return ctx=>{ const a=ctx.chart.chartArea; if(!a) return c+"22";
  const g=ctx.chart.ctx.createLinearGradient(0,a.top,0,a.bottom); g.addColorStop(0,c+"2e"); g.addColorStop(1,c+"02"); return g; }; }
function tip(){ return {backgroundColor:"#141a17",padding:11,cornerRadius:9,titleFont:{weight:"700",size:12.5},bodyFont:{size:12.5},boxPadding:4,usePointStyle:true}; }
function tk(max){ return {color:"#949a94",font:{size:10.5},maxRotation:0,autoSkip:true,maxTicksLimit:max||14,padding:6}; }
function leg(){ return {boxWidth:8,usePointStyle:true,pointStyle:"circle",font:{size:11.5,weight:"600"},color:"#61675f"}; }
function lineOpt(max){ return {responsive:true,maintainAspectRatio:false,
  interaction:{mode:"index",intersect:false},
  plugins:{legend:{display:false},tooltip:tip()},
  scales:{x:{grid:{display:false},border:{display:false},ticks:tk(max)},
    y:{beginAtZero:true,grid:{color:"#eef0ee"},border:{display:false},ticks:tk()}}}; }

init();
