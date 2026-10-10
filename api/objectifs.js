/**
 * Objectifs annuels de leads par site (profil complet uniquement : ce sont des leads back-office).
 * Stockés dans le repo de données PRIVÉ (objectifs/objectifs.json, via api/_lib/store.js).
 *
 *   { annees: { "2026": { "PEUGEOT FR": 123000, ... } }, updatedAt }
 *
 * Routes :
 *   GET  /api/objectifs                                  -> { annees, moi }
 *   POST /api/objectifs {action:"save", annee, cibles:{site: n|null}}   fusionne ; null / 0 supprime la cible du site
 */

const { verifySessionFromRequest } = require("./_lib/auth");
const { fail } = require("./_lib/errors");
const { readJson, writeJson } = require("./_lib/store");

const FILE = "objectifs/objectifs.json";
const txt = (v, max) => String(v == null ? "" : v).replace(/\u0000/g, "").trim().slice(0, max);

module.exports = async function handler(req, res) {
  const session = verifySessionFromRequest(req);
  if (!session || !session.email) { res.status(401).json({ error: "Non authentifie." }); return; }
  if (session.role !== "full") { res.status(403).json({ error: "Acces non autorise pour ce profil." }); return; }
  const email = String(session.email).toLowerCase();

  try {
    const { data, sha } = await readJson(FILE);
    const annees = (data && data.annees && typeof data.annees === "object") ? data.annees : {};
    if (req.method === "GET") {
      res.setHeader("cache-control", "no-store");
      res.status(200).json({ annees, moi: email });
      return;
    }
    if (req.method !== "POST") { res.status(405).json({ error: "Methode non supportee." }); return; }
    const body = req.body && typeof req.body === "object" ? req.body : {};
    if (body.action !== "save") { res.status(400).json({ error: "Action inconnue." }); return; }
    const annee = txt(body.annee, 4);
    if (!/^20\d{2}$/.test(annee)) { res.status(400).json({ error: "Année invalide." }); return; }
    const cibles = body.cibles && typeof body.cibles === "object" ? body.cibles : {};
    const cur = Object.assign({}, annees[annee] || {});
    let n = 0;
    for (const [site, v] of Object.entries(cibles)) {
      const nom = txt(site, 60);
      if (!nom) continue;
      const nb = Math.round(Number(v));
      if (v == null || !Number.isFinite(nb) || nb <= 0) delete cur[nom];
      else if (nb <= 100000000) cur[nom] = nb;
      if (++n > 500) break;
    }
    annees[annee] = cur;
    const nouveau = { updatedAt: Date.now(), modifiePar: email, annees };
    await writeJson(FILE, nouveau, `chore(objectifs): ${annee} — ${email}`, sha);
    res.status(200).json({ ok: true, annees });
  } catch (e) {
    fail(res, 500, "Erreur serveur.", e, "objectifs");
  }
};
