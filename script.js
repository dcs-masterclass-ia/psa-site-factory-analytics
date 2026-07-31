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
    const soft = !!o.soft;
    const col = soft ? "#e8892e" : "#0e6f56";
    const px = (o.index != null && xs) ? xs.getPixelForValue(o.index) : a.left;
    ctx.fillStyle = soft ? "rgba(232,137,46,.06)" : "rgba(14,111,86,.07)";
    ctx.fillRect(px, a.top, a.right - px, a.bottom - a.top);
    if(o.index != null){
      ctx.setLineDash([5,4]); ctx.lineWidth = 1.6; ctx.strokeStyle = col;
      ctx.beginPath(); ctx.moveTo(px, a.top); ctx.lineTo(px, a.bottom); ctx.stroke();
      ctx.setLineDash([]);
    }
    if(o.label){
      ctx.font = '700 10.8px -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif';
      if(soft){
        // libelle discret, pose au-dessus de la zone de traçage
        ctx.fillStyle = col; ctx.textBaseline = "bottom"; ctx.textAlign = "left";
        const w = ctx.measureText(o.label).width;
        let lx = px + 6; if(lx + w > a.right) lx = Math.max(a.left, a.right - w);
        ctx.fillText(o.label, lx, a.top - 8);
      } else {
        const w = ctx.measureText(o.label).width + 14;
        let lx = (o.index != null) ? px + 6 : a.right - w - 2;
        if(lx + w > a.right - 2) lx = a.right - w - 2;
        if(lx < a.left) lx = a.left;
        ctx.fillStyle = col;
        ctx.fillRect(lx, a.top + 4, w, 18);
        ctx.fillStyle = "#fff"; ctx.textBaseline = "middle"; ctx.textAlign = "left";
        ctx.fillText(o.label, lx + 7, a.top + 13);
      }
    }
    ctx.restore();
  }
};
Chart.register(V2_MARK);

/* ---- valeurs affichees directement sur les points ---- */
const V_LABEL = {
  id: "vlabel",
  afterDatasetsDraw(chart){
    const o = chart.options.plugins && chart.options.plugins.vlabel;
    if(!o || !o.on) return;
    const ctx = chart.ctx, a = chart.chartArea;
    ctx.save();
    ctx.font = '700 11.5px -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif';
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.lineJoin = "round";

    const GAP = 15, OFF = 15;
    const n = chart.data.labels.length;
    const items = [];

    for(let i=0;i<n;i++){
      // les points de l'index i, du plus haut au plus bas a l'ecran
      const col = [];
      chart.data.datasets.forEach((ds,di)=>{
        const meta = chart.getDatasetMeta(di);
        if(meta.hidden) return;
        const v = ds.data[i], pt = meta.data[i];
        if(v==null || !pt) return;
        col.push({ x:pt.x, py:pt.y, text:fmt(v), color:ds.borderColor });
      });
      if(!col.length) continue;
      col.sort((p,q)=>p.py-q.py);
      // le plus haut prend l'espace au-dessus, les autres en dessous
      col.forEach((p,k)=>{ p.y = (k===0 ? p.py - OFF : p.py + OFF); });
      // on ecarte ce qui se chevauche encore, puis on recadre
      col.sort((p,q)=>p.y-q.y);
      for(let k=1;k<col.length;k++){
        if(col[k].y - col[k-1].y < GAP) col[k].y = col[k-1].y + GAP;
      }
      const over = col[col.length-1].y - (a.bottom - 4);
      if(over > 0) col.forEach(p=>{ p.y -= over; });
      const under = (a.top + 4) - col[0].y;
      if(under > 0) col.forEach(p=>{ p.y += under; });
      col.forEach(p=>{
        const w = ctx.measureText(p.text).width/2 + 2;
        p.x = Math.min(Math.max(p.x, a.left + w), a.right - w);
        items.push(p);
      });
    }

    // halo blanc pour rester lisible par-dessus les courbes
    items.forEach(p=>{
      ctx.strokeStyle = "#fff"; ctx.lineWidth = 3.5;
      ctx.strokeText(p.text, p.x, p.y);
      ctx.fillStyle = p.color;
      ctx.fillText(p.text, p.x, p.y);
    });
    ctx.restore();
  }
};
Chart.register(V_LABEL);

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
  document.getElementById("siteTabs").innerHTML = SITES.map(s=>
    '<button class="site-tab" data-site="'+esc(s)+'"><span class="dot"></span>'+esc(s)+'</button>').join("");
  document.getElementById("btnOverview").addEventListener("click", showOverview);
  document.querySelectorAll("#siteTabs .site-tab").forEach(b=>b.addEventListener("click",async()=>{
    document.querySelectorAll(".site-tab").forEach(x=>x.classList.remove("active"));
    b.classList.add("active"); await load(b.dataset.site);
  }));
  document.querySelectorAll(".section-tab").forEach(b=>b.addEventListener("click",()=>{
    document.querySelectorAll(".section-tab").forEach(x=>x.classList.remove("active"));
    b.classList.add("active");
    document.querySelectorAll(".panel").forEach(p=>p.classList.remove("active"));
    document.getElementById("panel-"+b.dataset.section).classList.add("active");
  }));
  await showOverview();
}

/* ==================== VUE D'ENSEMBLE ==================== */
let ovScope = "month";

async function loadAll(){
  await Promise.all(SITES.map(async s=>{
    if(!cache[s]) cache[s] = await (await fetch("data/"+slug(s)+".json")).json();
  }));
}

async function showOverview(){
  await loadAll();
  document.querySelectorAll(".site-tab").forEach(x=>x.classList.remove("active"));
  document.getElementById("btnOverview").classList.add("active");
  document.querySelectorAll(".panel").forEach(p=>p.classList.remove("active"));
  document.getElementById("panel-overview").classList.add("active");
  document.getElementById("pageTitle").textContent = "Vue d'ensemble";
  document.getElementById("pageSub").textContent = "Les cinq sites, du trafic au lead";
  document.getElementById("crumbSite").textContent = "Vue d'ensemble";
  document.getElementById("sectionTabs").hidden = true;
  document.getElementById("monthTabs").hidden = true;
  document.getElementById("partialNotice").hidden = true;
  renderOverview();
}

/* Agrégats d'un site sur une période : m = clé de mois, ou "day" pour le dernier jour connu */
function ovStats(d, mode){
  const ms = d.months, m = ms[ms.length-1], pm = ms[ms.length-2];
  if(mode === "day"){
    const n = d.daily.d.length - 1;
    const L = d.leads[m];
    const li = L.daily.length - 1;
    const last7 = L.daily.slice(-8, -1);
    const moy7 = last7.length ? last7.reduce((a,b)=>a+b,0)/last7.length : null;
    return { label: d.daily.d[n], sess: d.daily.rep[n], leads: L.daily[li],
             conv: d.daily.rep[n] ? L.daily[li]/d.daily.rep[n]*100 : null,
             ref: moy7, refLabel: "moyenne 7 jours", spark: L.daily.slice(-14) };
  }
  const T = d.trafficMonth[m], R = d.repriseMonth[m], L = d.leads[m], days = d.meta[m].days;
  const Rp = d.repriseMonth[pm], Lp = d.leads[pm], daysP = d.meta[pm].days;
  return { label: d.meta[m].label, sess: R.sessions, leads: L.total, parent: T.sessions,
           part: T.sessions ? R.sessions/T.sessions*100 : null,
           conv: R.sessions ? L.total/R.sessions*100 : null,
           convPrev: Rp.sessions ? Lp.total/Rp.sessions*100 : null,
           perDay: L.total/days, perDayPrev: Lp.total/daysP,
           spark: L.daily.slice(-14) };
}

function sparkline(vals, color){
  if(!vals || vals.length < 2) return "";
  const w = 84, h = 22, mx = Math.max(...vals), mn = Math.min(...vals), sp = (mx-mn)||1;
  const pts = vals.map((v,i)=>[i/(vals.length-1)*w, h - (v-mn)/sp*(h-4) - 2]);
  const dd = pts.map((p,i)=>(i?"L":"M")+p[0].toFixed(1)+" "+p[1].toFixed(1)).join(" ");
  return '<svg class="spark-svg" viewBox="0 0 '+w+' '+h+'" preserveAspectRatio="none">'+
         '<path d="'+dd+'" fill="none" stroke="'+color+'" stroke-width="1.6" stroke-linejoin="round"/>'+
         '<circle cx="'+pts[pts.length-1][0].toFixed(1)+'" cy="'+pts[pts.length-1][1].toFixed(1)+'" r="2.2" fill="'+color+'"/></svg>';
}

function renderOverview(){
  const seg = document.getElementById("ovScope");
  seg.querySelectorAll(".seg-btn").forEach(b=>{
    b.classList.toggle("active", b.dataset.scope === ovScope);
    b.onclick = ()=>{ ovScope = b.dataset.scope; renderOverview(); };
  });

  const rows = SITES.map(s=>({ site:s, d:cache[s], st:ovStats(cache[s], ovScope) }))
                    .sort((a,b)=> b.st.leads - a.st.leads);
  const day = ovScope === "day";
  const totLeads = rows.reduce((a,r)=>a+r.st.leads,0);
  const totSess  = rows.reduce((a,r)=>a+r.st.sess,0);
  const ref      = rows.reduce((a,r)=>a+(day ? (r.st.ref||0) : (r.st.perDayPrev||0)),0);
  const conv     = totSess ? totLeads/totSess*100 : 0;

  const d0 = rows[0].d, lastM = d0.months[d0.months.length-1];
  const periodLabel = day
    ? "Journée du " + rows[0].st.label.slice(3) + "/" + rows[0].st.label.slice(0,2)
    : d0.meta[lastM].label + " · " + d0.meta[lastM].days + " jours";

  document.getElementById("ovSub").textContent = periodLabel + " · classement par volume de leads";
  document.getElementById("ovKpis").innerHTML =
    kpi("Leads — " + (day ? "dernier jour" : "mois en cours"), fmt(totLeads),
        day ? "moyenne 7 j : " + fmt(ref) : "mois précédent : " + fmt(ref) + " / jour",
        ref ? badge(((day ? totLeads : totLeads/d0.meta[lastM].days) - ref)/ref*100, "%") : null) +
    kpi("Sessions outil de reprise", fmt(totSess), day ? "sur la journée" : "sur le mois") +
    kpi("Transformation moyenne", pct(conv), "sessions reprise → leads") +
    kpi("Sites suivis", String(rows.length), "lancements V2 échelonnés");

  const head = day
    ? '<tr><th class="mtx-lab">Site</th><th class="num">Leads</th><th class="num">Moy. 7 j</th><th class="num">Sessions reprise</th><th class="num">Transformation</th><th class="num mtx-end">14 derniers jours</th></tr>'
    : '<tr><th class="mtx-lab">Site</th><th class="num">Leads</th><th class="num">/ jour</th><th class="num">Sessions reprise</th><th class="num">Part du site</th><th class="num">Transformation</th><th class="num mtx-end">14 derniers jours</th></tr>';

  const body = rows.map(r=>{
    const st = r.st, v2 = r.d.v2_date ? r.d.v2_date.slice(8,10)+"/"+r.d.v2_date.slice(5,7) : "—";
    const cells = day
      ? '<td class="num"><span class="mtx-val">'+fmt(st.leads)+'</span></td>'+
        '<td class="num mtx-ref">'+fmt(st.ref)+'</td>'+
        '<td class="num">'+fmt(st.sess)+'</td>'+
        '<td class="num">'+(st.conv==null?"—":pct(st.conv))+'</td>'
      : '<td class="num"><span class="mtx-val">'+fmt(st.leads)+'</span>'+
          (st.perDayPrev ? '<span class="mtx-sub">'+badge((st.perDay-st.perDayPrev)/st.perDayPrev*100,"%")+'</span>' : '')+'</td>'+
        '<td class="num mtx-ref">'+fmt(st.perDay)+'</td>'+
        '<td class="num">'+fmt(st.sess)+'</td>'+
        '<td class="num">'+(st.part==null?"—":pct(st.part))+'</td>'+
        '<td class="num"><span class="mtx-val">'+pct(st.conv)+'</span>'+
          (st.convPrev!=null ? '<span class="mtx-sub">'+badge(st.conv-st.convPrev,"pts")+'</span>' : '')+'</td>';
    return '<tr class="ov-row" data-site="'+esc(r.site)+'">'+
      '<td class="mtx-lab"><span class="ov-name">'+esc(r.site)+'</span><span class="ov-v2">V2 le '+v2+'</span></td>'+
      cells+'<td class="num mtx-end">'+sparkline(st.spark, C.teal)+'</td></tr>';
  }).join("");

  document.querySelector("#ovTable thead").innerHTML = head;
  document.querySelector("#ovTable tbody").innerHTML = body;
  document.querySelectorAll(".ov-row").forEach(tr=>tr.addEventListener("click", async ()=>{
    document.querySelectorAll(".site-tab").forEach(x=>x.classList.remove("active"));
    document.querySelector('#siteTabs [data-site="'+tr.dataset.site+'"]').classList.add("active");
    await load(tr.dataset.site);
  }));

  // lecture automatique : meilleure et moins bonne transformation, plus forte variation
  const best = rows.reduce((a,b)=> b.st.conv>a.st.conv?b:a);
  const worst= rows.reduce((a,b)=> b.st.conv<a.st.conv?b:a);
  let note = "Transformation la plus forte : <strong>"+esc(best.site)+"</strong> ("+pct(best.st.conv)+
             "), la plus faible : <strong>"+esc(worst.site)+"</strong> ("+pct(worst.st.conv)+"). ";
  if(!day){
    const mv = rows.filter(r=>r.st.convPrev!=null)
                   .reduce((a,b)=> Math.abs(b.st.conv-b.st.convPrev)>Math.abs(a.st.conv-a.st.convPrev)?b:a);
    note += "Plus forte variation par rapport au mois précédent : <strong>"+esc(mv.site)+"</strong> ("+
            (mv.st.conv-mv.st.convPrev>=0?"+":"−")+fmt(Math.abs(mv.st.conv-mv.st.convPrev))+" pts). ";
  }
  note += "Cliquer une ligne ouvre le détail du site.";
  document.getElementById("ovNote").innerHTML = note;

  // courbe : leads quotidiens cumulés des 5 sites sur le mois en cours
  const n = Math.max(...rows.map(r=>r.d.leads[lastM].daily.length));
  const labels = Array.from({length:n},(_,i)=>String(i+1));
  const serie = labels.map((_,i)=> rows.reduce((a,r)=> a + (r.d.leads[lastM].daily[i]||0), 0));
  document.getElementById("ovChartSub").textContent = d0.meta[lastM].label + " · somme des cinq sites";
  kill("ov");
  charts.ov = new Chart(document.getElementById("ovChart"), {
    type:"line",
    data:{ labels, datasets:[{ label:"Leads", data:serie, borderColor:C.teal, backgroundColor:grad(C.teal),
            fill:true, tension:.3, pointRadius:0, pointHoverRadius:5, borderWidth:2.4 }] },
    options: lineOpt(16),
  });
}

async function load(site){
  curSite = site;
  document.getElementById("sectionTabs").hidden = false;
  document.getElementById("monthTabs").hidden = false;
  document.getElementById("panel-overview").classList.remove("active");
  if(!document.querySelector(".panel.active")) document.getElementById("panel-leads").classList.add("active");
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
      ? "La période cumule <strong>121 jours</strong> (01/04 → 30/07). Juillet n'en compte que 30 : ce mois pèse donc un peu moins que les autres dans les totaux."
      : "Juillet ne couvre que <strong>30 jours</strong> au lieu de 31. Les totaux mensuels ne sont donc pas comparables tels quels — les évolutions affichées sont calculées en <strong>moyenne par jour</strong>.";
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

  renderEvo(d);

  // graphe quotidien du mois
  document.getElementById("leadsDailySub").textContent = isTotal(mk) ? "01/04 → 30/07 · 121 jours" : meta.label;
  kill("ld");
  charts.ld=new Chart(document.getElementById("leadsDailyChart"),{type:"line",
    data:{labels:(isTotal(mk)? d.daily.d.map(x=>x.slice(3)+"/"+x.slice(0,2)) : L.daily.map((_,i)=>String(i+1))),
      datasets:[{label:"Leads",data:L.daily,
      borderColor:C.teal,backgroundColor:grad(C.teal),fill:true,tension:.35,pointRadius:0,pointHoverRadius:5,borderWidth:2.4}]},
    options:(()=>{ const o=lineOpt(isTotal(mk)?12:14);
      o.plugins.v2mark=v2Mark(d, isTotal(mk)? d.daily.d : monthAxis(mk, meta.days)); return o; })()});

  buildDims(d,L);
  donut("entryChart","dEntry","entryLegend","entryCenter",Object.entries(L.entry).sort((a,b)=>b[1]-a[1]));
  donut("projectChart","dProj","projectLegend","projectCenter",L.project);
}

/* ---- bloc principal : sessions reprise vs leads, mois par mois ---- */
let evoScale = "day";

function renderEvo(d){
  const ms = d.months, mk = curMonth;
  const ref = isTotal(mk) ? ms[ms.length-1] : mk;   // mois mis en avant dans les cartes
  const base = ms[0];
  const dv = evoScale === "day";
  const days = m => d.meta[m].days;
  const sess = m => d.repriseMonth[m].sessions / (dv ? days(m) : 1);
  const lead = m => d.leads[m].total / (dv ? days(m) : 1);
  const conv = m => d.repriseMonth[m].sessions ? d.leads[m].total / d.repriseMonth[m].sessions * 100 : null;

  // segmented control
  const seg = document.getElementById("evoScale");
  seg.querySelectorAll(".seg-btn").forEach(b=>{
    b.classList.toggle("active", b.dataset.scale === evoScale);
    b.onclick = () => { evoScale = b.dataset.scale; renderEvo(d); };
  });

  // marqueur V2 sur un axe mensuel
  const vm = (() => {
    if(!d.v2_date) return {on:false};
    const i = ms.indexOf(d.v2_date.slice(0,7));
    const lbl = "Nouvelle version · " + Number(d.v2_date.slice(8,10)) + " " +
      ["janvier","février","mars","avril","mai","juin","juillet","août","septembre","octobre","novembre","décembre"][Number(d.v2_date.slice(5,7))-1];
    return i>=0 ? {on:true, index:i, label:lbl, soft:true} : {on:false};
  })();

  const sc = dualScale(ms.map(sess), ms.map(lead));
  kill("evo");
  charts.evo = new Chart(document.getElementById("evoChart"), {
    type:"line",
    data:{ labels: ms.map(m=>d.meta[m].label.replace(" 2026","")),
      datasets:[
        {label:"Sessions outil de reprise", data: ms.map(sess), yAxisID:"y",
         borderColor:C.teal, backgroundColor:"transparent", borderWidth:2.6, tension:.25,
         pointRadius: ms.map(m=>m===ref?7:5.5), pointBackgroundColor:C.teal, pointBorderColor:"#fff", pointBorderWidth:2},
        {label:"Leads", data: ms.map(lead), yAxisID:"y1",
         borderColor:C.orange, backgroundColor:"transparent", borderWidth:2.6, tension:.25,
         pointRadius: ms.map(m=>m===ref?7:5.5), pointBackgroundColor:C.orange, pointBorderColor:"#fff", pointBorderWidth:2}
      ]},
    options:{ responsive:true, maintainAspectRatio:false,
      layout:{ padding:{ top:26, right:8, left:4 } },
      interaction:{ mode:"index", intersect:false },
      plugins:{ legend:{display:false},
        tooltip:{...tip(), callbacks:{ label:c=>c.dataset.label+" : "+fmt(c.parsed.y)+(dv?" / jour":"") }},
        v2mark: vm, vlabel:{ on:true } },
      scales:{
        x:{ grid:{display:false}, border:{display:false},
            ticks:{...tk(), font:{size:11.5}, color:"#61675f"} },
        y:{ beginAtZero:true, max:sc.left, grid:{color:"#eef0ee"}, border:{display:false},
            ticks:{...tk(), color:C.teal},
            title:{display:true, text: dv?"Sessions reprise / jour":"Sessions reprise", color:C.teal, font:{size:10.5, weight:"700"}} },
        y1:{ position:"right", beginAtZero:true, max:sc.right, grid:{display:false}, border:{display:false},
            ticks:{...tk(), color:C.orange},
            title:{display:true, text: dv?"Leads / jour":"Leads", color:C.orange, font:{size:10.5, weight:"700"}} }
      }}
  });

  const unit = dv ? " / jour" : "";
  const sB = sess(base), sR = sess(ref), lB = lead(base), lR = lead(ref);
  const cB = conv(base), cR = conv(ref);
  const nm = m => d.meta[m].label.replace(" 2026","").toLowerCase();
  document.getElementById("evoKpis").innerHTML =
    kpi("Sessions reprise — "+nm(ref), fmt(sR)+unit, nm(base)+" : "+fmt(sB)+unit,
        sB?badge((sR-sB)/sB*100,"%"):null) +
    kpi("Leads — "+nm(ref), fmt(lR)+unit, nm(base)+" : "+fmt(lB)+unit,
        lB?badge((lR-lB)/lB*100,"%"):null) +
    kpi("Transformation — "+nm(ref), pct(cR), nm(base)+" : "+pct(cB),
        (cB!=null&&cR!=null)?badge(cR-cB,"pts"):null) +
    kpi("Évolution "+nm(base)+" → "+nm(ref), (cB?"× "+fmt(cR/cB):"—"), "sur le taux de transformation");
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
  document.getElementById("trafficDailySub").textContent=(isTotal(mk)?"01/04 → 30/07":meta.label)+" · deux échelles";
  document.getElementById("trafficLegend").innerHTML=
    '<div class="legend-item"><span class="swatch" style="background:'+C.teal+'"></span><span class="lname">Site parent</span><span class="lvalue">'+fmt(T.sessions)+'</span></div>'+
    '<div class="legend-item"><span class="swatch" style="background:'+C.orange+'"></span><span class="lname">Outil de reprise</span><span class="lvalue">'+fmt(R.sessions)+'</span></div>';
  const sPar=idx.map(i=>d.daily.u[i]), sRep=idx.map(i=>d.daily.rep[i]);
  const sc=dualScale(sPar,sRep);
  kill("tr");
  charts.tr=new Chart(document.getElementById("trafficChart"),{type:"line",
    data:{labels:lab,datasets:[
      {label:"Site parent",data:sPar,yAxisID:"y",borderColor:C.teal,backgroundColor:grad(C.teal),fill:true,tension:.3,pointRadius:0,pointHoverRadius:5,borderWidth:2.4},
      {label:"Outil de reprise",data:sRep,yAxisID:"y1",borderColor:C.orange,backgroundColor:grad(C.orange),fill:true,tension:.3,pointRadius:0,pointHoverRadius:5,borderWidth:2.4}]},
    options:(()=>{ const o=lineOpt(isTotal(mk)?12:16);
      o.plugins.v2mark=v2Mark(d, idx.map(i=>d.daily.d[i]));
      o.scales.y={...o.scales.y, max:sc.left, ticks:{...tk(), color:C.teal},
        title:{display:true,text:"Sessions site parent",color:C.teal,font:{size:10.5,weight:"700"}}};
      o.scales.y1={position:"right",beginAtZero:true,max:sc.right,grid:{display:false},border:{display:false},
        ticks:{...tk(), color:C.orange},
        title:{display:true,text:"Sessions outil de reprise",color:C.orange,font:{size:10.5,weight:"700"}}};
      return o; })()});

  renderSynth(d);
}

/* ---- tableau de synthese mensuelle : trafic -> reprise -> leads ---- */
function renderSynth(d){
  const ms = d.months, mk = curMonth;
  const days = m => d.meta[m].days;
  const site = m => d.trafficMonth[m].sessions;
  const rep  = m => d.repriseMonth[m].sessions;
  const lead = m => d.leads[m] ? d.leads[m].total : null;

  const groups = [
    { title:"Trafic", rows:[
      { l:"Sessions site parent", v:site, perDay:true },
      { l:"Sessions outil de reprise", v:rep, perDay:true },
      { l:"Part du site allant vers la reprise", v:m=>site(m)?rep(m)/site(m)*100:null, kind:"pct", hi:true }
    ]},
    { title:"Leads", rows:[
      { l:"Leads (extraction back-office)", v:lead, perDay:true },
      { l:"Transformation reprise → leads", v:m=>rep(m)?lead(m)/rep(m)*100:null, kind:"pct", hi:true },
      { l:"Leads pour 1 000 sessions du site", v:m=>site(m)?lead(m)/site(m)*1000:null, kind:"dec" }
    ]}
  ];

  const head = '<tr><th class="mtx-lab">Indicateur</th>' +
    ms.map(m=>'<th class="num'+(m===mk?" mtx-cur":"")+'">'+esc(d.meta[m].label.replace(" 2026",""))+'</th>').join("") +
    '<th class="num mtx-end">Évolution avril → juillet</th></tr>';

  let body = "";
  groups.forEach(g=>{
    body += '<tr class="mtx-group"><td colspan="'+(ms.length+2)+'">'+g.title+'</td></tr>';
    g.rows.forEach(r=>{
      const vals = ms.map(r.v);
      const a = vals[0], z = vals[vals.length-1];
      let evo = "—";
      if(a!=null && z!=null){
        if(r.kind==="pct"){
          const pts = z-a;
          evo = '<span class="mtx-evo '+(pts>=0?"pos":"neg")+'">'+(pts>=0?"+ ":"− ")+fmt(Math.abs(pts))+' pts</span>'+
                (a?'<span class="mtx-evo-sub">× '+fmt(z/a)+'</span>':"");
        } else {
          // comparaison en moyenne / jour : juillet ne compte que 28 jours
          const pa = a/days(ms[0]), pz = z/days(ms[ms.length-1]);
          const dl = pa ? (pz-pa)/pa*100 : 0;
          evo = '<span class="mtx-evo '+(dl>=0?"pos":"neg")+'">'+(dl>=0?"+ ":"− ")+fmt(Math.abs(dl))+' %</span>'+
                '<span class="mtx-evo-sub">en moyenne / jour</span>';
        }
      }
      body += '<tr class="'+(r.hi?"mtx-hi":"")+'"><td class="mtx-lab">'+r.l+'</td>' +
        vals.map((v,i)=>{
          const m = ms[i];
          const main = v==null ? "—" : (r.kind==="pct" ? pct(v) : fmt(r.kind==="dec"? v : Math.round(v)));
          const sub  = (v!=null && r.perDay) ? '<span class="mtx-sub">'+fmt(v/days(m))+' / j</span>' : "";
          return '<td class="num'+(m===mk?" mtx-cur":"")+'"><span class="mtx-val">'+main+'</span>'+sub+'</td>';
        }).join("") +
        '<td class="num mtx-end">'+evo+'</td></tr>';
    });
  });

  document.querySelector("#synthTable thead").innerHTML = head;
  document.querySelector("#synthTable tbody").innerHTML = body;

  const lastM = ms[ms.length-1];
  const partA = site(ms[0])?rep(ms[0])/site(ms[0])*100:0, partZ = site(lastM)?rep(lastM)/site(lastM)*100:0;
  const convA = rep(ms[0])?lead(ms[0])/rep(ms[0])*100:0, convZ = rep(lastM)?lead(lastM)/rep(lastM)*100:0;
  document.getElementById("synthNote").innerHTML =
    "Lecture : sur 1 000 sessions du site parent, <strong>"+fmt(partZ*10)+"</strong> arrivent sur l'outil de reprise en juillet (contre "+
    fmt(partA*10)+" en avril), et <strong>"+fmt(convZ)+" %</strong> d'entre elles déposent un lead (contre "+fmt(convA)+" % en avril). " +
    "Juillet ne couvre que 28 jours : les évolutions de volume sont donc calculées en moyenne par jour, les taux le sont sur la période complète.";
}

/* ==================== FUNNEL ==================== */
function renderFunnel(d){
  const mk=curMonth, isJuly=(mk==="2026-07"&&d.v2), FM=d.funnelMonth[mk];

  renderSteps(d);

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

/* ---- tableau du parcours etape par etape, avril -> juillet ---- */
const STEP_FR = ["Page d'accueil","Sélection de version","Kilométrage","Coordonnées","Choix du concessionnaire","Estimation de prix"];

function stepUsers(d,m){
  if(d.funnelMonth[m]) return d.funnelMonth[m].steps.map(s=>s.users);
  if(m==="2026-07" && d.v2steps) return d.v2steps.map(s=>s.a+s.b);   // juillet = somme des deux exports
  return null;
}

function renderSteps(d){
  const ms = d.months, mk = curMonth;
  const cols = ms.map(m=>({ m:m, label:d.meta[m].label.replace(" 2026",""), u:stepUsers(d,m) })).filter(c=>c.u);
  const ref = cols.filter(c=>c.m!=="2026-07");     // avril -> juin, base de comparaison
  const last = cols[cols.length-1];
  if(!last){ document.querySelector("#stepTable thead").innerHTML=""; document.querySelector("#stepTable tbody").innerHTML=""; return; }
  const n = last.u.length;

  const rows = [];
  for(let i=0;i<n-1;i++){
    const vals = cols.map(c=> c.u[i] ? c.u[i+1]/c.u[i]*100 : null);
    const sA = ref.reduce((s,c)=>s+c.u[i],0), sB = ref.reduce((s,c)=>s+c.u[i+1],0);
    const moy = sA ? sB/sA*100 : null;
    rows.push({ l:(STEP_FR[i]||("Étape "+(i+1)))+" → "+(STEP_FR[i+1]||("Étape "+(i+2))), vals:vals, moy:moy });
  }
  const conv = cols.map(c=> c.u[0] ? c.u[n-1]/c.u[0]*100 : null);
  const cA = ref.reduce((s,c)=>s+c.u[0],0), cZ = ref.reduce((s,c)=>s+c.u[n-1],0);
  const convMoy = cA ? cZ/cA*100 : null;

  // etape la plus determinante : le plus gros ecart entre juillet et la moyenne avril-juin
  let hi = -1, best = 0;
  rows.forEach((r,i)=>{ const e = (r.moy!=null && r.vals[r.vals.length-1]!=null) ? Math.abs(r.vals[r.vals.length-1]-r.moy) : 0;
    if(e>best){ best=e; hi=i; } });

  const gap = (v,m) => {
    if(v==null||m==null) return "—";
    const e = v-m;
    return '<span class="mtx-evo '+(e>=0?"pos":"neg")+'">'+(e>=0?"+":"−")+fmt(Math.abs(e))+' pts</span>';
  };

  document.querySelector("#stepTable thead").innerHTML =
    '<tr><th class="mtx-lab">Étape du parcours</th>' +
    cols.map(c=>'<th class="num'+(c.m===mk?" mtx-cur":"")+'">'+esc(c.label)+'</th>').join("") +
    '<th class="num mtx-ref">Moyenne avril–juin</th><th class="num mtx-end">Écart</th></tr>';

  let body = rows.map((r,i)=>
    '<tr class="'+(i===hi?"mtx-hi":"")+'"><td class="mtx-lab">'+esc(r.l)+'</td>' +
    r.vals.map((v,j)=>'<td class="num'+(cols[j].m===mk?" mtx-cur":"")+'">'+(v==null?"—":pct(v))+'</td>').join("") +
    '<td class="num mtx-ref">'+(r.moy==null?"—":pct(r.moy))+'</td>' +
    '<td class="num mtx-end">'+gap(r.vals[r.vals.length-1], r.moy)+'</td></tr>').join("");

  const cz = conv[conv.length-1];
  body += '<tr class="mtx-total"><td class="mtx-lab">Taux de complétion du parcours</td>' +
    conv.map((v,j)=>'<td class="num'+(cols[j].m===mk?" mtx-cur":"")+'">'+(v==null?"—":pct(v))+'</td>').join("") +
    '<td class="num mtx-ref">'+(convMoy==null?"—":pct(convMoy))+'</td>' +
    '<td class="num mtx-end">'+gap(cz,convMoy)+
      ((convMoy&&cz)?'<span class="mtx-evo-sub">× '+fmt(cz/convMoy)+'</span>':"")+'</td></tr>';

  document.querySelector("#stepTable tbody").innerHTML = body;

  document.getElementById("stepSub").textContent =
    "Part des utilisateurs actifs franchissant chaque étape · avril → juillet 2026";
  const dd = v2DateFR(d);
  document.getElementById("stepNote").innerHTML =
    (hi>=0 ? "L'étape qui bouge le plus est <strong>"+esc(rows[hi].l)+"</strong> ("+
      fmt(Math.abs(rows[hi].vals[rows[hi].vals.length-1]-rows[hi].moy))+" pts d'écart avec la moyenne avril–juin). " : "") +
    "La moyenne avril–juin est pondérée par les volumes de chaque mois. Lancement V2 le <strong>"+dd+"</strong>. " +
    "Juillet est reconstitué en additionnant les deux exports de la période : GA4 dédoublonnant les utilisateurs actifs, " +
    "les volumes de juillet peuvent être très légèrement surestimés, mais pas les taux.";
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
/* arrondi "propre" superieur : 4 830 -> 5 000 */
function niceMax(v){
  if(!(v>0)) return 1;
  const e = Math.pow(10, Math.floor(Math.log10(v))), r = v/e;
  const s = [1,1.2,1.5,2,2.5,3,4,5,6,8,10].find(x=>x>=r) || 10;
  return s*e;
}
/* deux echelles calibrees pour que la serie secondaire reste sous la principale */
function dualScale(main, sec){
  const A = main.filter(x=>x!=null&&!isNaN(x)), B = sec.filter(x=>x!=null&&!isNaN(x));
  if(!A.length||!B.length) return { left:undefined, right:undefined };
  const maxA = Math.max.apply(null,A), minA = Math.min.apply(null,A), maxB = Math.max.apply(null,B);
  const left = niceMax(maxA*1.02);
  // hauteur relative du creux de la courbe principale : la secondaire doit rester dessous
  let frac = (minA/left)*0.9;
  frac = Math.min(Math.max(frac, 0.30), 0.85);
  return { left:left, right:niceMax(maxB/frac) };
}

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
