/* =========================================================================
   PSA Site Factory — Analytics
   Un rapport = une page. Un seul controle de periode, en topbar.
   Les ecarts sont toujours calcules sur des moyennes par jour.
   ========================================================================= */

const CSS = getComputedStyle(document.documentElement);
const C = {
  ink:   CSS.getPropertyValue("--ink").trim()   || "#0E1116",
  ink3:  CSS.getPropertyValue("--ink-3").trim() || "#8B94A1",
  ink4:  CSS.getPropertyValue("--ink-4").trim() || "#B9C0C9",
  eu:    CSS.getPropertyValue("--eu").trim()    || "#1B3FB8",
  jade:  CSS.getPropertyValue("--jade").trim()  || "#0B7B6B",
  tag:   CSS.getPropertyValue("--tag").trim()   || "#F5C518",
  rust:  CSS.getPropertyValue("--rust").trim()  || "#C4462F",
  line:  CSS.getPropertyValue("--line").trim()  || "#DCE1E7",
  line2: CSS.getPropertyValue("--line-2").trim()|| "#EDF0F3",
};

/* hotes de reference, repris du perimetre du projet */
const HOSTS = {
  "OPEL FR":       { pays:"F", host:"reprise.opel.fr" },
  "OPEL PT":       { pays:"P", host:"retoma.opel.pt" },
  "CITROEN PT":    { pays:"P", host:"retoma-citroen.pt" },
  "PEUGEOT PT":    { pays:"P", host:"retoma.peugeot.pt" },
  "DS PT":         { pays:"P", host:"retoma.dsautomobiles.pt" },
  "FIAT PT":       { pays:"P", host:"retoma.fiat.pt" },
  "JEEP PT":       { pays:"P", host:"retoma.jeep.pt" },
  "ALFA ROMEO PT": { pays:"P", host:"retoma.alfaromeo.pt" },
};

/* deux familles de marques : historique PSA et ex-FCA */
const FAMILLE = {
  "OPEL FR":"PSA", "OPEL PT":"PSA", "CITROEN PT":"PSA", "PEUGEOT PT":"PSA", "DS PT":"PSA",
  "FIAT PT":"FCA", "JEEP PT":"FCA", "ALFA ROMEO PT":"FCA",
};
const FAM_LABEL = { PSA:"Marques PSA", FCA:"Marques ex-FCA" };

/* la marque du site, pour isoler les reprises "dans la marque" */
const OWN_BRAND = {
  "OPEL FR":"OPEL", "OPEL PT":"OPEL", "CITROEN PT":"CITROEN",
  "PEUGEOT PT":"PEUGEOT", "DS PT":"DS AUTOMOBILES",
  "FIAT PT":"FIAT", "JEEP PT":"JEEP", "ALFA ROMEO PT":"ALFA ROMEO",
};

const DIMS = [
  { k:"brand",   t:"Marque reprise",   h:"Marque du véhicule que le visiteur fait estimer." },
  { k:"fuel",    t:"Carburant",        h:"Énergie du véhicule repris." },
  { k:"project",  t:"Projet d'achat",  h:"Intention déclarée par le visiteur." },
  { k:"source",  t:"Source",           h:"Origine d'acquisition transmise par le back-office." },
  { k:"code",    t:"Code marketing",   h:"Code de campagne rattaché au lead." },
];

/* harmonisation des libelles — les 5 sites ne parlent pas la meme langue */
const STEP_MAP = {
  "homepage":"Page d'accueil", "hp":"Page d'accueil",
  "version":"Version",
  "mileage":"Kilométrage", "kilométrage":"Kilométrage",
  "contact details":"Coordonnées", "contact":"Coordonnées",
  "dealer choice":"Point de vente", "pdv":"Point de vente",
  "price estimation":"Estimation", "estimation":"Estimation",
};
const VALUE_MAP = {
  "NO PURCHASE PROJECT":"Aucun projet",
  "VN":"Véhicule neuf",
  "VO":"Véhicule d'occasion",
};

/* ============================== etat ============================== */

let SITES = [];
const DATA = {};
const CHARTS = {};

const view = {
  scope: "overview",   // "overview" | "site"
  site: null,
  report: "acquisition",
  period: null,
  compare: null,       // null = aucune comparaison
  dim: "brand",
  sort: null,
};

/* ============================ utilitaires ============================ */

const $  = (s, r) => (r || document).querySelector(s);
const el = (t, c, h) => { const n = document.createElement(t); if (c) n.className = c; if (h != null) n.innerHTML = h; return n; };
const slug = s => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;" }[c]));

const nf0 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits:0 });
const nf1 = new Intl.NumberFormat("fr-FR", { minimumFractionDigits:1, maximumFractionDigits:1 });

const fmt  = n => (n == null || !isFinite(n)) ? "—" : nf0.format(Math.round(n));
const fmt1 = n => (n == null || !isFinite(n)) ? "—" : nf1.format(n);
const pct  = n => (n == null || !isFinite(n)) ? "—" : nf1.format(n) + " %";

const MONTHS = ["janv.","févr.","mars","avril","mai","juin","juil.","août","sept.","oct.","nov.","déc."];
const shortP = p => p === "total" ? "cumul" : MONTHS[+p.slice(5, 7) - 1];

function tidy(s) {
  const u = String(s || "").trim().toUpperCase();
  if (VALUE_MAP[u]) return VALUE_MAP[u];
  return String(s || "").trim();
}
function stepLabel(s) {
  const raw = String(s || "").replace(/^\s*\d+\s*[.)]\s*/, "").trim();
  return STEP_MAP[raw.toLowerCase()] || (raw.charAt(0).toUpperCase() + raw.slice(1));
}

/* regroupe les paires en fusionnant les variantes de casse */
function pairs(x) {
  const src = Array.isArray(x) ? x : Object.entries(x || {});
  const acc = new Map();
  for (const [name, v] of src) {
    const key = String(name).trim().toUpperCase();
    const cur = acc.get(key);
    if (cur) { cur.v += v; if (v > cur.top) { cur.top = v; cur.name = name; } }
    else acc.set(key, { name, v, top: v });
  }
  return [...acc.values()].map(o => [tidy(o.name), o.v]).sort((a, b) => b[1] - a[1]);
}

/* ============================ acces donnees ============================ */

const months = d => d.months.filter(m => m !== "total");

/* periode d'ouverture : le dernier mois consolide.
   Atterrir sur un mois provisoire de 2 jours sans trafic n'aurait aucun sens. */
function defaultPeriod(d) {
  const ms = months(d).filter(m => !provisoire(d, m));
  return (ms.length ? ms : months(d))[(ms.length ? ms : months(d)).length - 1];
}

function prevPeriod(d, p) {
  const ms = months(d), i = ms.indexOf(p);
  for (let k = i - 1; k >= 0; k--) {
    if (!(d.meta[ms[k]] || {}).provisional) return ms[k];
  }
  return null;
}

const provisoire = (d, m) => !!(d.meta[m] && d.meta[m].provisional);

/* indices de D.daily correspondant a la periode.
   Le cumul ne prend que les mois consolides : un mois provisoire n'a pas
   encore ses releves GA4, l'inclure faussrait le rapport leads/sessions. */
function idx(d, p) {
  const all = d.daily.d.map((_, i) => i);
  if (p === "total") {
    const ok = new Set(months(d).filter(m => !provisoire(d, m)).map(m => m.slice(5, 7)));
    return all.filter(i => ok.has(d.daily.d[i].slice(0, 2)));
  }
  const mm = p.slice(5, 7);
  return all.filter(i => d.daily.d[i].slice(0, 2) === mm);
}

/* leads par date, reconstruits mois par mois */
function leadsByDate(d) {
  if (d.__lbd) return d.__lbd;
  const m = {};
  for (const p of months(d)) {
    const arr = (d.leads[p] && d.leads[p].daily) || [];
    const mm = p.slice(5, 7);
    arr.forEach((v, i) => { m[mm + "-" + String(i + 1).padStart(2, "0")] = v; });
  }
  d.__lbd = m;
  return m;
}

/* bloc de metriques d'une periode */
function stats(d, p) {
  if (!p || !d.meta[p]) return null;
  const days = d.meta[p].days;
  const traffic = (d.trafficMonth[p] || {}).sessions ?? null;
  const reprise = (d.repriseMonth[p] || {}).sessions ?? null;
  const leads = (d.leads[p] || {}).total;
  const sansGA4 = traffic == null || reprise == null;
  /* trafic automatise identifie : on garde le brut, on calcule sur le net */
  const an = (d.anomaly || {})[p] || null;
  const net = an ? an.reprise_nette : reprise;
  return {
    p, days, partial: !!d.meta[p].partial, label: d.meta[p].label,
    provisional: !!d.meta[p].provisional, note: d.meta[p].note || "", sansGA4,
    traffic, reprise, leads,
    bot: an ? an.sessions : 0, botPct: an ? an.part_pct : 0, net,
    jours: an ? (an.jours || []) : [],
    part: traffic ? net / traffic * 100 : null,
    conv: net ? leads / net * 100 : null,
    convBrut: reprise ? leads / reprise * 100 : null,
    per1k: traffic ? leads / traffic * 1000 : null,
    trafficPD: traffic == null ? null : traffic / days,
    reprisePD: net == null ? null : net / days,
    leadsPD: leads / days,
  };
}

/* la periode de scission pre/post portee par le bloc v2 */
function splitPeriod(d) {
  const lbl = (d.v2 && d.v2.pre_label) || "";
  const m = lbl.match(/\/(\d{2})\s*$/);
  if (!m) return null;
  return months(d).find(p => p.slice(5, 7) === m[1]) || null;
}

/* index du jour de bascule V2 dans la periode courante */
function v2Index(d, p) {
  if (!d.v2_date || !d.v2 || !d.v2.is_v2_split) return null;
  const key = d.v2_date.slice(5).replace("-", "-");
  const list = idx(d, p).map(i => d.daily.d[i]);
  const i = list.indexOf(key);
  return i >= 0 ? i : null;
}

/* ============================ composants ============================ */

function arrow(dir) {
  const p = dir > 0 ? "m5 12 7-7 7 7M12 5v14" : dir < 0 ? "m5 12 7 7 7-7M12 19V5" : "M5 12h14";
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="${p}"/></svg>`;
}

/* ecart : "pts" pour les taux, pourcentage relatif pour les volumes */
function delta(cur, ref, mode) {
  if (cur == null || ref == null || !isFinite(cur) || !isFinite(ref)) return "";
  const isPts = mode === "pts";
  const v = isPts ? cur - ref : (ref ? (cur - ref) / ref * 100 : null);
  if (v == null || !isFinite(v)) return "";
  const dir = Math.abs(v) < 0.05 ? 0 : (v > 0 ? 1 : -1);
  const cls = dir > 0 ? "up" : dir < 0 ? "down" : "flat";
  const txt = (v > 0 ? "+" : "") + nf1.format(v) + (isPts ? " pts" : " %");
  return `<span class="delta ${cls}">${arrow(dir)}${txt}</span>`;
}

function spark(values, color) {
  const v = (values || []).filter(x => x != null && isFinite(x));
  if (v.length < 2) return "";
  const w = 78, h = 24, min = Math.min(...v), max = Math.max(...v), span = (max - min) || 1;
  const pt = v.map((y, i) => [i / (v.length - 1) * w, h - 2 - (y - min) / span * (h - 4)]);
  const line = pt.map(([x, y]) => x.toFixed(1) + "," + y.toFixed(1)).join(" ");
  const area = `0,${h} ${line} ${w},${h}`;
  const id = "g" + Math.random().toString(36).slice(2, 8);
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true">
    <defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="${color}" stop-opacity=".18"/>
      <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
    </linearGradient></defs>
    <polygon points="${area}" fill="url(#${id})"/>
    <polyline points="${line}" fill="none" stroke="${color}" stroke-width="1.6"
      stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>
    <circle cx="${pt[pt.length-1][0].toFixed(1)}" cy="${pt[pt.length-1][1].toFixed(1)}" r="2" fill="${color}"/>
  </svg>`;
}

function score(o) {
  return `<div class="score">
    <div class="score-lbl">${esc(o.label)}</div>
    <div class="score-val">${o.value}${o.unit ? `<u>${o.unit}</u>` : ""}</div>
    <div class="score-foot">
      <div>
        <div class="score-sub">${o.sub || ""}</div>
        ${o.delta || ""}
      </div>
      ${o.spark || ""}
    </div>
  </div>`;
}

function bar(ratio, tone) {
  const w = Math.max(0, Math.min(1, ratio || 0)) * 100;
  return `<span class="bar ${tone || ""}"><i style="width:${w.toFixed(1)}%"></i></span>`;
}

/* ============================ graphiques ============================ */

Chart.defaults.font.family = '"IBM Plex Mono", ui-monospace, monospace';
Chart.defaults.font.size = 10.5;
Chart.defaults.color = C.ink3;
Chart.defaults.animation.duration = 420;
Chart.defaults.maintainAspectRatio = false;

/* bande + etiquette du jour de bascule V2 */
const V2MARK = {
  id: "v2mark",
  beforeDatasetsDraw(chart) {
    const o = chart.options.plugins.v2mark;
    if (!o || o.index == null) return;
    const a = chart.chartArea, ctx = chart.ctx;
    if (!a) return;
    const x = chart.scales.x.getPixelForValue(o.index);
    ctx.save();
    ctx.fillStyle = "rgba(245,197,24,.14)";
    ctx.fillRect(x, a.top, a.right - x, a.bottom - a.top);
    ctx.strokeStyle = C.tag; ctx.lineWidth = 1.6;
    ctx.beginPath(); ctx.moveTo(x, a.top); ctx.lineTo(x, a.bottom); ctx.stroke();
    if (o.label) {
      ctx.font = '700 9px "IBM Plex Sans Condensed", sans-serif';
      const w = ctx.measureText(o.label).width + 12;
      const lx = Math.min(x, a.right - w);
      ctx.fillStyle = C.tag;
      ctx.beginPath(); ctx.roundRect(lx, a.top + 4, w, 15, 3); ctx.fill();
      ctx.fillStyle = C.ink; ctx.textBaseline = "middle"; ctx.textAlign = "center";
      ctx.fillText(o.label, lx + w / 2, a.top + 12);
    }
    ctx.restore();
  }
};
Chart.register(V2MARK);

function tooltipCfg(fmtFn) {
  return {
    backgroundColor: C.ink, padding: 10, cornerRadius: 6, displayColors: true,
    boxWidth: 8, boxHeight: 8, boxPadding: 4,
    titleFont: { family:'"IBM Plex Sans", sans-serif', weight:"600", size:11.5 },
    bodyFont: { family:'"IBM Plex Mono", monospace', size:11.5 },
    callbacks: { label: c => "  " + c.dataset.label + " : " + (fmtFn || fmt)(c.parsed.y) }
  };
}

function axes(showX, tickCount) {
  return {
    x: {
      grid: { display:false }, border:{ color:C.line },
      ticks: {
        display: showX !== false, maxRotation:0, autoSkip:true,
        maxTicksLimit: tickCount || 10, padding:6, color:C.ink3
      }
    },
    y: {
      beginAtZero:true, border:{ display:false },
      grid: { color:C.line2, drawTicks:false },
      ticks: { padding:9, maxTicksLimit:5, callback:v => fmt(v) }
    }
  };
}

function draw(key, cfg) {
  if (CHARTS[key]) CHARTS[key].destroy();
  const cv = document.getElementById(key);
  if (!cv) return;
  CHARTS[key] = new Chart(cv.getContext("2d"), cfg);
}
function clearCharts() {
  Object.keys(CHARTS).forEach(k => { CHARTS[k].destroy(); delete CHARTS[k]; });
}

/* ============================== rail ============================== */

function euStars() {
  let s = "";
  for (let i = 0; i < 12; i++) {
    const a = (i / 12) * Math.PI * 2 - Math.PI / 2;
    s += `<circle cx="${(12 + Math.cos(a) * 6.4).toFixed(2)}" cy="${(12 + Math.sin(a) * 6.4).toFixed(2)}" r="1.05" fill="#fff"/>`;
  }
  return `<svg viewBox="0 0 24 24" aria-hidden="true">${s}</svg>`;
}

function renderRail() {
  const groupes = ["PSA", "FCA"];
  $("#plates").innerHTML = groupes.map(g => {
    const liste = SITES.filter(s => (FAMILLE[s] || "PSA") === g);
    if (!liste.length) return "";
    return `<div class="fam">${esc(FAM_LABEL[g])}</div>` + liste.map(s => {
      const h = HOSTS[s] || { pays:"", host:"" };
      const band = h.pays === "P" ? "var(--tag)" : "var(--eu)";
      return `<button class="plate" data-site="${esc(s)}" style="--band:${band}" aria-pressed="false">
        <span class="plate-eu">${euStars()}<b>${esc(h.pays)}</b></span>
        <span class="plate-face">
          <span class="plate-name">${esc(s)}</span>
          <span class="plate-sub">${esc(h.host)}</span>
        </span>
        <span class="plate-band"></span>
      </button>`;
    }).join("");
  }).join("");

  $("#plates").addEventListener("click", e => {
    const b = e.target.closest(".plate");
    if (b) selectSite(b.dataset.site);
  });
  $("#navOverview").addEventListener("click", () => selectOverview());
}

function syncRail() {
  $("#navOverview").classList.toggle("on", view.scope === "overview");
  document.querySelectorAll(".plate").forEach(p => {
    const on = view.scope === "site" && p.dataset.site === view.site;
    p.classList.toggle("on", on);
    p.setAttribute("aria-pressed", on ? "true" : "false");
  });
}

/* ============================ controle de periode ============================ */

function periodList() {
  const d = view.scope === "site" ? DATA[view.site] : DATA[SITES[0]];
  return d.periods || d.months;
}
function metaOf(p) {
  const d = view.scope === "site" ? DATA[view.site] : DATA[SITES[0]];
  return d.meta[p];
}

function renderPeriodControl() {
  const list = periodList();
  const d = view.scope === "site" ? DATA[view.site] : null;

  $("#ctlLabel").textContent = metaOf(view.period).label;
  $("#ctlCmp").textContent = view.compare ? "vs " + shortP(view.compare) : "sans comparaison";
  $("#ctlCmp").hidden = false;

  const pf = $("#partialFlag");
  const mm = metaOf(view.period);
  const isPartial = d ? !!d.meta[view.period].partial
                      : SITES.some(s => (DATA[s].meta[view.period] || {}).partial);
  pf.hidden = !isPartial;
  if (isPartial) {
    pf.textContent = mm.provisional ? "Mois en cours" : "Données partielles";
    pf.title = mm.note || "Ce mois n'est pas complet.";
  }

  $("#popPeriods").innerHTML = list.map(p =>
    `<button class="pop-opt ${p === view.period ? "on" : ""}" data-period="${p}">
      <span>${esc(metaOf(p).label)}</span><small>${metaOf(p).days} j</small>
    </button>`).join("");

  /* un mois provisoire ne sert pas de reference : 2 jours face a 31 n'a pas de sens */
  const opts = list.filter(p => p !== view.period && p !== "total"
    && !(metaOf(p) || {}).provisional);
  $("#popCompare").innerHTML =
    `<button class="pop-opt ${!view.compare ? "on" : ""}" data-cmp="">Aucune</button>` +
    opts.map(p => `<button class="pop-opt ${view.compare === p ? "on" : ""}" data-cmp="${p}">
      <span>${esc(metaOf(p).label)}</span><small>${metaOf(p).days} j</small></button>`).join("");
}

function wirePeriodControl() {
  const btn = $("#ctlBtn"), pop = $("#pop");
  const close = () => { pop.hidden = true; btn.setAttribute("aria-expanded", "false"); };

  btn.addEventListener("click", e => {
    e.stopPropagation();
    const open = pop.hidden;
    pop.hidden = !open;
    btn.setAttribute("aria-expanded", open ? "true" : "false");
  });
  document.addEventListener("click", e => { if (!pop.contains(e.target)) close(); });
  document.addEventListener("keydown", e => { if (e.key === "Escape") close(); });

  pop.addEventListener("click", e => {
    const p = e.target.closest("[data-period]");
    if (p) {
      view.period = p.dataset.period;
      const prev = view.scope === "site" ? prevPeriod(DATA[view.site], view.period) : prevPeriod(DATA[SITES[0]], view.period);
      view.compare = prev;
      close(); render(); return;
    }
    const c = e.target.closest("[data-cmp]");
    if (c) { view.compare = c.dataset.cmp || null; close(); render(); }
  });
}

/* ============================ navigation ============================ */

const REPORTS = [
  { k:"acquisition", t:"Acquisition" },
  { k:"leads",       t:"Leads" },
  { k:"parcours",    t:"Parcours" },
];

function renderTabs() {
  const nav = $("#tabs");
  nav.hidden = view.scope !== "site";
  if (nav.hidden) { nav.innerHTML = ""; return; }
  nav.innerHTML = REPORTS.map(r =>
    `<button class="tab ${r.k === view.report ? "on" : ""}" data-report="${r.k}">${r.t}</button>`).join("");
}

function selectOverview() {
  view.scope = "overview"; view.site = null;
  render();
}
async function selectSite(site) {
  await load(site);
  view.scope = "site"; view.site = site;
  if (!DATA[site].meta[view.period]) view.period = defaultPeriod(DATA[site]);
  if (view.compare && !DATA[site].meta[view.compare]) view.compare = prevPeriod(DATA[site], view.period);
  render();
}

/* ============================== rapports ============================== */

function panel(id) {
  document.querySelectorAll(".panel").forEach(p => p.hidden = true);
  const p = document.getElementById(id);
  p.hidden = false;
  return p;
}

/* ---------------------------- vue d'ensemble ---------------------------- */

function renderOverview() {
  const p = view.period, cmp = view.compare;
  const rows = SITES.map(s => {
    const d = DATA[s];
    const st = stats(d, p), ref = cmp ? stats(d, cmp) : null;
    const ids = idx(d, p), lbd = leadsByDate(d);
    return { s, d, st, ref, fam: FAMILLE[s] || "PSA",
             sparkLeads: ids.map(i => lbd[d.daily.d[i]]).filter(v => v != null) };
  });

  const days = metaOf(p).days;
  const daysRef = cmp ? metaOf(cmp).days : null;
  const som = (k, r) => r.reduce((a, x) => a + (x.st[k] || 0), 0);
  const somRef = (k, r) => cmp ? r.reduce((a, x) => a + ((x.ref && x.ref[k]) || 0), 0) : null;

  const sansGA4 = rows.some(r => r.st.sansGA4);
  const tLeads = som("leads", rows), tNet = som("net", rows), tTraf = som("traffic", rows);
  const tBot = som("bot", rows);
  const rLeads = somRef("leads", rows), rNet = somRef("net", rows), rTraf = somRef("traffic", rows);
  const totalJour = mergeDaily(rows);

  const host = panel("panel-overview");
  host.innerHTML = `
    <div class="scores">
      ${score({ label:"Leads", value:fmt(tLeads), sub:fmt1(tLeads / days) + " / jour",
        delta: cmp ? delta(tLeads / days, rLeads / daysRef) : "", spark:spark(totalJour, C.ink) })}
      ${score({ label:"Sessions outil de reprise", value: sansGA4 ? "—" : fmt(tNet),
        sub: sansGA4 ? "relevé GA4 en attente" : fmt1(tNet / days) + " / jour",
        delta: cmp && !sansGA4 ? delta(tNet / days, rNet / daysRef) : "" })}
      ${score({ label:"Leads BO / sessions reprise",
        value: sansGA4 ? "—" : pct(tNet ? tLeads / tNet * 100 : null),
        sub: sansGA4 ? "relevé GA4 en attente" : "sur l'ensemble du parc",
        delta: cmp && rNet && !sansGA4 ? delta(tLeads / tNet * 100, rLeads / rNet * 100, "pts") : "" })}
      ${score({ label:"Sessions site parent", value: sansGA4 ? "—" : fmt(tTraf),
        sub: sansGA4 ? "relevé GA4 en attente" : fmt1(tTraf / days) + " / jour",
        delta: cmp && !sansGA4 ? delta(tTraf / days, rTraf / daysRef) : "" })}
    </div>
    ${sansGA4 ? `<div class="card"><div class="v2-strip">
      <span class="tagchip">Provisoire</span>
      <p>Les relevés GA4 de ${esc(metaOf(p).label)} ne sont pas encore disponibles. Seuls les leads,
      issus du back-office, sont affichés. Trafic et transformation apparaîtront une fois GA4 relevé.</p>
    </div></div>` : ""}

    ${bandeauSante()}

    ${tBot ? `<div class="card"><div class="v2-strip">
      <span class="tagchip">Robot</span>
      <p><b>${fmt(tBot)} sessions automatisées</b> ont été identifiées sur les sites ex-FCA et retirées du calcul de transformation. Les volumes affichés restent les valeurs GA4 brutes.</p>
    </div></div>` : ""}

    <div class="card">
      <div class="card-head">
        <div>
          <h2>Le parc, site par site</h2>
          <p>Chaque ligne suit la même chaîne : le site parent amène du trafic vers l'outil de reprise, qui produit des leads. Cliquez une ligne pour ouvrir le site.</p>
        </div>
      </div>
      <div class="card-body flush"><table class="grid" id="ovTable"></table></div>
      <div class="note">La <b>part vers la reprise</b> mesure combien de sessions du site parent atteignent l'outil. <b>Leads BO / sessions reprise</b> part des leads du back-office, qui les enregistre tous. Ce taux est donc structurellement supérieur au Conversion Rate de Looker, qui ne compte que les leads vus par GA4 — ceux des visiteurs ayant accepté les cookies. Sur OPEL FR, GA4 en a capté 34 % en avril, 30 % en mai et 57 % en juin : cette captation variant d'un mois sur l'autre, le taux de Looker ne se compare pas dans le temps. <b>Complétion parcours</b> est une mesure GA4 en utilisateurs actifs, de l'entrée jusqu'à l'estimation affichée. Les deux colonnes ne mesurent pas la même chose.</div>
    </div>

    <div class="card">
      <div class="card-head">
        <div><h2>Leads par jour, tout le parc</h2><p>${esc(metaOf(p).label)} — total des ${rows.length} sites.</p></div>
        <div class="legend"><span><i style="background:${C.ink}"></i>Total parc</span></div>
      </div>
      <div class="card-body"><div class="plot tall"><canvas id="ovChart"></canvas></div></div>
    </div>`;

  const maxLeads = Math.max(...rows.map(r => r.st.leads || 0));
  const ligne = r => `
    <tr class="clickable" data-site="${esc(r.s)}">
      <td><span class="cell-name"><b>${esc(r.s)}</b>${r.st.bot ? `<span class="flag">robot ${r.st.botPct} %</span>` : ""}</span></td>
      <td class="num dim">${r.st.sansGA4 ? "—" : fmt(r.st.traffic)}</td>
      <td class="num dim">${r.st.sansGA4 ? "—" : fmt(r.st.net)}</td>
      <td class="num dim">${r.st.sansGA4 ? "—" : pct(r.st.part)}</td>
      <td class="num">${fmt(r.st.leads)}</td>
      <td class="td-bar">${bar((r.st.leads || 0) / maxLeads, "k")}</td>
      <td class="num">${r.st.sansGA4 ? "—" : pct(r.st.conv)}</td>
      <td class="num dim">${pct(((r.d.funnelMonth || {})[view.period] || {}).conversion_pct)}</td>
      <td>${spark(r.sparkLeads, C.ink4)}</td>
    </tr>`;

  const sousTotal = (g, r) => {
    const l = som("leads", r), n = som("net", r), t = som("traffic", r);
    const sg = r.some(x => x.st.sansGA4);
    return `<tr class="total"><td>${esc(FAM_LABEL[g])}</td>
      <td class="num">${sg ? "—" : fmt(t)}</td><td class="num">${sg ? "—" : fmt(n)}</td>
      <td class="num">${sg ? "—" : pct(t ? n / t * 100 : null)}</td>
      <td class="num">${fmt(l)}</td><td></td>
      <td class="num">${sg ? "—" : pct(n ? l / n * 100 : null)}</td><td></td><td></td></tr>`;
  };

  const table = $("#ovTable");
  table.innerHTML = `
    <thead><tr>
      <th>Site</th><th>Sessions site</th><th>Sessions reprise</th>
      <th>Part vers la reprise</th><th>Leads BO</th><th></th><th>Leads BO / sessions</th><th>Complétion parcours</th><th>Tendance</th>
    </tr></thead>
    <tbody>${["PSA", "FCA"].map(g => {
      const r = rows.filter(x => x.fam === g);
      if (!r.length) return "";
      return `<tr class="grp"><td colspan="9">${esc(FAM_LABEL[g])}</td></tr>`
        + r.map(ligne).join("") + sousTotal(g, r);
    }).join("")}
      <tr class="total gt">
        <td>Ensemble du parc</td>
        <td class="num">${sansGA4 ? "—" : fmt(tTraf)}</td><td class="num">${sansGA4 ? "—" : fmt(tNet)}</td>
        <td class="num">${sansGA4 ? "—" : pct(tTraf ? tNet / tTraf * 100 : null)}</td>
        <td class="num">${fmt(tLeads)}</td><td></td>
        <td class="num">${sansGA4 ? "—" : pct(tNet ? tLeads / tNet * 100 : null)}</td><td></td><td></td>
      </tr>
    </tbody>`;
  table.addEventListener("click", e => {
    const tr = e.target.closest("tr[data-site]");
    if (tr) selectSite(tr.dataset.site);
  });

  const base = DATA[SITES[0]];
  const labels = idx(base, p).map(i => base.daily.d[i]);
  draw("ovChart", {
    type:"line",
    data:{ labels, datasets:[{ label:"Total parc", data:totalJour,
      borderColor:C.ink, backgroundColor:"rgba(14,17,22,.07)", fill:true,
      borderWidth:2, pointRadius:0, pointHoverRadius:3.5, tension:.28 }] },
    options:{
      interaction:{ mode:"index", intersect:false },
      plugins:{ legend:{ display:false }, tooltip:tooltipCfg(), v2mark:{ index:null } },
      scales:axes(true, 12)
    }
  });
}

const SERIES = [C.ink, C.eu, C.jade, "#8B5CF6", "#C4462F", "#B07C00", "#0E7490", "#9D174D"];

function mergeDaily(rows) {
  const n = Math.max(...rows.map(r => r.sparkLeads.length));
  const out = [];
  for (let i = 0; i < n; i++) out.push(rows.reduce((a, r) => a + (r.sparkLeads[i] || 0), 0));
  return out;
}

/* ---------------------------- acquisition ---------------------------- */

function renderAcquisition() {
  const d = DATA[view.site], p = view.period, cmp = view.compare;
  const st = stats(d, p), ref = cmp ? stats(d, cmp) : null;
  const ids = idx(d, p);
  const labels = ids.map(i => d.daily.d[i]);
  const su = ids.map(i => d.daily.u[i]);
  const sr = ids.map(i => d.daily.rep[i]);
  const vi = v2Index(d, p);

  const host = panel("panel-acquisition");
  if (st.sansGA4) {
    host.innerHTML = `<div class="card"><div class="empty">
      <b>Relevés GA4 indisponibles sur ${esc(st.label)}</b>
      <p>${esc(st.note || "Le trafic de ce mois n'a pas encore été relevé.")}</p>
      <p style="margin-top:10px">L'onglet <b>Leads</b> reste consultable : les leads proviennent du back-office, pas de GA4.</p>
    </div></div>`;
    return;
  }
  host.innerHTML = `
    ${st.bot ? `<div class="card"><div class="v2-strip">
      <span class="tagchip">Robot</span>
      <p><b>${fmt(st.bot)} sessions automatisées</b> identifiées sur ${st.jours.length} journée${st.jours.length > 1 ? "s" : ""}
      (${esc(st.jours.join(", "))}), soit ${st.botPct} % du trafic de reprise du mois. Origine Espagne, Chrome desktop.
      Le graphique montre les volumes bruts ; les taux sont calculés hors robot.</p>
    </div></div>` : ""}
    <div class="scores">
      ${score({ label:"Sessions site parent", value:fmt(st.traffic),
        sub:fmt1(st.trafficPD) + " / jour",
        delta: ref ? delta(st.trafficPD, ref.trafficPD) : "", spark:spark(su, C.eu) })}
      ${score({ label:"Sessions outil de reprise", value:fmt(st.reprise),
        sub: st.bot ? fmt(st.net) + " hors robot" : fmt1(st.reprisePD) + " / jour",
        delta: ref ? delta(st.reprisePD, ref.reprisePD) : "", spark:spark(sr, C.jade) })}
      ${score({ label:"Part vers la reprise", value:pct(st.part),
        sub:"des sessions du site parent",
        delta: ref ? delta(st.part, ref.part, "pts") : "" })}
      ${score({ label:"Leads pour 1 000 sessions site", value:fmt1(st.per1k),
        sub:"chaîne complète",
        delta: ref ? delta(st.per1k, ref.per1k) : "" })}
    </div>

    <div class="card">
      <div class="card-head">
        <div>
          <h2>Deux niveaux, deux échelles</h2>
          <p>Le site parent et l'outil de reprise n'ont pas le même ordre de grandeur. Ils sont tracés l'un sous l'autre, sur le même axe des jours, plutôt que superposés — les hauteurs ne se comparent pas, les formes si.</p>
        </div>
      </div>
      <div class="card-body">
        <div class="twin-wrap">
          <div class="twin-tag"><i style="background:${C.eu}"></i>Sessions site parent</div>
          <div class="plot twin"><canvas id="acqTop"></canvas></div>
          <div class="twin-tag"><i style="background:${C.jade}"></i>Sessions outil de reprise</div>
          <div class="plot twin"><canvas id="acqBot"></canvas></div>
        </div>
      </div>
      ${vi != null ? `<div class="note"><b>Bande jaune :</b> période postérieure à la bascule V2 du ${esc(frDate(d.v2_date))}.</div>` : ""}
    </div>

    <div class="card">
      <div class="card-head">
        <div><h2>Mois par mois</h2><p>Du site parent au lead, chaque étage de la chaîne.</p></div>
      </div>
      <div class="card-body flush"><table class="grid" id="acqTable"></table></div>
      <div class="note">Les colonnes <b>par jour</b> sont celles à comparer entre mois : juillet compte 31 jours, juin 30. <b>Leads BO / sessions reprise</b> part des leads du back-office, qui les enregistre tous. Ce taux est donc structurellement supérieur au Conversion Rate de Looker, qui ne compte que les leads vus par GA4 — ceux des visiteurs ayant accepté les cookies. Sur OPEL FR, GA4 en a capté 34 % en avril, 30 % en mai et 57 % en juin : cette captation variant d'un mois sur l'autre, le taux de Looker ne se compare pas dans le temps. <b>Complétion parcours</b> est une mesure GA4 en utilisateurs actifs, de l'entrée jusqu'à l'estimation affichée. Les deux colonnes ne mesurent pas la même chose.</div>
    </div>`;

  const opts = (showX, markIdx) => ({
    interaction:{ mode:"index", intersect:false },
    plugins:{
      legend:{ display:false }, tooltip:tooltipCfg(),
      v2mark:{ index:markIdx, label: markIdx != null && showX ? "V2" : null }
    },
    scales:axes(showX, 12)
  });

  draw("acqTop", {
    type:"line",
    data:{ labels, datasets:[{ label:"Sessions site parent", data:su,
      borderColor:C.eu, backgroundColor:"rgba(27,63,184,.08)", fill:true,
      borderWidth:1.9, pointRadius:0, pointHoverRadius:3.5, tension:.3 }] },
    options:opts(false, vi)
  });
  draw("acqBot", {
    type:"line",
    data:{ labels, datasets:[{ label:"Sessions outil de reprise", data:sr,
      borderColor:C.jade, backgroundColor:"rgba(11,123,107,.10)", fill:true,
      borderWidth:1.9, pointRadius:0, pointHoverRadius:3.5, tension:.3 }] },
    options:opts(true, vi)
  });

  /* tableau de trafic : seuls les mois dont GA4 est releve */
  const ms = months(d).filter(m => !provisoire(d, m));
  $("#acqTable").innerHTML = `
    <thead><tr>
      <th>Mois</th><th>Jours</th><th>Sessions site</th><th>/ jour</th>
      <th>Sessions reprise</th><th>/ jour</th><th>Part</th><th>Leads BO</th><th>Leads BO / sessions</th><th>Complétion parcours</th>
    </tr></thead>
    <tbody>${ms.map(m => {
      const s = stats(d, m), on = m === p;
      return `<tr${on ? ' style="background:var(--sunk)"' : ""}>
        <td><span class="cell-name"><b>${esc(s.label)}</b>${s.partial ? '<span class="flag">partiel</span>' : ""}</span></td>
        <td class="num dim">${s.days}</td>
        <td class="num">${fmt(s.traffic)}</td>
        <td class="num dim">${fmt(s.trafficPD)}</td>
        <td class="num">${fmt(s.reprise)}</td>
        <td class="num dim">${fmt(s.reprisePD)}</td>
        <td class="num">${pct(s.part)}</td>
        <td class="num">${fmt(s.leads)}</td>
        <td class="num">${pct(s.conv)}</td>
        <td class="num dim">${pct(((d.funnelMonth || {})[m] || {}).conversion_pct)}</td>
      </tr>`;
    }).join("")}</tbody>`;
}

function frDate(iso) {
  if (!iso) return "";
  const [y, m, dd] = iso.split("-");
  return `${+dd} ${MONTHS[+m - 1]} ${y}`;
}

/* ------------------------------- leads ------------------------------- */

function renderLeads() {
  const d = DATA[view.site], p = view.period, cmp = view.compare;
  const st = stats(d, p), ref = cmp ? stats(d, cmp) : null;
  const ids = idx(d, p), lbd = leadsByDate(d);
  const labels = ids.map(i => d.daily.d[i]);
  const series = ids.map(i => lbd[d.daily.d[i]] ?? null);
  const vi = v2Index(d, p);

  const own = OWN_BRAND[view.site];
  const brands = pairs((d.leads[p] || {}).brand);
  const ownV = (brands.find(b => b[0].toUpperCase() === own) || [null, 0])[1];
  const ownShare = st.leads ? ownV / st.leads * 100 : null;
  const refBrands = ref ? pairs((d.leads[cmp] || {}).brand) : null;
  const refOwn = refBrands ? (refBrands.find(b => b[0].toUpperCase() === own) || [null, 0])[1] : null;
  const refShare = ref && ref.leads ? refOwn / ref.leads * 100 : null;

  /* moyenne mobile 7 jours */
  const ma = series.map((_, i) => {
    const w = series.slice(Math.max(0, i - 6), i + 1).filter(v => v != null);
    return w.length ? w.reduce((a, b) => a + b, 0) / w.length : null;
  });

  const host = panel("panel-leads");
  host.innerHTML = `
    ${st.provisional ? `<div class="card"><div class="v2-strip">
      <span class="tagchip">Provisoire</span>
      <p>${esc(st.note)}</p>
    </div></div>` : ""}
    ${st.bot ? `<div class="card"><div class="v2-strip">
      <span class="tagchip">Robot</span>
      <p>Le taux de transformation est calculé sur <b>${fmt(st.net)} sessions réelles</b> et non sur les
      ${fmt(st.reprise)} sessions brutes : ${fmt(st.bot)} d'entre elles sont automatisées.
      En brut, le taux afficherait ${pct(st.convBrut)}.</p>
    </div></div>` : ""}
    <div class="scores">
      ${score({ label:"Leads", value:fmt(st.leads),
        sub:fmt1(st.leadsPD) + " / jour",
        delta: ref ? delta(st.leadsPD, ref.leadsPD) : "", spark:spark(series, C.ink) })}
      ${score({ label:"Leads BO / sessions reprise", value: st.sansGA4 ? "—" : pct(st.conv),
        sub: st.sansGA4 ? "relevé GA4 en attente" : "leads du back-office",
        delta: ref && !st.sansGA4 ? delta(st.conv, ref.conv, "pts") : "" })}
      ${score({ label:"Reprises de la marque", value:pct(ownShare),
        sub:`${fmt(ownV)} véhicules ${esc(own || "")}`,
        delta: refShare != null ? delta(ownShare, refShare, "pts") : "" })}
      ${score({ label:"Leads pour 1 000 sessions site", value: st.sansGA4 ? "—" : fmt1(st.per1k),
        sub: st.sansGA4 ? "relevé GA4 en attente" : "chaîne complète",
        delta: ref && !st.sansGA4 ? delta(st.per1k, ref.per1k) : "" })}
    </div>

    <div class="card">
      <div class="card-head">
        <div>
          <h2>Leads par jour</h2>
          <p>Barres : le volume quotidien. Courbe : la moyenne des sept derniers jours, qui lisse l'effet week-end.</p>
        </div>
        <div class="legend">
          <span><i style="background:${C.ink}"></i>Leads du jour</span>
          <span><i style="background:${C.jade}"></i>Moyenne 7 jours</span>
        </div>
      </div>
      <div class="card-body"><div class="plot tall"><canvas id="leadsChart"></canvas></div></div>
      ${st.partial ? `<div class="note"><b>Le 31 juillet manque.</b> L'API d'extraction a renvoyé une erreur ce jour-là. Le trafic et le parcours couvrent bien le mois entier.</div>` : ""}
    </div>

    <div class="card">
      <div class="card-head">
        <div>
          <h2>Qui fait estimer son véhicule</h2>
          <p id="dimHelp">—</p>
        </div>
        <div class="seg" id="dimSeg">${DIMS.map(x =>
          `<button data-dim="${x.k}" class="${x.k === view.dim ? "on" : ""}">${x.t}</button>`).join("")}</div>
      </div>
      <div class="card-body flush"><table class="grid" id="dimTable"></table></div>
      <div class="note" id="dimNote"></div>
    </div>`;

  draw("leadsChart", {
    data:{ labels, datasets:[
      { type:"bar", label:"Leads du jour", data:series,
        backgroundColor:C.ink, borderRadius:2, barPercentage:.72, categoryPercentage:.92, order:2 },
      { type:"line", label:"Moyenne 7 jours", data:ma,
        borderColor:C.jade, borderWidth:2, pointRadius:0, pointHoverRadius:3.5, tension:.35, order:1 }
    ]},
    options:{
      interaction:{ mode:"index", intersect:false },
      plugins:{
        legend:{ display:false }, tooltip:tooltipCfg(v => fmt1(v)),
        v2mark:{ index:vi, label: vi != null ? "V2" : null }
      },
      scales:axes(true, 12)
    }
  });

  $("#dimSeg").addEventListener("click", e => {
    const b = e.target.closest("[data-dim]");
    if (!b) return;
    view.dim = b.dataset.dim;
    document.querySelectorAll("#dimSeg button").forEach(x => x.classList.toggle("on", x === b));
    renderDim();
  });
  renderDim();

  function renderDim() {
    const meta = DIMS.find(x => x.k === view.dim);
    $("#dimHelp").textContent = meta.h;
    const list = pairs((d.leads[p] || {})[view.dim]);
    const covered = list.reduce((a, b) => a + b[1], 0);
    /* la dimension ne couvre pas toujours tous les leads : on montre l'ecart */
    const tot = st.leads || covered;
    const gap = Math.max(0, tot - covered);
    const max = list.length ? list[0][1] : 1;
    const shown = list.slice(0, 12);
    const rest = list.slice(12);
    const restSum = rest.reduce((a, b) => a + b[1], 0);

    $("#dimTable").innerHTML = `
      <thead><tr><th>${esc(meta.t)}</th><th></th><th>Leads</th><th>Part</th></tr></thead>
      <tbody>${shown.map(([n, v], i) => `
        <tr>
          <td><span class="cell-name"><span class="rank">${i + 1}</span><b title="${esc(n)}">${esc(n)}</b></span></td>
          <td class="td-bar">${bar(v / max, "k")}</td>
          <td class="num">${fmt(v)}</td>
          <td class="num dim">${pct(tot ? v / tot * 100 : null)}</td>
        </tr>`).join("")}
        ${rest.length ? `<tr>
          <td><span class="cell-name"><span class="rank"></span><b style="color:var(--ink-3)">${rest.length} autres</b></span></td>
          <td class="td-bar">${bar(restSum / max, "k")}</td>
          <td class="num dim">${fmt(restSum)}</td>
          <td class="num dim">${pct(tot ? restSum / tot * 100 : null)}</td>
        </tr>` : ""}
        ${gap ? `<tr>
          <td><span class="cell-name"><span class="rank"></span><b style="color:var(--ink-3)">${
            view.dim === "brand" && list.length >= 25 ? "Autres marques" : "Non renseigné"}</b></span></td>
          <td class="td-bar">${bar(gap / max, "k")}</td>
          <td class="num dim">${fmt(gap)}</td>
          <td class="num dim">${pct(tot ? gap / tot * 100 : null)}</td>
        </tr>` : ""}
        <tr class="total"><td>Total des leads</td><td></td><td class="num">${fmt(tot)}</td><td class="num">100,0 %</td></tr>
      </tbody>`;

    /* la liste des marques est plafonnee a 25 par le pipeline : l'ecart n'est
       pas une valeur manquante mais une queue tronquee. */
    const tronque = view.dim === "brand" && list.length >= 25;
    $("#dimNote").innerHTML = !gap
      ? `Toutes les lignes du mois portent une valeur pour cette dimension.`
      : tronque
        ? `<b>${fmt(gap)} leads</b> portent une marque hors des 25 plus fréquentes, que la source ne détaille pas. Les parts sont calculées sur le total des leads.`
        : `<b>${fmt(gap)} leads</b> n'ont pas de valeur renseignée pour cette dimension, soit ${pct(gap / tot * 100)} du mois. Les parts sont calculées sur le total des leads, pas sur les seules lignes renseignées.`;
  }
}

/* ------------------------------ parcours ------------------------------ */

function renderParcours() {
  const d = DATA[view.site], p = view.period, cmp = view.compare;
  const host = panel("panel-parcours");
  const fm = d.funnelMonth[p];

  if (!fm) {
    const st0 = stats(d, p);
    host.innerHTML = `<div class="card"><div class="empty">
      <b>Pas de parcours sur ${esc(st0 ? st0.label : "cette période")}</b>
      <p>${st0 && st0.note ? esc(st0.note)
        : "Les entonnoirs sont relevés mois par mois. Choisissez un mois dans le sélecteur de période."}</p>
    </div></div>`;
    return;
  }

  const steps = fm.steps || [];
  const first = steps.length ? steps[0].users : 0;
  const last = steps.length ? steps[steps.length - 1].users : 0;
  const fmRef = cmp ? d.funnelMonth[cmp] : null;
  const drop12 = first && steps[1] ? (first - steps[1].users) / first * 100 : null;

  const isSplitHere = splitPeriod(d) === p && d.v2steps && d.v2steps.length;
  const v2 = d.v2 || {};
  const realV2 = !!v2.is_v2_split;

  host.innerHTML = `
    ${isSplitHere && realV2 ? `<div class="card" style="margin-bottom:14px">
      <div class="v2-strip">
        <span class="tagchip">V2</span>
        <p>Bascule le <b>${esc(frDate(d.v2_date))}</b>. Les deux moitiés du mois sont comparées ci-dessous : <b>${esc(v2.pre_label)}</b> avant, <b>${esc(v2.post_label)}</b> après.</p>
      </div>
    </div>` : ""}

    <div class="scores">
      ${score({ label:"Entrées de parcours", value:fmt(first),
        sub:fmt1(fm.users_per_day) + " / jour",
        delta: fmRef ? delta(first / d.meta[p].days, fmRef.steps[0].users / d.meta[cmp].days) : "" })}
      ${score({ label:"Estimations terminées", value:fmt(last),
        sub:fmt1(last / d.meta[p].days) + " / jour",
        delta: fmRef ? delta(last / d.meta[p].days, fmRef.steps[fmRef.steps.length - 1].users / d.meta[cmp].days) : "" })}
      ${score({ label:"Taux de complétion", value:pct(fm.conversion_pct),
        sub:"de l'entrée à l'estimation",
        delta: fmRef ? delta(fm.conversion_pct, fmRef.conversion_pct, "pts") : "" })}
      ${score({ label:"Perte à la première étape", value:pct(drop12),
        sub:"entrée → choix de version" })}
    </div>

    <div class="card">
      <div class="card-head">
        <div>
          <h2>Le parcours, étape par étape</h2>
          <p>Mesuré en <b>utilisateurs actifs</b> : l'exploration de funnel GA4 ne propose pas les sessions. Ces volumes ne se comparent pas à ceux de l'onglet Acquisition.</p>
        </div>
        ${isSplitHere ? `<div class="legend">
          <span><i style="background:var(--ink-4)"></i>${esc(v2.pre_label)}</span>
          <span><i style="background:var(--ink)"></i>${esc(v2.post_label)}</span>
        </div>` : ""}
      </div>
      <div class="card-body"><div class="steps" id="stepList"></div></div>
      <div class="note">La colonne de droite indique la <b>perte par rapport à l'étape précédente</b>. C'est là que se joue le parcours, pas sur le total.</div>
    </div>

    ${isSplitHere ? renderSplitCards(d, v2, realV2) : ""}`;

  /* etapes */
  const useSplit = isSplitHere;
  const stepsSrc = useSplit ? d.v2steps : steps;
  const maxA = useSplit ? Math.max(...d.v2steps.map(s => Math.max(s.a, s.b))) : first;

  $("#stepList").innerHTML = stepsSrc.map((s, i) => {
    const name = stepLabel(s.step);
    const prev = i > 0 ? stepsSrc[i - 1] : null;
    if (useSplit) {
      const lossA = prev && prev.a ? (prev.a - s.a) / prev.a * 100 : null;
      const lossB = prev && prev.b ? (prev.b - s.b) / prev.b * 100 : null;
      return `<div class="step">
        <div class="step-name">${esc(name)}<em>${esc(String(s.step).replace(/^\s*\d+\s*[.)]\s*/, ""))}</em></div>
        <div class="step-track">
          ${barRow(s.a, maxA, "a", i)}
          ${barRow(s.b, maxA, "b", i)}
        </div>
        <div class="step-val">
          ${fmt(s.b)}
          <em class="${lossB == null ? "none" : ""}">${lossB == null ? "entrée" : "−" + nf1.format(lossB) + " %"}</em>
        </div>
      </div>`;
    }
    const loss = prev && prev.users ? (prev.users - s.users) / prev.users * 100 : null;
    return `<div class="step">
      <div class="step-name">${esc(name)}<em>${esc(String(s.step).replace(/^\s*\d+\s*[.)]\s*/, ""))}</em></div>
      <div class="step-track">${barRow(s.users, maxA, "solo", i)}</div>
      <div class="step-val">
        ${fmt(s.users)}
        <em class="${loss == null ? "none" : ""}">${loss == null ? "entrée" : "−" + nf1.format(loss) + " %"}</em>
      </div>
    </div>`;
  }).join("");
}

function barRow(v, max, tone, i) {
  const w = max ? v / max * 100 : 0;
  const inside = w > 22;
  return `<div class="step-bar ${tone}">
    <i style="width:${w.toFixed(1)}%;animation-delay:${i * 55}ms"></i>
    <span class="${inside ? "" : "out"}" style="left:${inside ? "0" : w.toFixed(1) + "%"}">${fmt(v)}</span>
  </div>`;
}

function renderSplitCards(d, v2, realV2) {
  const title = realV2 ? "Avant et après la bascule V2" : "Première et seconde moitié du mois";
  const sub = realV2
    ? "Le volume d'entrées et le taux de complétion ne bougent pas dans le même sens : c'est la lecture utile."
    : "Ce site n'a pas basculé en V2 sur ce mois. Le découpage est conservé pour rester comparable à l'historique.";
  return `<div class="duo">
    <div class="card">
      <div class="card-head"><div><h2>${title}</h2><p>Entrées de parcours, en moyenne par jour.</p></div></div>
      <div class="card-body">
        <div class="stat-pair">
          <div class="stat-side pre">
            <div class="k">${esc(v2.pre_label || "avant")}</div>
            <div class="v">${fmt1(v2.pre_users_per_day)}</div>
            <div class="d">${v2.pre_days} jours</div>
          </div>
          <div class="stat-arrow"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14m-6-6 6 6-6 6"/></svg></div>
          <div class="stat-side post">
            <div class="k">${esc(v2.post_label || "après")}</div>
            <div class="v">${fmt1(v2.post_users_per_day)}</div>
            <div class="d">${v2.post_days} jours</div>
          </div>
        </div>
        <div style="text-align:center">${delta(v2.post_users_per_day, v2.pre_users_per_day)}</div>
      </div>
      <div class="note">${esc(sub)}</div>
    </div>
    <div class="card">
      <div class="card-head"><div><h2>Taux de complétion</h2><p>Part des entrées qui vont jusqu'à l'estimation.</p></div></div>
      <div class="card-body">
        <div class="stat-pair">
          <div class="stat-side pre">
            <div class="k">${esc(v2.pre_label || "avant")}</div>
            <div class="v">${pct(v2.pre_conversion_pct)}</div>
            <div class="d">${fmt(v2.pre_final_users)} estimations</div>
          </div>
          <div class="stat-arrow"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14m-6-6 6 6-6 6"/></svg></div>
          <div class="stat-side post">
            <div class="k">${esc(v2.post_label || "après")}</div>
            <div class="v">${pct(v2.post_conversion_pct)}</div>
            <div class="d">${fmt(v2.post_final_users)} estimations</div>
          </div>
        </div>
        <div style="text-align:center">${delta(v2.post_conversion_pct, v2.pre_conversion_pct, "pts")}</div>
      </div>
      <div class="note">Moins d'entrées mais une meilleure complétion signifie un parcours qui filtre plus tôt, pas forcément moins performant.</div>
    </div>
  </div>`;
}

/* ============================== rendu ============================== */

function render() {
  clearCharts();
  syncRail();
  renderTabs();
  renderPeriodControl();

  $("#crumb").textContent = view.scope === "overview" ? "Synthèse" : view.site;

  if (view.scope === "overview") { renderOverview(); return; }
  if (view.report === "acquisition") renderAcquisition();
  else if (view.report === "leads") renderLeads();
  else renderParcours();
}

$("#tabs").addEventListener("click", e => {
  const b = e.target.closest("[data-report]");
  if (!b) return;
  view.report = b.dataset.report;
  render();
});

/* ============================== chargement ============================== */

/* etat du pipeline : fraicheur des donnees et anomalies remontees.
   Le silence compte autant que l'echec declare : si le pipeline s'arrete,
   pipeline.json cesse d'etre mis a jour et personne ne verrait rien. */
var ETAT = null;

async function loadEtat() {
  /* l'apercu hors ligne injecte l'etat comme il injecte les donnees */
  if (window.__INLINE_ETAT__) { ETAT = window.__INLINE_ETAT__; return; }
  try {
    const r = await fetch("data/pipeline.json", { cache: "no-store" });
    ETAT = r.ok ? await r.json() : null;
  } catch (e) { ETAT = null; }
}

const HEURES_RETARD = 30;
const HEURES_ARRET = 72;

function santeDonnees() {
  if (!ETAT || !ETAT.derniere_execution) {
    return { niveau: "inconnu",
             texte: "État du rafraîchissement inconnu : le fichier d'état n'est pas publié." };
  }
  const ageH = (Date.now() - new Date(ETAT.derniere_execution).getTime()) / 36e5;
  const quand = new Date(ETAT.derniere_execution).toLocaleString("fr-FR",
    { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });

  if (ageH > HEURES_ARRET) {
    return { niveau: "arret",
             texte: `Pipeline arrêté depuis ${Math.floor(ageH / 24)} jours. Dernier rafraîchissement le ${quand}. Les chiffres affichés ne bougent plus.` };
  }
  if (ageH > HEURES_RETARD) {
    return { niveau: "retard",
             texte: `Rafraîchissement en retard : dernière exécution le ${quand}, il y a ${Math.round(ageH)} heures.` };
  }
  if (ETAT.statut === "echec") {
    return { niveau: "echec",
             texte: (ETAT.blocage || "Un contrôle bloquant a échoué.") + ` Dernier essai le ${quand}.` };
  }
  if (ETAT.statut === "degrade") {
    const n = (ETAT.anomalies || []).length;
    return { niveau: "degrade",
             texte: `${n} anomalie${n > 1 ? "s" : ""} relevée${n > 1 ? "s" : ""} au dernier rafraîchissement, le ${quand}.` };
  }
  return { niveau: "ok", texte: `Données à jour, rafraîchies le ${quand}.` };
}

function bandeauSante() {
  const s = santeDonnees();
  if (s.niveau === "ok") return "";
  const grave = s.niveau === "arret" || s.niveau === "echec";
  const liste = (ETAT && ETAT.anomalies || []).slice(0, 6).map(a =>
    `<li><b>${esc(a.site)}</b> — ${esc(a.controle)}${a.detail ? " : " + esc(a.detail) : ""}</li>`).join("");
  return `<div class="card"><div class="v2-strip${grave ? " grave" : ""}">
    <span class="tagchip">${grave ? "Alerte" : "Attention"}</span>
    <div>
      <p>${esc(s.texte)}</p>
      ${liste ? `<ul class="anos">${liste}</ul>` : ""}
      ${ETAT && ETAT.sites ? (() => {
        const ind = Object.entries(ETAT.sites).filter(([, v]) => v.statut === "indisponible");
        return ind.length ? `<p style="margin-top:6px">Sites non rafraîchis : ${
          ind.map(([k, v]) => `<b>${esc(k)}</b> (${esc(v.motif || "")})`).join(", ")}</p>` : "";
      })() : ""}
    </div>
  </div></div>`;
}

async function load(site) {
  if (DATA[site]) return DATA[site];
  const r = await fetch("data/" + slug(site) + ".json");
  if (!r.ok) throw new Error("Données indisponibles pour " + site);
  DATA[site] = await r.json();
  return DATA[site];
}

async function boot() {
  try {
    const index = await (await fetch("data/index.json")).json();
    SITES = index.sites;
    await Promise.all([loadEtat(), ...SITES.map(load)]);
  } catch (err) {
    document.querySelector(".content").innerHTML =
      `<div class="card"><div class="empty">
        <b>Les données ne se chargent pas</b>
        <p>Vérifiez que le dossier <code>data/</code> est bien publié à côté de cette page.</p>
      </div></div>`;
    return;
  }

  const base = DATA[SITES[0]];
  view.period = defaultPeriod(base);
  view.compare = prevPeriod(base, view.period);

  renderRail();
  wirePeriodControl();
  render();
}

/* les donnees peuvent etre injectees en dur pour une previsualisation hors ligne */
if (window.__INLINE_DATA__) {
  SITES = window.__INLINE_DATA__.sites;
  SITES.forEach(s => { DATA[s] = window.__INLINE_DATA__.data[s]; });
  const base = DATA[SITES[0]];
  view.period = defaultPeriod(base);
  view.compare = prevPeriod(base, view.period);
  renderRail(); wirePeriodControl(); render();
} else {
  boot();
}
