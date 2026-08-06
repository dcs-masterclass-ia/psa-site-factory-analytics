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
  pos:   CSS.getPropertyValue("--pos").trim()   || "#3ECF8E",
  pink:  CSS.getPropertyValue("--pink").trim()  || "#EC6FAE",
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

/* ============================ plage calendaire (GA4) ============================ */
/* Le sélecteur n'impose plus des mois entiers : n'importe quelle plage de
   jours est acceptable, comme dans GA4. Sessions, reprise et leads sont
   resolus au jour pres — c'est la granularite reelle des donnees.
   Deux choses restent au mois, parce que la donnee elle-meme n'existe qu'a
   ce grain : les dimensions de leads (marque, carburant...) et le funnel.
   Quand la plage choisie couvre un ou plusieurs mois complets, on les
   agrege ; sinon on l'affiche honnetement comme indisponible plutot que
   d'inventer une repartition quotidienne qui n'existe pas. */

const DIMS_KEYS = ["brand", "fuel", "entry", "project", "source", "code"];

const mdToYmd = md => "2026-" + md;
function rangeLabel(debut, fin) {
  const f = md => { const [m, j] = md.split("-"); return `${+j} ${MONTHS[+m - 1]}`; };
  return debut === fin ? f(debut) + " 2026" : `${f(debut)} → ${f(fin)} 2026`;
}
function nbJoursRange(debut, fin) {
  return Math.round((new Date(mdToYmd(fin)) - new Date(mdToYmd(debut))) / 86400000) + 1;
}
function decaleMD(md, n) {
  const dt = new Date(mdToYmd(md));
  dt.setDate(dt.getDate() + n);
  return `${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;
}
function joursDansRange(d, debut, fin) {
  return d.daily.d.map((_, i) => i).filter(i => d.daily.d[i] >= debut && d.daily.d[i] <= fin);
}
function rangeKey(debut, fin) { return `range:${debut}:${fin}`; }
function estRange(p) { return typeof p === "string" && p.startsWith("range:"); }

/* les mois entierement inclus dans [debut, fin] — seuls eux peuvent nourrir
   les dimensions de leads et le funnel, sommables ou affichables tels quels. */
function moisCompletsCouverts(d, debut, fin) {
  return months(d).filter(m => {
    const mm = m.slice(5, 7);
    const jm = d.daily.d.filter(x => x.slice(0, 2) === mm);
    if (!jm.length) return false;
    return debut <= jm[0] && fin >= jm[jm.length - 1];
  });
}

/* materialise une plage libre dans les memes structures que les mois
   existants (d.meta / d.trafficMonth / d.repriseMonth / d.leads / ...),
   pour que stats(), idx() et tous les rendus continuent de fonctionner sans
   distinguer un mois "en dur" d'une plage choisie a la volee. Mis en cache
   sur l'objet du site, recalcule si les bornes changent. */
function materialiseRange(d, debut, fin) {
  const key = rangeKey(debut, fin);
  if (d.meta[key]) return key;

  const idxs = joursDansRange(d, debut, fin);
  const days = nbJoursRange(debut, fin);
  const idxsU = idxs.filter(i => d.daily.u[i] != null);
  const idxsR = idxs.filter(i => d.daily.rep[i] != null);
  // indisponible seulement si RIEN n'est exploitable sur la plage ; un jour
  // manquant au milieu (mois en cours non consolide) ne doit pas effacer les
  // jours qui, eux, ont une vraie mesure — GA4 ne fait pas disparaitre toute
  // la plage pour un seul jour provisoire.
  const sansU = idxsU.length === 0;
  const sansR = idxsR.length === 0;
  const traffic = sansU ? null : idxsU.reduce((a, i) => a + (d.daily.u[i] || 0), 0);
  const reprise = sansR ? null : idxsR.reduce((a, i) => a + (d.daily.rep[i] || 0), 0);
  const joursManquants = idxs.length - idxsU.length;

  const lbd = leadsByDate(d);
  const leadsDaily = idxs.map(i => lbd[d.daily.d[i]] ?? 0);
  const leadsTotal = leadsDaily.reduce((a, b) => a + b, 0);

  d.meta[key] = {
    label: rangeLabel(debut, fin), days,
    partial: joursManquants > 0 || sansU || sansR, provisional: false,
    note: joursManquants > 0
      ? `${joursManquants} jour${joursManquants > 1 ? "s" : ""} sur ${days} n'a/n'ont pas encore de relevé GA4 (mois en cours, données non consolidées). Les totaux ci-dessous portent sur les jours disponibles.`
      : "",
  };
  d.trafficMonth[key] = { sessions: traffic, tdays: days };
  d.repriseMonth[key] = { sessions: reprise, rdays: days };
  d.leads[key] = { total: leadsTotal, daily: leadsDaily };

  const moisComplets = moisCompletsCouverts(d, debut, fin);
  d.leads[key]._dimsDisponibles = moisComplets.length > 0;
  if (moisComplets.length) {
    for (const k of DIMS_KEYS) {
      const acc = new Map();
      for (const m of moisComplets) {
        const src = d.leads[m][k];
        const arr = Array.isArray(src) ? src : Object.entries(src || {});
        for (const [n, v] of arr) acc.set(n, (acc.get(n) || 0) + v);
      }
      d.leads[key][k] = [...acc.entries()];
    }
    // exactement un mois complet, bornes identiques : le funnel de ce mois s'applique
    if (moisComplets.length === 1) {
      const mm = moisComplets[0].slice(5, 7);
      const jm = d.daily.d.filter(x => x.slice(0, 2) === mm);
      if (debut === jm[0] && fin === jm[jm.length - 1] && d.funnelMonth[moisComplets[0]]) {
        d.funnelMonth[key] = d.funnelMonth[moisComplets[0]];
      }
      if (debut === jm[0] && fin === jm[jm.length - 1] && (d.canalQuotidien || {})[moisComplets[0]]) {
        d.canalQuotidien = d.canalQuotidien || {};
        d.canalQuotidien[key] = d.canalQuotidien[moisComplets[0]];
      }
      if (debut === jm[0] && fin === jm[jm.length - 1] && (d.searchMonth || {})[moisComplets[0]]) {
        d.searchMonth = d.searchMonth || {};
        d.searchMonth[key] = d.searchMonth[moisComplets[0]];
      }
    }
    // une anomalie documentee ne s'applique que si la plage = exactement ce mois
    if (moisComplets.length === 1) {
      const mm = moisComplets[0].slice(5, 7);
      const jm = d.daily.d.filter(x => x.slice(0, 2) === mm);
      if (debut === jm[0] && fin === jm[jm.length - 1] && (d.anomaly || {})[moisComplets[0]]) {
        d.anomaly[key] = d.anomaly[moisComplets[0]];
      }
    }
  }
  return key;
}

/* periode precedente de meme duree, pour la comparaison par defaut */
function rangePrecedente(debut, fin) {
  const n = nbJoursRange(debut, fin);
  return { debut: decaleMD(debut, -n), fin: decaleMD(fin, -n) };
}

/* presets, sur le modele de GA4 : bornes calculees a partir du dernier jour
   de donnees disponible pour le site de reference. */
function bornesDonnees(d) {
  return { min: d.daily.d[0], max: d.daily.d[d.daily.d.length - 1] };
}
function presets(d) {
  const { max } = bornesDonnees(d);
  const auj = new Date(mdToYmd(max));
  const back = n => decaleMD(max, -(n - 1));
  const moisCourant = max.slice(0, 2) + "-01";
  const moisPrec = (() => {
    const dt = new Date(mdToYmd(moisCourant)); dt.setDate(0);
    return { debut: `${String(dt.getMonth() + 1).padStart(2, "0")}-01`, fin: `${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}` };
  })();
  return [
    { label:"7 derniers jours", debut:back(7), fin:max },
    { label:"28 derniers jours", debut:back(28), fin:max },
    { label:"Ce mois-ci", debut:moisCourant, fin:max },
    { label:"Mois précédent", debut:moisPrec.debut, fin:moisPrec.fin },
    { label:"Depuis le début", debut:months(d)[0].slice(5,7)+"-01", fin:max },
  ];
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
  if (estRange(p)) {
    const [, debut, fin] = p.split(":");
    return joursDansRange(d, debut, fin);
  }
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
    <polyline points="${line}" fill="none" stroke="${color}" stroke-width="2.4"
      stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>
    <circle cx="${pt[pt.length-1][0].toFixed(1)}" cy="${pt[pt.length-1][1].toFixed(1)}" r="2" fill="${color}"/>
  </svg>`;
}

/* pastille d'icone par defaut : simple point dans un halo pastel — pas
   besoin d'un pictogramme distinct par metrique pour lire la carte. */
function scoreIcon(color) {
  return `<i style="color:${color}"></i>`;
}

/* carte KPI, sur le modele exact des cartes Total sales / Total expenses de
   la reference : libelle en haut, pastille d'icone au coin, gros chiffre,
   ecart en dessous. */
function score(o) {
  const color = o.color || C.eu;
  return `<div class="score">
    <div class="score-top">
      <span class="score-lbl">${esc(o.label)}</span>
      <span class="score-ic" style="background:${color}22;color:${color}">${o.icon || scoreIcon(color)}</span>
    </div>
    <div class="score-val">${o.value}${o.unit ? `<u>${o.unit}</u>` : ""}</div>
    ${o.delta ? `<div class="score-delta">${o.delta}</div>` : ""}
  </div>`;
}

function bar(ratio, tone) {
  const w = Math.max(0, Math.min(1, ratio || 0)) * 100;
  return `<span class="bar ${tone || ""}"><i style="width:${w.toFixed(1)}%"></i></span>`;
}

/* ============================ graphiques ============================ */
/* Fondation refaite entierement : aucun reglage Chart.js par defaut ne
   subsiste. Les regles suivies partout :
   - pas de grille verticale, grille horizontale pointillee tres claire
   - pas de bordure d'axe
   - remplissages en degrade vertical, jamais en aplat
   - points masques au repos, anneau blanc au survol
   - nombres abreges sur l'axe Y (1,2 k plutot que 1200)
   - une seule police, Plus Jakarta Sans, dans tout le graphique
   - curseur vertical au survol pour lier les series a la date          */

const FONT = "Inter";

Chart.defaults.font.family = FONT;
Chart.defaults.font.size = 11;
Chart.defaults.font.weight = 600;
Chart.defaults.color = C.ink4;
Chart.defaults.animation.duration = 520;
Chart.defaults.animation.easing = "easeOutQuart";
Chart.defaults.maintainAspectRatio = false;
if (Chart.defaults.elements && Chart.defaults.elements.point) {
  Chart.defaults.elements.point.hoverBorderWidth = 2.5;
  Chart.defaults.elements.point.hoverBorderColor = "#fff";
}

/* nombres abreges : 12 400 -> 12,4 k */
function abrege(v) {
  const n = Math.abs(v);
  if (n >= 1e6) return nf1.format(v / 1e6) + " M";
  if (n >= 1e4) return nf0.format(Math.round(v / 1e3)) + " k";
  if (n >= 1e3) return nf1.format(v / 1e3) + " k";
  return nf0.format(v);
}

/* degrade vertical sous une courbe, recalcule a chaque redimensionnement */
function fondDegrade(couleur, opacite = .2) {
  return (ctx) => {
    const { ctx: c, chartArea: a } = ctx.chart;
    if (!a) return "transparent";
    const g = c.createLinearGradient(0, a.top, 0, a.bottom);
    g.addColorStop(0, couleur + Math.round(opacite * 255).toString(16).padStart(2, "0"));
    g.addColorStop(1, couleur + "00");
    return g;
  };
}

/* curseur vertical au survol : relie visuellement les series a une date */
const CURSEUR = {
  id: "curseur",
  afterDatasetsDraw(chart) {
    const act = chart.tooltip?.getActiveElements?.() || [];
    if (!act.length) return;
    const x = act[0].element.x, a = chart.chartArea, ctx = chart.ctx;
    ctx.save();
    ctx.beginPath();
    ctx.setLineDash([4, 4]);
    ctx.moveTo(x, a.top); ctx.lineTo(x, a.bottom);
    ctx.strokeStyle = C.ink4; ctx.lineWidth = 1;
    ctx.stroke();
    ctx.restore();
  },
};
Chart.register(CURSEUR);

/* etiquette du jour de bascule V2 : juste un trait pointille + une pastille,
   plus de fond teinte pleine largeur — ca lisait comme une alerte d'erreur
   plutot qu'un simple repere temporel. */
const V2MARK = {
  id: "v2mark",
  beforeDatasetsDraw(chart) {
    const o = chart.options.plugins.v2mark;
    if (!o || o.index == null) return;
    const a = chart.chartArea, ctx = chart.ctx;
    if (!a) return;
    const x = chart.scales.x.getPixelForValue(o.index);
    ctx.save();
    ctx.beginPath();
    ctx.setLineDash([3, 3]);
    ctx.moveTo(x, a.top); ctx.lineTo(x, a.bottom);
    ctx.strokeStyle = C.ink4; ctx.lineWidth = 1.25;
    ctx.stroke();
    ctx.setLineDash([]);
    if (o.label) {
      ctx.font = `800 9.5px ${FONT}`;
      const w = ctx.measureText(o.label).width + 14;
      const lx = Math.min(x + 5, a.right - w);
      ctx.fillStyle = C.tag;
      ctx.beginPath(); ctx.roundRect(lx, a.top + 5, w, 17, 100); ctx.fill();
      ctx.fillStyle = "#0b0b12"; ctx.textBaseline = "middle"; ctx.textAlign = "center";
      ctx.fillText(o.label, lx + w / 2, a.top + 13.5);
    }
    ctx.restore();
  }
};
Chart.register(V2MARK);

/* met en evidence ce qui compte dans une serie temporelle : le pic, annote,
   et la moyenne en ligne de reference. Sans reperes, une courbe de 31 points
   ne dit rien — on ne sait pas si une valeur est haute ou basse. */
const SAILLANT = {
  id: "saillant",
  afterDatasetsDraw(chart) {
    const o = chart.options.plugins.saillant;
    if (!o || !o.actif) return;
    const ds = chart.data.datasets[o.dataset ?? 0];
    const vals = (ds.data || []).map(v => (v == null ? null : +v));
    const reels = vals.filter(v => v != null);
    if (reels.length < 3) return;
    const { ctx, scales: { x, y }, chartArea: a } = chart;
    if (!a) return;

    const moy = reels.reduce((s, v) => s + v, 0) / reels.length;
    ctx.save();

    /* ligne de moyenne : fine, discrete */
    const ym = y.getPixelForValue(moy);
    if (ym > a.top && ym < a.bottom) {
      ctx.beginPath();
      ctx.setLineDash([2, 5]);
      ctx.moveTo(a.left, ym); ctx.lineTo(a.right, ym);
      ctx.strokeStyle = C.line; ctx.lineWidth = 1;
      ctx.stroke();
      ctx.setLineDash([]);
      const txt = `moy. ${abrege(moy)}`;
      ctx.font = `700 9.5px ${FONT}`;
      const w = ctx.measureText(txt).width + 12;
      ctx.fillStyle = "#1b1b28";
      ctx.beginPath(); ctx.roundRect(a.right - w, ym - 8, w, 16, 100); ctx.fill();
      ctx.fillStyle = C.ink3; ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillText(txt, a.right - w / 2, ym);
    }

    /* pic annote : petite carte flottante (libelle + valeur), sur le modele
       des bulles "Income / $190,350" de la reference, plutot qu'une simple
       pastille de chiffre. */
    const max = Math.max(...reels);
    const iMax = vals.indexOf(max);
    if (iMax >= 0) {
      const col = o.couleur || C.eu;
      const px = x.getPixelForValue(iMax), py = y.getPixelForValue(max);

      ctx.beginPath(); ctx.arc(px, py, 4, 0, Math.PI * 2);
      ctx.fillStyle = col; ctx.fill();
      ctx.lineWidth = 2; ctx.strokeStyle = "#0b0b12"; ctx.stroke();

      const lbl = (o.label || "pic").toUpperCase();
      const val = abrege(max);
      ctx.font = `700 8.5px ${FONT}`;
      const wLbl = ctx.measureText(lbl).width;
      ctx.font = `800 13px ${FONT}`;
      const wVal = ctx.measureText(val).width;
      const cw = Math.max(wLbl, wVal) + 24;
      const ch = 46;
      let bx = px - cw / 2; bx = Math.min(Math.max(bx, a.left), a.right - cw);
      let by = py - ch - 14; if (by < a.top) by = py + 14;

      ctx.beginPath(); ctx.roundRect(bx, by, cw, ch, 12);
      ctx.fillStyle = "#1b1b28"; ctx.fill();
      ctx.lineWidth = 1; ctx.strokeStyle = "rgba(255,255,255,.1)"; ctx.stroke();

      ctx.textAlign = "left"; ctx.textBaseline = "alphabetic";
      ctx.fillStyle = C.ink4; ctx.font = `700 8.5px ${FONT}`;
      ctx.fillText(lbl, bx + 12, by + 17);
      ctx.fillStyle = "#f4f4f7"; ctx.font = `800 13px ${FONT}`;
      ctx.fillText(val, bx + 12, by + 35);
      ctx.beginPath(); ctx.arc(bx + cw - 12, by + 27, 3, 0, Math.PI * 2);
      ctx.fillStyle = col; ctx.fill();
    }
    ctx.restore();
  },
};
Chart.register(SAILLANT);

function tooltipCfg(fmtFn) {
  return {
    enabled: true,
    backgroundColor: "#1b1b28",
    borderColor: "rgba(255,255,255,.1)",
    borderWidth: 1,
    padding: { top: 10, bottom: 10, left: 12, right: 14 },
    cornerRadius: 10,
    caretSize: 5,
    caretPadding: 8,
    displayColors: true,
    usePointStyle: true,
    boxWidth: 7, boxHeight: 7, boxPadding: 6,
    titleFont: { family: FONT, weight: "700", size: 11.5 },
    titleColor: "#fff",
    titleMarginBottom: 7,
    bodyFont: { family: FONT, weight: "600", size: 12 },
    bodyColor: "rgba(255,255,255,.9)",
    bodySpacing: 5,
    callbacks: {
      label: c => " " + c.dataset.label + "   " + (fmtFn || fmt)(c.parsed.y ?? c.parsed),
    },
  };
}

/* quasi aucune grille visible, comme la reference : juste assez pour
   raccrocher un point a sa valeur, jamais un quadrillage. */
function axes(showX, tickCount) {
  return {
    x: {
      grid: { display: false },
      border: { display: false },
      ticks: {
        display: showX !== false, maxRotation: 0, autoSkip: true,
        maxTicksLimit: tickCount || 10, padding: 10,
        color: C.ink4, font: { family: FONT, size: 10.5, weight: 600 },
      },
    },
    y: {
      beginAtZero: true,
      border: { display: false },
      grid: { color: C.line2, drawTicks: false, lineWidth: 1 },
      ticks: {
        padding: 12, maxTicksLimit: 5, callback: v => abrege(v),
        color: C.ink4, font: { family: FONT, size: 10.5, weight: 600 },
      },
    },
  };
}

/* libelle chaque point d'une courbe : illisible a 30 points (les jours),
   mais a 4-5 points (les mois) ca se lit d'un coup d'oeil sans survol —
   pas besoin de deviner la valeur exacte au pixel pres. */
function pointLabels(fmtFn) {
  return {
    id: "pointLabels",
    afterDatasetsDraw(chart) {
      const { ctx, scales: { x, y } } = chart;
      ctx.save();
      ctx.textAlign = "center"; ctx.textBaseline = "alphabetic";
      chart.data.datasets.forEach(ds => {
        if (ds.hidden) return;
        ctx.font = `800 11px ${FONT}`;
        ctx.fillStyle = ds.borderColor || C.ink;
        (ds.data || []).forEach((v, i) => {
          if (v == null || !isFinite(v)) return;
          const px = x.getPixelForValue(i), py = y.getPixelForValue(v);
          ctx.fillText((fmtFn || fmt)(v), px, py - 11);
        });
      });
      ctx.restore();
    },
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

const ICON_GRID = `<svg viewBox="0 0 24 24" fill="currentColor"><rect x="3" y="3" width="7.5" height="7.5" rx="2"/><rect x="13.5" y="3" width="7.5" height="7.5" rx="2"/><rect x="3" y="13.5" width="7.5" height="7.5" rx="2"/><rect x="13.5" y="13.5" width="7.5" height="7.5" rx="2"/></svg>`;
const ICON_SPARKLE = `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l1.8 5.2L19 9l-5.2 1.8L12 16l-1.8-5.2L5 9l5.2-1.8L12 2z"/><path d="M19 14l.9 2.6L22.5 17.5l-2.6.9L19 21l-.9-2.6-2.6-.9 2.6-.9L19 14z" opacity=".7"/></svg>`;

/* bande d'icones : un monogramme par marque (2 lettres) + le pays en
   sous-texte, le nom complet et le volume de leads apparaissent au survol
   (voir data-tip) plutot que d'occuper la place en permanence. */
function renderSiteSelect() {
  const lignes = [`<button class="navRow" data-site="__overview__" data-tip="Synthèse — tous les sites">
      <span class="navDot">${ICON_GRID}</span>
      <span class="navName">Tous</span>
    </button>`];

  for (const s of SITES) {
    const mono = s.split(" ")[0].slice(0, 2).toUpperCase();
    const cc = s.split(" ").slice(-1)[0];
    lignes.push(`<button class="navRow" data-site="${esc(s)}" data-tip="${esc(s)}">
      <span class="navDot">${esc(mono)}</span>
      <span class="navName">${esc(cc)}</span>
    </button>`);
  }
  $("#siteNav").innerHTML = lignes.join("");

  $("#siteNav").addEventListener("click", e => {
    const b = e.target.closest(".navRow");
    if (!b) return;
    if (b.dataset.site === "__overview__") selectOverview();
    else selectSite(b.dataset.site);
  });

  /* fleches haut/bas : parcourir les marques sans quitter le clavier */
  document.addEventListener("keydown", e => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    if (/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || "")) return;
    const ordre = ["__overview__", ...SITES];
    const actuel = view.scope === "overview" ? "__overview__" : view.site;
    let i = ordre.indexOf(actuel) + (e.key === "ArrowDown" ? 1 : -1);
    if (i < 0 || i >= ordre.length) return;
    e.preventDefault();
    if (ordre[i] === "__overview__") selectOverview(); else selectSite(ordre[i]);
  });
}

function syncSiteSelect() {
  document.querySelectorAll("#siteNav .navRow").forEach(b => {
    const on = (view.scope === "overview" && b.dataset.site === "__overview__")
            || (view.scope === "site" && b.dataset.site === view.site);
    b.classList.toggle("on", on);
    b.setAttribute("aria-current", on ? "page" : "false");
  });
  /* volume de leads de la periode courante, ajoute a l'infobulle de survol */
  document.querySelectorAll("#siteNav .navRow[data-site]").forEach(b => {
    const s = b.dataset.site, d = DATA[s];
    if (!d) return;
    if (estRange(view.period)) {
      const [, deb, fin] = view.period.split(":");
      materialiseRange(d, deb, fin);
    }
    const st = stats(d, view.period);
    b.dataset.tip = `${s} — ${st ? fmt(st.leads) + " leads" : "—"}`;
  });
}

/* ============================ controle de periode ============================ */

/* ============================ controle de periode (calendaire) ============================ */

/* bornes calendaires de n'importe quelle periode, qu'elle soit une plage
   libre, un mois classique ou le cumul — pour alimenter les champs de date
   quelle que soit la selection en cours. */
function bornesDePeriode(d, p) {
  if (estRange(p)) { const [, debut, fin] = p.split(":"); return { debut, fin }; }
  if (p === "total") {
    const ms = months(d);
    const premierMois = d.daily.d.filter(x => x.slice(0, 2) === ms[0].slice(5, 7));
    const dernierMois = d.daily.d.filter(x => x.slice(0, 2) === ms[ms.length - 1].slice(5, 7));
    return { debut: premierMois[0], fin: dernierMois[dernierMois.length - 1] };
  }
  const jm = d.daily.d.filter(x => x.slice(0, 2) === p.slice(5, 7));
  return { debut: jm[0], fin: jm[jm.length - 1] };
}

function refSite() { return view.scope === "site" ? DATA[view.site] : DATA[SITES[0]]; }
function metaOf(p) { return refSite().meta[p]; }

function renderPeriodControl() {
  const d = refSite();
  const { debut: pDebut, fin: pFin } = bornesDePeriode(d, view.period);

  $("#ctlLabel").textContent = metaOf(view.period).label;
  $("#ctlCmp").textContent = view.compare ? "vs " + metaOf(view.compare).label : "sans comparaison";
  $("#ctlCmp").hidden = false;

  const mm = metaOf(view.period);
  const pf = $("#partialFlag");
  pf.hidden = !mm.partial;
  if (mm.partial) {
    pf.textContent = mm.provisional ? "Mois en cours" : "Données partielles";
    pf.title = mm.note || "Cette période n'est pas complète.";
  }

  $("#rangeDebut").value = mdToYmd(pDebut);
  $("#rangeFin").value = mdToYmd(pFin);
  const b = bornesDonnees(d);
  $("#rangeDebut").min = $("#rangeFin").min = mdToYmd(b.min);
  $("#rangeDebut").max = $("#rangeFin").max = mdToYmd(b.max);

  $("#popPresets").innerHTML = presets(d).map(pr => {
    const k = rangeKey(pr.debut, pr.fin);
    return `<button class="pop-opt ${view.period === k ? "on" : ""}" data-preset="${pr.debut}|${pr.fin}">
      <span>${esc(pr.label)}</span><small>${nbJoursRange(pr.debut, pr.fin)} j</small>
    </button>`;
  }).join("") + `<button class="pop-opt ${view.period === "total" ? "on" : ""}" data-preset="__total__">
    <span>Période cumulée</span><small>${(metaOf("total") || {}).days || ""} j</small>
  </button>`;

  const moisOptions = months(d).filter(m => m !== view.period);
  $("#popCompare").innerHTML =
    `<button class="pop-opt ${!view.compare ? "on" : ""}" data-cmp="">Aucune</button>` +
    `<button class="pop-opt ${view.compare === "__auto__" ? "on" : ""}" data-cmp="__auto__">
      <span>Période précédente</span><small>même durée</small></button>` +
    moisOptions.filter(m => !(metaOf(m) || {}).provisional).map(m =>
      `<button class="pop-opt ${view.compare === m ? "on" : ""}" data-cmp="${m}">
        <span>${esc(metaOf(m).label)}</span><small>${metaOf(m).days} j</small></button>`).join("");
}

function appliquerRange(debut, fin) {
  const d = refSite();
  const key = materialiseRange(d, debut, fin);
  view.period = key;
  view.compare = !view.compare
    ? appliquerComparaisonAuto(d, debut, fin) : view.compare;
  render();
}
function appliquerComparaisonAuto(d, debut, fin) {
  const prev = rangePrecedente(debut, fin);
  const b = bornesDonnees(d);
  if (prev.fin < b.min) return null;      // hors des donnees disponibles
  return materialiseRange(d, prev.debut, prev.fin);
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
  document.addEventListener("click", e => { if (!pop.contains(e.target) && e.target !== btn && !btn.contains(e.target)) close(); });
  document.addEventListener("keydown", e => { if (e.key === "Escape") close(); });

  pop.addEventListener("click", e => {
    const pr = e.target.closest("[data-preset]");
    if (pr) {
      if (pr.dataset.preset === "__total__") {
        view.period = "total";
        const d = refSite();
        view.compare = null;
        close(); render(); return;
      }
      const [debut, fin] = pr.dataset.preset.split("|");
      close(); appliquerRange(debut, fin); return;
    }
    const c = e.target.closest("[data-cmp]");
    if (c) {
      const val = c.dataset.cmp;
      if (val === "__auto__") {
        const d = refSite();
        if (estRange(view.period)) {
          const [, deb, fin] = view.period.split(":");
          view.compare = appliquerComparaisonAuto(d, deb, fin);
        } else {
          view.compare = prevPeriod(d, view.period);
        }
      } else {
        view.compare = val || null;
      }
      close(); render();
    }
  });

  $("#rangeApply").addEventListener("click", () => {
    const deb = $("#rangeDebut").value, fin = $("#rangeFin").value;
    if (!deb || !fin || deb > fin) return;
    close();
    appliquerRange(deb.slice(5), fin.slice(5));
  });
}

/* ============================ navigation ============================ */

/* deux niveaux : le groupe est la source de donnee (GA4 / Recherche...),
   le rapport est la vue a l'interieur. view.report reste la seule source de
   verite — le groupe s'en deduit toujours, jamais stocke a part, pour ne
   jamais desynchroniser les deux. */
const GROUPS = [
  { k:"ga4", t:"GA4", reports:[
    { k:"acquisition", t:"Acquisition" },
    { k:"leads",       t:"Leads" },
    { k:"parcours",    t:"Parcours" },
  ]},
  { k:"recherche", t:"Google Search Console", reports:[
    { k:"recherche", t:"Vue d'ensemble" },
  ]},
];
const REPORTS = GROUPS.flatMap(g => g.reports);
const groupOf = r => (GROUPS.find(g => g.reports.some(x => x.k === r)) || GROUPS[0]).k;

function renderGroups() {
  const nav = $("#groups");
  nav.hidden = view.scope !== "site";
  if (nav.hidden) { nav.innerHTML = ""; return; }
  const cur = groupOf(view.report);
  nav.innerHTML = GROUPS.map(g =>
    `<button class="grouptab ${g.k === cur ? "on" : ""}" data-group="${g.k}">${esc(g.t)}</button>`).join("");
}

function renderTabs() {
  const nav = $("#tabs");
  const g = GROUPS.find(x => x.k === groupOf(view.report)) || GROUPS[0];
  nav.hidden = view.scope !== "site" || g.reports.length < 2;
  if (nav.hidden) { nav.innerHTML = ""; return; }
  nav.innerHTML = g.reports.map(r =>
    `<button class="tab ${r.k === view.report ? "on" : ""}" data-report="${r.k}">${esc(r.t)}</button>`).join("");
}

function selectOverview() {
  view.scope = "overview"; view.site = null;
  render();
}
async function selectSite(site) {
  await load(site);
  view.scope = "site"; view.site = site;
  if (estRange(view.period)) {
    const [, deb, fin] = view.period.split(":");
    materialiseRange(DATA[site], deb, fin);
  } else if (!DATA[site].meta[view.period]) {
    view.period = defaultPeriod(DATA[site]);
  }
  if (view.compare && estRange(view.compare)) {
    const [, deb, fin] = view.compare.split(":");
    materialiseRange(DATA[site], deb, fin);
  } else if (view.compare && !DATA[site].meta[view.compare]) {
    view.compare = prevPeriod(DATA[site], view.period);
  }
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
  if (estRange(p)) {
    const [, deb, fin] = p.split(":");
    SITES.forEach(s => materialiseRange(DATA[s], deb, fin));
  }
  if (cmp && estRange(cmp)) {
    const [, deb, fin] = cmp.split(":");
    SITES.forEach(s => materialiseRange(DATA[s], deb, fin));
  }
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
      ${score({ label:"Sessions site parent", value: sansGA4 ? "—" : fmt(tTraf), color:C.eu,
        delta: cmp && !sansGA4 ? delta(tTraf / days, rTraf / daysRef) : "" })}
      ${score({ label:"Sessions outil de reprise", value: sansGA4 ? "—" : fmt(tNet), color:C.jade,
        delta: cmp && !sansGA4 ? delta(tNet / days, rNet / daysRef) : "" })}
      ${score({ label:"Leads BO / sessions reprise",
        value: sansGA4 ? "—" : pct(tNet ? tLeads / tNet * 100 : null), color:C.tag,
        delta: cmp && rNet && !sansGA4 ? delta(tLeads / tNet * 100, rLeads / rNet * 100, "pts") : "" })}
      ${score({ label:"Leads", value:fmt(tLeads), color:C.pink,
        delta: cmp ? delta(tLeads / days, rLeads / daysRef) : "" })}
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

    <div class="ov-grid">
      <div class="card">
        <div class="card-head">
          <div><h2>Leads par jour, tout le parc</h2><p>${esc(metaOf(p).label)} — total des ${rows.length} sites.</p></div>
          <div class="legend"><span><i style="background:${C.eu}"></i>Total parc</span></div>
        </div>
        <div class="card-body"><div class="plot tall"><canvas id="ovChart"></canvas></div></div>
      </div>

      <div class="card">
        <div class="card-head">
          <div><h2>Classement</h2><p>Par volume de leads sur la période.</p></div>
        </div>
        <div class="card-body">
          <div class="rankList">
            ${[...rows].sort((a, b) => (b.st.leads || 0) - (a.st.leads || 0)).map((r, i) => {
              const maxL = Math.max(...rows.map(x => x.st.leads || 0)) || 1;
              return `<button class="rankRow" data-site="${esc(r.s)}">
                <span class="rankNum">${i + 1}</span>
                <span class="rankBody">
                  <span class="rankTop"><b>${esc(r.s)}</b><em class="num">${fmt(r.st.leads)}</em></span>
                  <span class="bar k"><i style="width:${((r.st.leads || 0) / maxL * 100).toFixed(1)}%"></i></span>
                </span>
              </button>`;
            }).join("")}
          </div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-head">
        <div>
          <h2>Le parc, site par site</h2>
          <p>Chaque ligne suit la même chaîne : le site parent amène du trafic vers l'outil de reprise, qui produit des leads. Cliquez une ligne pour ouvrir le site.</p>
        </div>
      </div>
      <div class="card-body flush"><table class="grid" id="ovTable"></table></div>
      <div class="note">La <b>part vers la reprise</b> mesure combien de sessions du site parent atteignent l'outil. <b>Leads BO / sessions reprise</b> part des leads du back-office, qui les enregistre tous. Ce taux est donc structurellement supérieur au Conversion Rate de Looker, qui ne compte que les leads vus par GA4 — ceux des visiteurs ayant accepté les cookies. Sur OPEL FR, GA4 en a capté 34 % en avril, 30 % en mai et 57 % en juin : cette captation variant d'un mois sur l'autre, le taux de Looker ne se compare pas dans le temps. <b>Complétion parcours</b> est une mesure GA4 en utilisateurs actifs, de l'entrée jusqu'à l'estimation affichée. Les deux colonnes ne mesurent pas la même chose.</div>
    </div>`;

  const maxLeads = Math.max(...rows.map(r => r.st.leads || 0));
  const ligne = r => `
    <tr class="clickable" data-site="${esc(r.s)}">
      <td><span class="cell-name"><b>${esc(r.s)}</b>${r.st.bot ? `<span class="chipBot" title="${r.st.botPct} % du trafic de reprise identifié comme automatisé">robot ${r.st.botPct}\u00a0%</span>` : ""}</span></td>
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
  const rl = $(".rankList");
  if (rl) rl.addEventListener("click", e => {
    const b = e.target.closest(".rankRow");
    if (b) selectSite(b.dataset.site);
  });

  table.addEventListener("click", e => {
    const tr = e.target.closest("tr[data-site]");
    if (tr) selectSite(tr.dataset.site);
  });

  const base = DATA[SITES[0]];
  const labels = idx(base, p).map(i => base.daily.d[i]);
  draw("ovChart", {
    type:"line",
    data:{ labels, datasets:[{ label:"Leads", data:totalJour,
      borderColor:C.eu, fill:true, backgroundColor:fondDegrade(C.eu, .22),
      borderWidth:2.2, tension:.4,
      pointRadius:0, pointHoverRadius:5,
      pointBackgroundColor:C.eu, pointHoverBackgroundColor:C.eu }] },
    options:{
      interaction:{ mode:"index", intersect:false },
      plugins:{ legend:{ display:false }, tooltip:tooltipCfg(), v2mark:{ index:null },
        saillant:{ actif:true, couleur:C.eu, label:"pic leads" } },
      scales:axes(true, 10),
      layout:{ padding:{ top:32, right:4 } }
    }
  });
}

const SERIES = [C.eu, C.jade, C.tag, C.pink, C.pos, C.rust, "#9d8cf9", "#7fa8f7"];

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
      ${score({ label:"Sessions site parent", value:fmt(st.traffic), color:C.eu,
        delta: ref ? delta(st.trafficPD, ref.trafficPD) : "" })}
      ${score({ label:"Sessions outil de reprise", value:fmt(st.reprise), color:C.jade,
        delta: ref ? delta(st.reprisePD, ref.reprisePD) : "" })}
      ${score({ label:"Part vers la reprise", value:pct(st.part), color:C.tag,
        delta: ref ? delta(st.part, ref.part, "pts") : "" })}
      ${score({ label:"Leads BO / sessions reprise", value: st.sansGA4 ? "—" : pct(st.conv), color:C.pink,
        delta: ref && !st.sansGA4 ? delta(st.conv, ref.conv, "pts") : "" })}
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

    ${(d.canalQuotidien || {})[p] ? `<div class="card">
      <div class="card-head">
        <div><h2>Sessions par canal</h2><p>${esc(st.label)} — répartition quotidienne du trafic reprise.</p></div>
      </div>
      <div class="card-body"><div class="plot tall"><canvas id="canalChart"></canvas></div></div>
    </div>` : ""}

    <div class="card">
      <div class="card-head">
        <div><h2>Mois par mois</h2><p>Du site parent au lead, chaque étage de la chaîne — en moyenne par jour, pour rester comparable d'un mois à l'autre.</p></div>
      </div>
      <div class="card-body">
        <div class="twin-wrap">
          <div class="twin-tag"><i style="background:${C.eu}"></i>Sessions site parent / jour</div>
          <div class="plot twin"><canvas id="moisSite"></canvas></div>
          <div class="twin-tag"><i style="background:${C.jade}"></i>Sessions outil de reprise / jour</div>
          <div class="plot twin"><canvas id="moisReprise"></canvas></div>
          <div class="twin-tag"><i style="background:${C.pink}"></i>Leads BO / mois</div>
          <div class="plot twin"><canvas id="moisLeads"></canvas></div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-head">
        <div><h2>Taux, mois par mois</h2><p>Part vers la reprise, conversion et complétion du parcours.</p></div>
        <div class="legend">
          <span><i style="background:${C.eu}"></i>Part vers la reprise</span>
          <span><i style="background:${C.jade}"></i>Leads BO / sessions</span>
          <span><i style="background:${C.tag}"></i>Complétion parcours</span>
        </div>
      </div>
      <div class="card-body"><div class="plot"><canvas id="moisTaux"></canvas></div></div>
      <div class="note">Les courbes ci-dessus sont en <b>moyenne par jour</b> : juillet compte 31 jours, juin 30, comparer les totaux bruts serait trompeur. <b>Leads BO / sessions reprise</b> part des leads du back-office, qui les enregistre tous. Ce taux est donc structurellement supérieur au Conversion Rate de Looker, qui ne compte que les leads vus par GA4 — ceux des visiteurs ayant accepté les cookies. Sur OPEL FR, GA4 en a capté 34 % en avril, 30 % en mai et 57 % en juin : cette captation variant d'un mois sur l'autre, le taux de Looker ne se compare pas dans le temps. <b>Complétion parcours</b> est une mesure GA4 en utilisateurs actifs, de l'entrée jusqu'à l'estimation affichée. Les deux colonnes ne mesurent pas la même chose.</div>
    </div>`;

  /* les deux graphiques partagent l'axe des jours : survoler l'un doit
     positionner l'autre, sinon on lit deux dates differentes cote a cote. */
  const syncJumeaux = (source) => (evt, actifs) => {
    const autre = CHARTS[source === "acqTop" ? "acqBot" : "acqTop"];
    if (!autre) return;
    if (!actifs.length) { autre.setActiveElements([]); autre.tooltip.setActiveElements([], {}); }
    else {
      const i = actifs[0].index;
      autre.setActiveElements([{ datasetIndex: 0, index: i }]);
      autre.tooltip.setActiveElements([{ datasetIndex: 0, index: i }], { x: 0, y: 0 });
    }
    autre.update("none");
  };

  const opts = (showX, markIdx, source) => ({
    interaction:{ mode:"index", intersect:false },
    onHover: syncJumeaux(source),
    plugins:{
      legend:{ display:false }, tooltip:tooltipCfg(),
      v2mark:{ index:markIdx, label: markIdx != null && showX ? "V2" : null }
    },
    scales:axes(showX, 10),
    layout:{ padding:{ top:6, right:4 } }
  });

  draw("acqTop", {
    type:"line",
    data:{ labels, datasets:[{ label:"Sessions site parent", data:su,
      borderColor:C.eu, fill:true, backgroundColor:fondDegrade(C.eu, .18),
      borderWidth:2, tension:.4,
      pointRadius:0, pointHoverRadius:5, pointBackgroundColor:C.eu }] },
    options:opts(false, vi, "acqTop")
  });
  draw("acqBot", {
    type:"line",
    data:{ labels, datasets:[{ label:"Sessions outil de reprise", data:sr,
      borderColor:C.jade, fill:true, backgroundColor:fondDegrade(C.jade, .2),
      borderWidth:2, tension:.4,
      pointRadius:0, pointHoverRadius:5, pointBackgroundColor:C.jade }] },
    options:opts(true, vi, "acqBot")
  });

  /* canal quotidien : aires empilees, uniquement si le pipeline a reussi a
     l'extraire pour ce mois (dimension GA4 non garantie sur toutes les
     proprietes — voir pipeline/channel.py). Rien n'est invente si absent. */
  const canalMois = (d.canalQuotidien || {})[p];
  if (canalMois) {
    const joursCanal = idx(d, p).map(i => d.daily.d[i]);
    const totalCanal = (c) => joursCanal.reduce((s, j) => s + ((canalMois[j] || {})[c] || 0), 0);
    const tous = [...new Set(joursCanal.flatMap(j => Object.keys(canalMois[j] || {})))]
      .sort((a, b) => totalCanal(b) - totalCanal(a));

    /* hierarchie : seuls les 4 premiers canaux sont nommes et colores. Le
       reste est regroupe en une seule bande grise « Autres ». Dix series
       empilees produisent une masse illisible ou rien ne ressort. */
    const MAJEURS = 4;
    const principaux = tous.slice(0, MAJEURS);
    const mineurs = tous.slice(MAJEURS);
    const canaux = [...principaux, ...(mineurs.length ? ["Autres"] : [])];
    const valeur = (c, j) => c === "Autres"
      ? mineurs.reduce((s, m) => s + ((canalMois[j] || {})[m] || 0), 0)
      : ((canalMois[j] || {})[c] || 0);

    /* barres empilees, pas des aires : la reference n'a jamais de masse
       lissee, et une silhouette de montagne a 5 series devient du bruit.
       Un jour = une barre, un canal = un segment. */
    draw("canalChart", {
      type: "bar",
      data: {
        labels: joursCanal,
        datasets: canaux.map((c, i) => {
          const gris = c === "Autres";
          const col = gris ? C.ink4 : SERIES[i % SERIES.length];
          return {
            label: gris ? `Autres (${mineurs.length})` : c,
            data: joursCanal.map(j => valeur(c, j)),
            backgroundColor: col + (gris ? "45" : "e0"),
            hoverBackgroundColor: col,
            borderRadius: 3, borderSkipped: false,
            barPercentage: .82, categoryPercentage: .92,
          };
        }),
      },
      options: {
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: {
            position: "bottom", align: "start",
            labels: {
              boxWidth: 8, boxHeight: 8, usePointStyle: true, pointStyle: "rect",
              padding: 16, color: C.ink3,
              font: { family: FONT, size: 11, weight: 600 },
            },
          },
          tooltip: { ...tooltipCfg(), itemSort: (a, b) => b.parsed.y - a.parsed.y },
        },
        scales: {
          x: { stacked: true, ...axes(true, 10).x },
          y: { stacked: true, ...axes(true).y },
        },
        layout: { padding: { top: 6, right: 4 } },
      },
    });
  }

  /* courbes mois par mois : seuls les mois dont GA4 est releve, en
     moyenne par jour pour rester comparable (juillet 31 j, juin 30). */
  const ms = months(d).filter(m => !provisoire(d, m));
  const statsMois = ms.map(m => stats(d, m));
  const moisLbl = ms.map(m => MONTHS[+m.slice(5, 7) - 1]);
  const onIdx = ms.indexOf(p);

  const miniLine = (canvasId, data, color, fmtFn) => draw(canvasId, {
    type: "line",
    data: { labels: moisLbl, datasets: [{
      data, borderColor: color, backgroundColor: fondDegrade(color, .16),
      borderWidth: 2, tension: .3, fill: true,
      pointRadius: 4, pointHoverRadius: 6, pointBorderWidth: 2,
      pointBorderColor: color,
      pointBackgroundColor: (ctx) => ctx.dataIndex === onIdx ? color : "#15151f",
    }] },
    options: {
      plugins: { legend: { display: false }, tooltip: tooltipCfg(fmtFn) },
      scales: axes(true, 8),
      layout: { padding: { top: 26, right: 10, left: 4 } },
    },
    plugins: [pointLabels(fmtFn)],
  });

  miniLine("moisSite", statsMois.map(s => s.trafficPD), C.eu, fmt);
  miniLine("moisReprise", statsMois.map(s => s.reprisePD), C.jade, fmt);
  miniLine("moisLeads", statsMois.map(s => s.leads), C.pink, fmt);

  draw("moisTaux", {
    type: "line",
    data: {
      labels: moisLbl,
      datasets: [
        { label:"Part vers la reprise", data: statsMois.map(s => s.part),
          borderColor: C.eu, backgroundColor: "transparent", borderWidth: 2.2, tension: .3,
          pointRadius: 4, pointHoverRadius: 6, pointBackgroundColor: C.eu, pointBorderColor: C.eu },
        { label:"Leads BO / sessions", data: statsMois.map(s => s.conv),
          borderColor: C.jade, backgroundColor: "transparent", borderWidth: 2.2, tension: .3,
          pointRadius: 4, pointHoverRadius: 6, pointBackgroundColor: C.jade, pointBorderColor: C.jade },
        { label:"Complétion parcours", data: ms.map(m => ((d.funnelMonth || {})[m] || {}).conversion_pct ?? null),
          borderColor: C.tag, backgroundColor: "transparent", borderWidth: 2.2, tension: .3,
          pointRadius: 4, pointHoverRadius: 6, pointBackgroundColor: C.tag, pointBorderColor: C.tag },
      ],
    },
    options: {
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { display: false }, tooltip: tooltipCfg(v => pct(v)) },
      scales: axes(true, 8),
      layout: { padding: { top: 10, right: 10, left: 4 } },
    },
  });
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

  /* serie de comparaison : la periode choisie en reference, alignee sur le
     meme axe. Elle etait selectionnable mais n'apparaissait nulle part sur
     les graphiques — seulement dans les deltas chiffres. */
  const serieRef = cmp ? (() => {
    const idsRef = idx(d, cmp);
    return idsRef.map(i => lbd[d.daily.d[i]] ?? null);
  })() : null;
  const labelRef = cmp ? (metaOf(cmp) || {}).label : "";

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
      ${score({ label:"Leads", value:fmt(st.leads), color:C.eu,
        delta: ref ? delta(st.leadsPD, ref.leadsPD) : "" })}
      ${score({ label:"Leads BO / sessions reprise", value: st.sansGA4 ? "—" : pct(st.conv), color:C.jade,
        delta: ref && !st.sansGA4 ? delta(st.conv, ref.conv, "pts") : "" })}
      ${score({ label:"Reprises de la marque", value:pct(ownShare), color:C.tag,
        delta: refShare != null ? delta(ownShare, refShare, "pts") : "" })}
      ${score({ label:"Leads pour 1 000 sessions site", value: st.sansGA4 ? "—" : fmt1(st.per1k), color:C.pink,
        delta: ref && !st.sansGA4 ? delta(st.per1k, ref.per1k) : "" })}
    </div>

    <div class="card">
      <div class="card-head">
        <div>
          <h2>Leads par jour</h2>
          <p>Deux vagues superposées : le volume brut du jour, et la moyenne des sept derniers jours qui lisse l'effet week-end.</p>
        </div>
        <div class="legend">
          <span><i style="background:${C.jade}"></i>Leads du jour</span>
          <span><i style="background:${C.eu}"></i>Moyenne 7 jours</span>
        </div>
      </div>
      <div class="card-body"><div class="plot tall"><canvas id="leadsChart"></canvas></div></div>
      ${st.partial ? `<div class="note"><b>Le 31 juillet manque.</b> L'API d'extraction a renvoyé une erreur ce jour-là. Le trafic et le parcours couvrent bien le mois entier.</div>` : ""}
    </div>

    <div class="leads-grid">
      <div class="card">
        <div class="card-head">
          <div><h2>Projet d'achat</h2><p>Répartition des leads par intention déclarée.</p></div>
        </div>
        <div class="card-body"><div class="plot" style="height:250px"><canvas id="projectDonut"></canvas></div></div>
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
        <div class="card-body">
          <div class="donut-row">
            <div class="plot" style="height:230px"><canvas id="dimDonut"></canvas></div>
            <ul class="legend-list" id="dimList"></ul>
          </div>
        </div>
        <div class="note" id="dimNote"></div>
      </div>
    </div>`;

  /* deux vagues superposees plutot que barres + ligne : le brut en aire
     douce et large, la moyenne 7 jours par-dessus en aire plus dense —
     meme esprit que l'aire montagneuse de la reference. */
  draw("leadsChart", {
    data:{ labels, datasets:[
      { type:"line", label:"Leads du jour", data:series,
        borderColor:C.jade, borderWidth:1.6, tension:.42, order:2, fill:true,
        backgroundColor:fondDegrade(C.jade, .32),
        pointRadius:0, pointHoverRadius:4, pointBackgroundColor:C.jade },
      { type:"line", label:"Moyenne 7 jours", data:ma,
        borderColor:C.eu, borderWidth:2.8, tension:.42, order:1, fill:true,
        backgroundColor:fondDegrade(C.eu, .22),
        pointRadius:0, pointHoverRadius:5, pointBackgroundColor:C.eu },
      ...(serieRef ? [{ type:"line", label:labelRef, data:serieRef,
        borderColor:C.ink4, borderWidth:1.8, borderDash:[5,4], tension:.42, order:3, fill:false,
        pointRadius:0, pointHoverRadius:4, pointBackgroundColor:C.ink4 }] : [])
    ]},
    options:{
      interaction:{ mode:"index", intersect:false },
      onClick:(evt, actifs) => {
        /* cliquer un jour restreint la periode a ce seul jour : la facon la
           plus directe d'aller inspecter un pic reperé a l'oeil. */
        if (!actifs.length) return;
        const md = labels[actifs[0].index];
        if (md) appliquerRange(md, md);
      },
      plugins:{
        legend:{ display: !!serieRef, position:"bottom", align:"start",
          labels:{ boxWidth:10, boxHeight:10, usePointStyle:true, pointStyle:"line",
            padding:16, color:C.ink3, font:{ family:FONT, size:11, weight:600 } } },
        tooltip:tooltipCfg(v => fmt1(v)),
        v2mark:{ index:vi, label: vi != null ? "V2" : null },
        saillant:{ actif:true, dataset:1, couleur:C.eu, label:"pic moyenne" }
      },
      scales:axes(true, 10),
      layout:{ padding:{ top:32, right:4 } }
    }
  });

  $("#dimSeg").addEventListener("click", e => {
    const b = e.target.closest("[data-dim]");
    if (!b) return;
    view.dim = b.dataset.dim;
    document.querySelectorAll("#dimSeg button").forEach(x => x.classList.toggle("on", x === b));
    renderDim();
  });

  /* donut projet d'achat : neuf / occasion / aucun projet — meme donnee
     que la dimension "project" du tableau ci-dessous, sur le modele du
     donut new/used/none du Looker Studio du projet */
  const projRaw = pairs((d.leads[p] || {}).project);
  const projMap = { "Véhicule neuf":C.eu, "Véhicule d'occasion":C.jade, "Aucun projet":C.ink4 };
  const projLabels = projRaw.map(([n]) => n);
  const projData = projRaw.map(([, v]) => v);
  const projColors = projLabels.map(n => projMap[n] || C.ink3);
  const projTotal = projData.reduce((a, b) => a + b, 0);
  const CENTRE_DONUT = {
    id: "centreDonut",
    afterDraw(chart) {
      const { ctx, chartArea: a } = chart;
      if (!a) return;
      const cx = (a.left + a.right) / 2, cy = (a.top + a.bottom) / 2;
      ctx.save();
      ctx.textAlign = "center";
      ctx.fillStyle = C.ink;
      ctx.font = `800 26px ${FONT}`;
      ctx.fillText(fmt(projTotal), cx, cy + 2);
      ctx.fillStyle = C.ink4;
      ctx.font = `700 9.5px ${FONT}`;
      ctx.fillText("LEADS", cx, cy + 20);
      ctx.restore();
    },
  };
  draw("projectDonut", {
    type:"doughnut",
    data:{ labels:projLabels, datasets:[{ data:projData, backgroundColor:projColors,
      borderColor:"#fff", borderWidth:4, hoverOffset:8, hoverBorderColor:"#fff",
      spacing:2 }] },
    options:{
      cutout:"74%",
      plugins:{
        legend:{ position:"bottom", align:"center",
          labels:{ boxWidth:8, boxHeight:8, usePointStyle:true, pointStyle:"circle",
            padding:14, color:C.ink3, font:{ family:FONT, size:11, weight:600 } } },
        tooltip:{ ...tooltipCfg(), callbacks:{
          label: c => ` ${c.label}   ${fmt(c.parsed)}  (${pct(c.parsed / projTotal * 100)})`,
        } }
      },
      layout:{ padding:6 }
    },
    plugins:[CENTRE_DONUT]
  });
  renderDim();

  function renderDim() {
    const meta = DIMS.find(x => x.k === view.dim);
    $("#dimHelp").textContent = meta.h;

    if (estRange(p) && (d.leads[p] || {})._dimsDisponibles === false) {
      if (CHARTS.dimDonut) { CHARTS.dimDonut.destroy(); delete CHARTS.dimDonut; }
      $("#dimList").innerHTML = "";
      $("#dimNote").innerHTML =
        `<b>Répartition indisponible sur cette plage.</b> Les dimensions de leads ne sont mesurées que par mois complet. ` +
        `Choisissez un mois entier, ou la période cumulée, pour voir cette répartition.`;
      return;
    }

    const list = pairs((d.leads[p] || {})[view.dim]);
    const covered = list.reduce((a, b) => a + b[1], 0);
    /* la dimension ne couvre pas toujours tous les leads : on montre l'ecart */
    const tot = st.leads || covered;
    const gap = Math.max(0, tot - covered);
    /* 5 parts nommees suffisent pour un donut lisible ; le reste rejoint
       « Autres », comme les classements de la reference. */
    const TOP = 5;
    const shown = list.slice(0, TOP);
    const rest = list.slice(TOP);
    const restSum = rest.reduce((a, b) => a + b[1], 0);
    const tronque = view.dim === "brand" && list.length >= 25;
    const gapLabel = view.dim === "brand" && list.length >= 25 ? "Autres marques" : "Non renseigné";

    const rows = [
      ...shown.map(([n, v], i) => ({ n, v, c: SERIES[i % SERIES.length] })),
      ...(rest.length ? [{ n: `${rest.length} autres`, v: restSum, c: "var(--ink-4)" }] : []),
      ...(gap ? [{ n: gapLabel, v: gap, c: "var(--line)" }] : []),
    ];

    $("#dimList").innerHTML = rows.map(r => `
      <li><i style="background:${r.c}"></i><span>${esc(r.n)}</span><b>${fmt(r.v)}</b><em>${pct(tot ? r.v / tot * 100 : null)}</em></li>
    `).join("");

    draw("dimDonut", {
      type:"doughnut",
      data:{ labels:rows.map(r => r.n), datasets:[{ data:rows.map(r => r.v),
        backgroundColor:rows.map(r => r.c), borderColor:"#fff", borderWidth:4,
        hoverOffset:8, hoverBorderColor:"#fff", spacing:2 }] },
      options:{
        cutout:"70%",
        plugins:{
          legend:{ display:false },
          tooltip:{ ...tooltipCfg(), callbacks:{
            label: c => ` ${c.label}   ${fmt(c.parsed)}  (${pct(tot ? c.parsed / tot * 100 : null)})`,
          } },
        },
        layout:{ padding:6 },
      },
      plugins:[{
        id:"centreDim",
        afterDraw(chart) {
          const { ctx, chartArea: a } = chart;
          if (!a) return;
          const cx = (a.left + a.right) / 2, cy = (a.top + a.bottom) / 2;
          ctx.save();
          ctx.textAlign = "center";
          ctx.fillStyle = C.ink;
          ctx.font = `800 24px ${FONT}`;
          ctx.fillText(fmt(tot), cx, cy + 2);
          ctx.fillStyle = C.ink4;
          ctx.font = `700 9px ${FONT}`;
          ctx.fillText("LEADS", cx, cy + 18);
          ctx.restore();
        },
      }],
    });

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
      ${score({ label:"Entrées de parcours", value:fmt(first), color:C.eu,
        delta: fmRef ? delta(first / d.meta[p].days, fmRef.steps[0].users / d.meta[cmp].days) : "" })}
      ${score({ label:"Estimations terminées", value:fmt(last), color:C.jade,
        delta: fmRef ? delta(last / d.meta[p].days, fmRef.steps[fmRef.steps.length - 1].users / d.meta[cmp].days) : "" })}
      ${score({ label:"Taux de complétion", value:pct(fm.conversion_pct), color:C.tag,
        delta: fmRef ? delta(fm.conversion_pct, fmRef.conversion_pct, "pts") : "" })}
      ${score({ label:"Perte à la première étape", value:pct(drop12), color:C.pink })}
    </div>

    <div class="card">
      <div class="card-head">
        <div><h2>Complétion par étape</h2><p>${esc(fm && metaOf(p) ? metaOf(p).label : "")} — chaque barre en part de la précédente.</p></div>
      </div>
      <div class="card-body">
        <div class="plot funnel"><canvas id="funnelBars"></canvas></div>
      </div>
      <div class="note">Complétion de chaque étape par rapport à l'entrée du parcours, en <b>utilisateurs actifs</b>.</div>
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

    ${isSplitHere ? renderSplitCards(d, v2, realV2) : ""}

    <div class="card">
      <div class="card-head">
        <div><h2>Complétion — évolution mensuelle</h2><p>Un mois par barre, sur tous les mois relevés pour ce site.</p></div>
      </div>
      <div class="card-body"><div class="plot"><canvas id="funnelEvo"></canvas></div></div>
    </div>`;

  /* etapes */
  /* funnel en barres horizontales : la lecture naturelle d'un entonnoir.
     Chaque barre porte son volume et sa part de l'entree, en bout de barre. */
  /* hierarchie du funnel : l'information utile n'est pas le volume de chaque
     etape mais OU l'on perd le plus de monde. L'etape de plus forte chute est
     donc coloree en rouge et porte sa perte ; les autres restent sobres. */
  const pertes = steps.map((s, i) => i === 0 ? 0
    : (steps[i - 1].users ? (steps[i - 1].users - s.users) / steps[i - 1].users : 0));
  const iPire = pertes.indexOf(Math.max(...pertes.slice(1)));

  const LABELS_PLUGIN = {
    id: "barLabels",
    afterDatasetsDraw(chart) {
      const { ctx, scales: { x, y } } = chart;
      const ds = chart.data.datasets[0];
      ctx.save();
      ctx.textBaseline = "middle";
      ds.data.forEach((v, i) => {
        const px = x.getPixelForValue(v) + 10, py = y.getPixelForValue(i);
        ctx.font = `800 12.5px ${FONT}`;
        ctx.fillStyle = C.ink;
        ctx.textAlign = "left";
        ctx.fillText(fmt(v), px, py - 6);
        ctx.font = `600 11px ${FONT}`;
        ctx.fillStyle = i === iPire ? C.rust : C.ink4;
        const suffixe = i === iPire
          ? `−${(pertes[i] * 100).toFixed(0)} % : plus forte perte`
          : (first ? `${(v / first * 100).toFixed(1)} % de l'entrée` : "");
        ctx.fillText(suffixe, px, py + 8);
      });
      ctx.restore();
    },
  };
  draw("funnelBars", {
    type: "bar",
    data: {
      labels: steps.map(s => stepLabel(s.step)),
      datasets: [{
        data: steps.map(s => s.users),
        backgroundColor: (ctx) => {
          const { ctx: c, chartArea: a } = ctx.chart;
          const pire = ctx.dataIndex === iPire;
          if (!a) return pire ? C.rust : C.eu;
          const g = c.createLinearGradient(a.left, 0, a.right, 0);
          g.addColorStop(0, pire ? C.rust : C.eu + "b0");
          g.addColorStop(1, (pire ? C.rust : C.eu) + "55");
          return g;
        },
        borderRadius: 7, borderSkipped: false,
        barPercentage: .74, categoryPercentage: .86,
      }],
    },
    options: {
      indexAxis: "y",
      plugins: { legend: { display: false }, tooltip: tooltipCfg(), curseur: false },
      scales: {
        x: { display: false, beginAtZero: true, grace: "34%" },
        y: {
          grid: { display: false }, border: { display: false },
          ticks: {
            color: (c) => c.index === iPire ? C.rust : C.ink,
            font: (c) => ({ family: FONT, weight: c.index === iPire ? 800 : 700, size: 12 }),
            padding: 6,
          },
        },
      },
      layout: { padding: { right: 160 } },
    },
    plugins: [LABELS_PLUGIN],
  });

  const useSplit = isSplitHere;

  /* evolution mensuelle : un mois = une barre, uniquement les mois qui ont
     un funnel releve pour ce site (JEEP par exemple n'en a pas avant juin). */
  const moisFunnel = months(d).filter(m => d.funnelMonth[m]);
  const evoData = moisFunnel.map(m => d.funnelMonth[m].conversion_pct);
  const EVO_LABELS_PLUGIN = {
    id: "evoLabels",
    afterDatasetsDraw(chart) {
      const { ctx, scales: { x, y } } = chart;
      ctx.save();
      ctx.textAlign = "center";
      evoData.forEach((v, i) => {
        ctx.font = `800 12px ${FONT}`;
        ctx.fillStyle = moisFunnel[i] === p ? C.eu : C.ink3;
        ctx.fillText(v.toFixed(1).replace(".", ",") + " %", x.getPixelForValue(i), y.getPixelForValue(v) - 10);
      });
      ctx.restore();
    },
  };
  draw("funnelEvo", {
    type: "bar",
    data: {
      labels: moisFunnel.map(m => MONTHS[+m.slice(5, 7) - 1]),
      datasets: [{
        data: evoData,
        backgroundColor: moisFunnel.map(m => m === p ? C.eu : C.eu + "2e"),
        hoverBackgroundColor: moisFunnel.map(m => m === p ? C.eu : C.eu + "70"),
        borderRadius: 7, borderSkipped: false,
        barPercentage: .5, categoryPercentage: .78,
      }],
    },
    options: {
      plugins: { legend: { display: false }, tooltip: tooltipCfg(v => pct(v)), curseur: false },
      scales: {
        x: { grid: { display: false }, border: { display: false },
          ticks: { color: C.ink3, font: { family: FONT, weight: 700, size: 11.5 }, padding: 8 } },
        y: { beginAtZero: true, border: { display: false },
          grid: { color: C.line, drawTicks: false, borderDash: [3, 4] },
          ticks: { callback: v => v + " %", maxTicksLimit: 4, padding: 12,
            color: C.ink4, font: { family: FONT, size: 10.5, weight: 600 } } },
      },
      layout: { padding: { top: 26 } },
    },
    plugins: [EVO_LABELS_PLUGIN],
  });
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

/* ------------------------------ recherche ------------------------------ */
/* Search Console, mesuré sur l'outil de reprise uniquement (le site parent
   n'entre pas dans ce périmètre). Deux grains distincts, comme pour le
   funnel : la série quotidienne clics/impressions existe pour n'importe
   quelle période (elle vit dans d.daily, comme le trafic GA4), mais le
   détail — total exact, top requêtes, top pages — n'est reconstruit qu'au
   mois complet ou au cumul, jamais sommé depuis des plages arbitraires. */

function rechTable(id, rows, keyLabel, keyField) {
  const max = rows.length ? Math.max(...rows.map(r => r.clics)) : 1;
  $(id).innerHTML = `
    <thead><tr><th>${esc(keyLabel)}</th><th></th><th>Clics</th><th>Impr.</th><th>CTR</th><th>Position</th></tr></thead>
    <tbody>${rows.length ? rows.map((r, i) => `
      <tr>
        <td><span class="cell-name"><span class="rank">${i + 1}</span><b title="${esc(r[keyField])}">${esc(r[keyField])}</b></span></td>
        <td class="td-bar">${bar(r.clics / max, "k")}</td>
        <td class="num">${fmt(r.clics)}</td>
        <td class="num dim">${fmt(r.impressions)}</td>
        <td class="num dim">${pct(r.ctr)}</td>
        <td class="num dim">${fmt1(r.position)}</td>
      </tr>`).join("") : `<tr><td colspan="6" style="text-align:center;color:var(--ink-4)">Aucune donnée</td></tr>`}
    </tbody>`;
}

function renderRecherche() {
  const d = DATA[view.site], p = view.period, cmp = view.compare;
  const host = panel("panel-recherche");

  const sm = (d.searchMonth || {})[p] || null;
  const smRef = cmp ? (d.searchMonth || {})[cmp] || null : null;

  const ids = idx(d, p);
  const labels = ids.map(i => d.daily.d[i]);
  const clicsJour = ids.map(i => (d.daily.sc || [])[i] ?? null);
  const imprJour = ids.map(i => (d.daily.si || [])[i] ?? null);
  const hasDaily = clicsJour.some(v => v != null);
  const vi = v2Index(d, p);

  if (!sm && !hasDaily) {
    host.innerHTML = `<div class="card"><div class="empty">
      <b>Search Console indisponible sur ${esc((metaOf(p) || {}).label || p)}</b>
      <p>Aucune propriété Search Console n'a été trouvée pour l'outil de reprise de ce site, ou la période n'a pas encore été relevée.</p>
    </div></div>`;
    return;
  }

  const days = (metaOf(p) || {}).days || 1;
  const daysRef = smRef ? ((metaOf(cmp) || {}).days || 1) : null;

  host.innerHTML = `
    <div class="note" style="margin-bottom:16px">Mesuré sur <b>l'outil de reprise uniquement</b> — le site parent n'est pas dans ce périmètre. Indépendant de GA4 : ce sont les clics et impressions dans les résultats de recherche Google.</div>

    ${sm ? `<div class="scores">
      ${score({ label:"Clics", value:fmt(sm.clics), color:C.eu,
        delta: smRef ? delta(sm.clics / days, smRef.clics / daysRef) : "" })}
      ${score({ label:"Impressions", value:fmt(sm.impressions), color:C.jade,
        delta: smRef ? delta(sm.impressions / days, smRef.impressions / daysRef) : "" })}
      ${score({ label:"CTR moyen", value:pct(sm.ctr), color:C.tag,
        delta: smRef ? delta(sm.ctr, smRef.ctr, "pts") : "" })}
      ${score({ label:"Position moyenne", value:fmt1(sm.position), color:C.pink,
        delta: smRef ? delta(-sm.position, -smRef.position, "pts") : "" })}
    </div>` : `<div class="card"><div class="empty">
      <b>Détail indisponible sur ${esc((metaOf(p) || {}).label || p)}</b>
      <p>Le total, les requêtes et les pages ne sont reconstruits qu'au mois complet ou au cumul. Choisissez un mois entier, ou la période cumulée, pour les voir. La série quotidienne ci-dessous reste valable sur n'importe quelle plage.</p>
    </div></div>`}

    ${(d.insights || []).length ? `<div class="card" id="aiInsightsCard">
      <div class="card-head">
        <div><h2 class="ai-title">${ICON_SPARKLE}Insights IA</h2><p>Signaux détectés automatiquement sur les derniers mois de Search Console — jamais un simple écart en pourcentage sur un petit volume.</p></div>
      </div>
      <div class="card-body">
        <div class="insight-list">
          ${d.insights.map(i => `<div class="insight insight--${esc(i.type)}">
            <div class="insight-titre">${esc(i.titre)}</div>
            <div class="insight-detail">${esc(i.detail)}</div>
          </div>`).join("")}
        </div>
      </div>
    </div>` : ""}

    ${hasDaily ? `<div class="card">
      <div class="card-head">
        <div><h2>Clics et impressions par jour</h2><p>Deux échelles très différentes : tracées l'une sous l'autre plutôt que superposées, comme le trafic parent/reprise.</p></div>
      </div>
      <div class="card-body">
        <div class="twin-wrap">
          <div class="twin-tag"><i style="background:${C.eu}"></i>Clics</div>
          <div class="plot twin"><canvas id="rechTop"></canvas></div>
          <div class="twin-tag"><i style="background:${C.jade}"></i>Impressions</div>
          <div class="plot twin"><canvas id="rechBot"></canvas></div>
        </div>
      </div>
      ${vi != null ? `<div class="note"><b>Bande jaune :</b> période postérieure à la bascule V2 du ${esc(frDate(d.v2_date))}.</div>` : ""}
    </div>` : ""}

    ${sm ? `<div class="search-grid">
      <div class="card">
        <div class="card-head"><div><h2>Top requêtes</h2><p>Recherches Google ayant amené des clics vers l'outil de reprise.</p></div></div>
        <div class="card-body flush"><div class="dimScroll"><table class="grid" id="reqTable"></table></div></div>
      </div>
      <div class="card">
        <div class="card-head"><div><h2>Top pages</h2><p>Pages de l'outil de reprise cliquées depuis la recherche.</p></div></div>
        <div class="card-body flush"><div class="dimScroll"><table class="grid" id="pageTable"></table></div></div>
      </div>
    </div>` : ""}`;

  if (hasDaily) {
    const syncJumeaux = (source) => (evt, actifs) => {
      const autre = CHARTS[source === "rechTop" ? "rechBot" : "rechTop"];
      if (!autre) return;
      if (!actifs.length) { autre.setActiveElements([]); autre.tooltip.setActiveElements([], {}); }
      else {
        const i = actifs[0].index;
        autre.setActiveElements([{ datasetIndex: 0, index: i }]);
        autre.tooltip.setActiveElements([{ datasetIndex: 0, index: i }], { x: 0, y: 0 });
      }
      autre.update("none");
    };
    const opts = (showX, source) => ({
      interaction:{ mode:"index", intersect:false },
      onHover: syncJumeaux(source),
      plugins:{ legend:{ display:false }, tooltip:tooltipCfg(), v2mark:{ index:vi, label: vi != null && showX ? "V2" : null } },
      scales:axes(showX, 10),
      layout:{ padding:{ top:6, right:4 } }
    });
    draw("rechTop", {
      type:"line",
      data:{ labels, datasets:[{ label:"Clics", data:clicsJour,
        borderColor:C.eu, fill:true, backgroundColor:fondDegrade(C.eu, .18),
        borderWidth:2, tension:.4, spanGaps:true,
        pointRadius:0, pointHoverRadius:5, pointBackgroundColor:C.eu }] },
      options:opts(false, "rechTop")
    });
    draw("rechBot", {
      type:"line",
      data:{ labels, datasets:[{ label:"Impressions", data:imprJour,
        borderColor:C.jade, fill:true, backgroundColor:fondDegrade(C.jade, .2),
        borderWidth:2, tension:.4, spanGaps:true,
        pointRadius:0, pointHoverRadius:5, pointBackgroundColor:C.jade }] },
      options:opts(true, "rechBot")
    });
  }

  if (sm) {
    rechTable("#reqTable", sm.queries || [], "Requête", "requete");
    rechTable("#pageTable", sm.pages || [], "Page", "page");
  }
}

/* ============================== rendu ============================== */

const REPORT_TITLES = { acquisition:"Acquisition", leads:"Leads", parcours:"Parcours", recherche:"Google Search Console" };

function syncPageHead() {
  const sub = $("#pageSub"), h1 = $("#pageTitle");
  if (view.scope === "overview") {
    sub.textContent = "Site Factory";
    h1.textContent = "Synthèse";
  } else {
    sub.textContent = view.site;
    h1.textContent = REPORT_TITLES[view.report] || view.report;
  }
}

function render() {
  clearCharts();
  syncSiteSelect();
  renderGroups();
  renderTabs();
  renderPeriodControl();
  syncPageHead();

  if (view.scope === "overview") { renderOverview(); return; }
  if (view.report === "acquisition") renderAcquisition();
  else if (view.report === "leads") renderLeads();
  else if (view.report === "parcours") renderParcours();
  else renderRecherche();
}

$("#groups").addEventListener("click", e => {
  const b = e.target.closest("[data-group]");
  if (!b) return;
  const g = GROUPS.find(x => x.k === b.dataset.group);
  if (!g) return;
  view.report = g.reports[0].k;
  render();
});

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

/* bouton Actualiser : appelle une fonction serverless Vercel (api/refresh.js)
   qui detient le jeton GitHub cote serveur. Le jeton n'entre jamais dans ce
   fichier ni dans le navigateur — c'est la seule maniere sure de declencher
   une GitHub Action depuis une page publique. */
/* recharge les donnees depuis le serveur sans perdre la position de
   l'utilisateur (site, rapport, periode) — contrairement a un F5 qui
   reviendrait au mois par defaut. */
async function rafraichirDonnees() {
  const index = await (await fetch("data/index.json", { cache: "no-store" })).json();
  SITES = index.sites;
  await Promise.all([loadEtat(), ...SITES.map(async (s) => {
    const r = await fetch("data/" + slug(s) + ".json", { cache: "no-store" });
    if (r.ok) DATA[s] = await r.json();
  })]);
  render();
}

/* le bouton Assistant IA n'appelle rien en direct : les insights sont deja
   calcules cote pipeline (voir pipeline/insights.py) et vivent dans les
   donnees du site. Cliquer navigue simplement jusqu'a la carte qui les
   affiche, en changeant de rapport/site si besoin. */
function wireAiButton() {
  const btn = $(".ai-btn");
  if (!btn) return;
  btn.addEventListener("click", () => {
    if (view.scope !== "site") return;
    const alreadyThere = view.report === "recherche";
    if (!alreadyThere) { view.report = "recherche"; render(); }
    requestAnimationFrame(() => {
      const carte = $("#aiInsightsCard");
      (carte || $("#panel-recherche"))?.scrollIntoView({ behavior:"smooth", block:"start" });
    });
  });
}

function wireRefreshButton() {
  const btn = $("#refreshBtn"), lbl = $("#refreshLabel");
  if (!btn) return;

  const DUREE_ESTIMEE = 210;   // secondes : pipeline (~150s) + redeploiement Vercel (~40s)
  const DELAI_SONDAGE = 15000; // frequence de verification, en ms
  const SONDAGE_MAX = 40;      // ~10 minutes avant d'abandonner

  async function attendreLesNouvellesDonnees(avant) {
    const debut = Date.now();
    for (let i = 0; i < SONDAGE_MAX; i++) {
      await new Promise(r => setTimeout(r, DELAI_SONDAGE));
      const restant = Math.max(0, Math.round(DUREE_ESTIMEE - (Date.now() - debut) / 1000));
      lbl.textContent = restant > 0 ? `En cours… ~${Math.ceil(restant / 60)} min` : "Vérification…";

      try {
        const r = await fetch("data/pipeline.json", { cache: "no-store" });
        if (!r.ok) continue;
        const etat = await r.json();
        if (etat.derniere_execution && etat.derniere_execution !== avant) {
          await rafraichirDonnees();
          lbl.textContent = etat.statut === "ok" ? "À jour ✓" : "À jour (voir alertes)";
          btn.title = `Rafraîchi à l'instant. Statut du pipeline : ${etat.statut}.`;
          return;
        }
      } catch (e) { /* on retente au prochain tour */ }
    }
    lbl.textContent = "Toujours en cours";
    btn.title = "Le pipeline met plus de temps que prévu. Les données se mettront à jour dès qu'il aura terminé — recharger la page dans quelques minutes.";
  }

  btn.addEventListener("click", async () => {
    if (btn.disabled) return;
    btn.disabled = true;
    btn.classList.add("spin");
    lbl.textContent = "Lancement…";
    try {
      // horodatage actuel, pour detecter le changement plutot que deviner un delai fixe
      const etatAvant = await fetch("data/pipeline.json", { cache: "no-store" })
        .then(r => r.ok ? r.json() : {}).catch(() => ({}));
      const avant = etatAvant.derniere_execution || null;

      const r = await fetch("/api/refresh", { method: "POST" });
      const j = await r.json().catch(() => ({}));

      if (r.status === 200) {
        btn.classList.remove("spin");
        btn.title = "Extraction GA4 puis redéploiement : compter 3 à 4 minutes.";
        await attendreLesNouvellesDonnees(avant);
      } else if (r.status === 429) {
        lbl.textContent = "Déjà en cours";
        btn.title = j.error || "Un rafraîchissement est déjà en cours.";
      } else {
        lbl.textContent = "Échec";
        btn.title = j.error || "Le déclenchement a échoué.";
      }
    } catch (e) {
      lbl.textContent = "Échec";
      btn.title = "Le service de rafraîchissement n'est pas joignable.";
    } finally {
      btn.classList.remove("spin");
      setTimeout(() => { btn.disabled = false; lbl.textContent = "Actualiser"; btn.title = ""; }, 8000);
    }
  });
}

/* ============================== connexion ============================== */
/* Barriere cote client uniquement : ce site est statique, sans serveur pour
   verifier quoi que ce soit. Elle arrete la visite accidentelle ou un lien
   partage sans y penser — pas un acces volontaire de quelqu'un qui lirait le
   code source de la page, ou il verrait cette meme empreinte. */

const AUTH_EMPREINTE = "fd98a33cea628c0865faf7df0f9dabcbbb9f9fad73130bbc9e2fad8a060f7af3";
const AUTH_CLE = "psf_auth_ok";

async function empreinte(texte) {
  const donnees = new TextEncoder().encode(texte);
  const buf = await crypto.subtle.digest("SHA-256", donnees);
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0")).join("");
}

/* localStorage peut etre indisponible (navigation privee stricte, origine
   opaque, iframe restreinte) : on degrade proprement plutot que de planter. */
function stockageLire(cle) {
  try { return localStorage.getItem(cle); } catch (e) { return null; }
}
function stockageEcrire(cle, val) {
  try { localStorage.setItem(cle, val); } catch (e) { /* session non memorisee */ }
}

function afficherApp() {
  $("#loginScreen").remove();
  $("#appRoot").hidden = false;
}

async function verifierConnexion(user, pass) {
  const h = await empreinte(`${user}:${pass}`);
  return h === AUTH_EMPREINTE;
}

function wireLogin() {
  if (stockageLire(AUTH_CLE) === "1") { afficherApp(); return; }

  $("#loginForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const ok = await verifierConnexion($("#loginUser").value.trim(), $("#loginPass").value);
    if (ok) {
      stockageEcrire(AUTH_CLE, "1");
      afficherApp();
    } else {
      $("#loginErr").hidden = false;
      $("#loginPass").value = "";
      $("#loginPass").focus();
    }
  });
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

  renderSiteSelect();
  wirePeriodControl();
  wireRefreshButton();
  wireAiButton();
  render();
}

/* les donnees peuvent etre injectees en dur pour une previsualisation hors ligne */
wireLogin();
if (window.__INLINE_DATA__) {
  SITES = window.__INLINE_DATA__.sites;
  SITES.forEach(s => { DATA[s] = window.__INLINE_DATA__.data[s]; });
  const base = DATA[SITES[0]];
  view.period = defaultPeriod(base);
  view.compare = prevPeriod(base, view.period);
  renderSiteSelect(); wirePeriodControl(); wireRefreshButton(); wireAiButton(); render();
} else {
  boot();
}
