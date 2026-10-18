/**
 * Contrôle des chiffres d'une réponse de KamIA : chaque nombre cité doit (a) figurer tel quel dans les données ou les résultats d'outils de CETTE
 * question, ou (b) se déduire de deux chiffres calculés par les outils (somme, différence, rapport, évolution en %). Sinon il est signalé :
 * l'agent est invité à le recalculer avec les outils ou à le retirer, et, s'il persiste, la réponse affiche honnêtement « chiffres non vérifiés ».
 * Un modèle additionne mal une longue suite (constaté le 18/10/2026 : 1 777 au lieu de 1 908) : seuls les totaux calculés par le serveur font foi.
 */

const SEP = "[ \\u00a0\\u202f]";
const RE_NOMBRE = new RegExp(`(?<![A-Za-zÀ-ÿ_\\-/.,\\d])(\\d{1,3}(?:${SEP}\\d{3})+(?:[.,]\\d+)?|\\d+(?:[.,]\\d+)?)(?![A-Za-zÀ-ÿ_\\d])`, "g");
const UNITES_COMPTAGE = /^\s*(j\b|jours?\b|mois\b|semaines?\b|sites?\b|étapes?\b|agents?\b|fois\b|points? de\b|lignes?\b|canaux\b|marques?\b|pays\b|écrans?\b|premiers?\b|derniers?\b|dernières?\b|premières?\b)/i;

/** Retire dates, années et identifiants qui ne sont pas des chiffres métier. */
function nettoie(t) {
  return String(t || "")
    .replace(/\b\d{4}-\d{2}(-\d{2})?\b/g, " ")
    .replace(/\b\d{1,2}\/\d{1,2}(\/\d{2,4})?\b/g, " ")
    .replace(/\b20(1[5-9]|2\d|3[0-5])\b/g, " ")
    .replace(/\b\d{1,2}h\d{0,2}\b/g, " ");
}

function parse(brut) {
  const compact = brut.replace(new RegExp(SEP, "g"), "");
  const virgule = compact.lastIndexOf(","), point = compact.lastIndexOf(".");
  let s = compact;
  if (virgule >= 0 && point >= 0) s = virgule > point ? compact.replace(/\./g, "").replace(",", ".") : compact.replace(/,/g, "");
  else if (virgule >= 0) s = /^\d{1,3}(,\d{3})+$/.test(compact) ? compact.replace(/,/g, "") : compact.replace(",", ".");
  else if (point >= 0 && /^\d{1,3}(\.\d{3})+$/.test(compact)) s = compact.replace(/\./g, "");
  const v = Number(s);
  const dec = (s.split(".")[1] || "").length;
  return Number.isFinite(v) ? { v, dec } : null;
}

/** [{ brut, v, dec, pct }] : nombres métier d'un texte. */
function nombres(texte, { filtrer = false } = {}) {
  const t = nettoie(texte), out = [];
  RE_NOMBRE.lastIndex = 0;
  let m;
  while ((m = RE_NOMBRE.exec(t))) {
    const p = parse(m[1]);
    if (!p) continue;
    const apres = t.slice(m.index + m[0].length, m.index + m[0].length + 14);
    const pct = /^\s*%/.test(apres);
    if (filtrer) {
      if (!pct && p.dec === 0 && p.v <= 10) continue;                     // « 3 écrans », « 4 agents »
      if (!pct && p.dec === 0 && UNITES_COMPTAGE.test(apres)) continue;    // « 17 jours », « 91 sites »
    }
    out.push({ brut: m[1], ...p, pct });
  }
  return out;
}

const ok = (c, n) => Number.isFinite(c) && Math.abs(c - n.v) <= 0.5 * Math.pow(10, -n.dec) + 1e-9 + (n.dec === 0 ? 0 : 0);

/**
 * preuves = { brut: [texte...], calcule: [texte...] } : « brut » = données lues par les outils (correspondance exacte seulement),
 * « calcule » = résultats d'outils et réponses d'agents (correspondance exacte, ou déduction par paire).
 * -> liste des nombres de la réponse non vérifiés (chaînes telles qu'écrites).
 */
function nonVerifies(reponse, question, preuves) {
  const exact = [], base = [];
  for (const t of (preuves.brut || [])) nombres(t).forEach(n => exact.push(n.v));
  for (const t of (preuves.calcule || [])) nombres(t).forEach(n => { exact.push(n.v); base.push(n.v); });
  nombres(question || "").forEach(n => { exact.push(n.v); base.push(n.v); });
  const set = new Set(exact.map(v => Math.round(v * 1e6)));
  const pool = [...new Set(base)].slice(0, 400);
  const candidats = n => {
    if (set.has(Math.round(n.v * 1e6))) return true;
    for (const e of exact) if (ok(e, n)) return true;                      // arrondi d'une valeur lue
    for (let i = 0; i < pool.length; i++) {
      const a = pool[i];
      for (let j = 0; j < pool.length; j++) {
        const b = pool[j];
        if (i < j && (ok(a + b, n) || ok(Math.abs(a - b), n))) return true;
        if (i !== j && b !== 0) { const r = a / b; if (ok(r * 100, n) || ok((r - 1) * 100, n) || ok(r, n) || ok((1 - r) * 100, n)) return true; }
      }
    }
    return false;
  };
  const vus = new Set(), inconnus = [];
  for (const n of nombres(reponse, { filtrer: true })) {
    const cle = n.v + (n.pct ? "%" : "");
    if (vus.has(cle)) continue;
    vus.add(cle);
    if (!candidats(n)) inconnus.push(n.brut + (n.pct ? " %" : ""));
  }
  return inconnus;
}

module.exports = { nombres, nonVerifies };
