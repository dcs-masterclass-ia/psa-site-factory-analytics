/**
 * Alertes proactives GA4 : lecture des alertes calculées par pipeline/alertes.py (data repo : alertes.json) et des seuils réglables
 * (alertes/config.json). Aucun lead back-office dans ces données : lisible aussi par le profil limité ; seuls les profils complets
 * modifient les seuils (pris en compte au prochain passage du pipeline, après le rafraîchissement quotidien).
 *
 *   GET  /api/alertes                          -> { config, alertes, genere, peutEcrire }
 *   POST /api/alertes {action:"save_config", config:{...}}     profil complet seulement
 */

const { verifySessionFromRequest } = require("./_lib/auth");
const { fail } = require("./_lib/errors");
const { readJson, writeJson } = require("./_lib/store");

const FICHIER_ALERTES = "alertes.json";
const FICHIER_CONFIG = "alertes/config.json";
// miroir de CONFIG_DEFAUT dans pipeline/alertes.py (bornes = garde-fous de saisie)
const DEFAUT = { sessionsPct: 25, convPts: 1.5, etapePts: 5, fraicheurJours: 3, volumeMin: 500, notifier: false };
const BORNES = { sessionsPct: [5, 90], convPts: [0.2, 20], etapePts: [1, 30], fraicheurJours: [1, 14], volumeMin: [50, 100000] };

function fusionne(brut) {
  const c = Object.assign({}, DEFAUT);
  const src = brut && typeof brut === "object" ? (brut.config || brut) : {};
  for (const k of Object.keys(DEFAUT)) {
    if (k === "notifier") { if (typeof src[k] === "boolean") c[k] = src[k]; continue; }
    const n = Number(src[k]);
    if (Number.isFinite(n)) c[k] = Math.min(BORNES[k][1], Math.max(BORNES[k][0], n));
  }
  return c;
}

module.exports = async function handler(req, res) {
  const session = verifySessionFromRequest(req);
  if (!session || !session.email) { res.status(401).json({ error: "Non authentifie." }); return; }
  const email = String(session.email).toLowerCase();
  const gere = session.role === "full";
  try {
    if (req.method === "GET") {
      const [{ data: alertes }, { data: cfg }] = await Promise.all([readJson(FICHIER_ALERTES), readJson(FICHIER_CONFIG)]);
      res.setHeader("cache-control", "no-store");
      res.status(200).json({
        config: fusionne(cfg),
        alertes: (alertes && Array.isArray(alertes.alertes)) ? alertes.alertes : [],
        genere: (alertes && alertes.genere) || null,
        peutEcrire: gere,
      });
      return;
    }
    if (req.method !== "POST") { res.status(405).json({ error: "Methode non supportee." }); return; }
    if (!gere) { res.status(403).json({ error: "Acces non autorise pour ce profil." }); return; }
    const body = req.body && typeof req.body === "object" ? req.body : {};
    if (body.action !== "save_config") { res.status(400).json({ error: "Action inconnue." }); return; }
    const config = fusionne(body.config);
    const { sha } = await readJson(FICHIER_CONFIG);
    await writeJson(FICHIER_CONFIG, { updatedAt: Date.now(), modifiePar: email, config }, `chore(alertes): seuils — ${email}`, sha);
    res.status(200).json({ ok: true, config });
  } catch (e) {
    fail(res, 500, "Erreur serveur.", e, "alertes");
  }
};
