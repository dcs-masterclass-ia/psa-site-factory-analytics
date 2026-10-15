/**
 * Préférences d'affichage du compte connecté (page Paramètres) : thème, langue, onglet d'accueil, période et comparaison
 * par défaut, périmètre favori. Un fichier par compte dans le repo de données privé : preferences/<hash e-mail>.json.
 * Aucune donnée métier : lisible et modifiable par tout profil connecté, pour son propre compte uniquement.
 *
 *   GET /api/preferences            -> { prefs }
 *   PUT /api/preferences {prefs}    -> { prefs }   (valide et borne chaque champ)
 */

const crypto = require("crypto");
const { verifySessionFromRequest } = require("./_lib/auth");
const { fail } = require("./_lib/errors");
const { readJson, writeJson } = require("./_lib/store");

const THEMES = ["system", "light", "dark"];
const LANGUES = ["fr", "en"];
const ACCUEILS = ["ga", "sc", "ads", "ps", "tb", "pr", "aaa"];
const PERIODES = ["7", "14", "30", "mois"];
const COMPARAISONS = ["previous", "year", "none"];

function fichier(email) {
  return `preferences/${crypto.createHash("sha256").update(String(email).toLowerCase()).digest("hex").slice(0, 32)}.json`;
}

function nettoie(brut) {
  const p = brut && typeof brut === "object" ? brut : {};
  const out = {};
  if (THEMES.includes(p.theme)) out.theme = p.theme;
  if (LANGUES.includes(p.lang)) out.lang = p.lang;
  if (ACCUEILS.includes(p.accueil)) out.accueil = p.accueil;
  if (PERIODES.includes(p.periode)) out.periode = p.periode;
  if (COMPARAISONS.includes(p.comparaison)) out.comparaison = p.comparaison;
  const per = p.perimetre;
  if (per && typeof per === "object") {
    if (per.mode === "sites" && Array.isArray(per.sites)) {
      const sites = [...new Set(per.sites.map((s) => String(s).slice(0, 80)).filter(Boolean))].slice(0, 120);
      if (sites.length) out.perimetre = { mode: "sites", sites };
    } else if (per.mode === "tous") out.perimetre = { mode: "tous", sites: [] };
  }
  return out;
}

module.exports = async function handler(req, res) {
  const session = verifySessionFromRequest(req);
  if (!session || !session.email) { res.status(401).json({ error: "Non authentifie." }); return; }
  const email = String(session.email).toLowerCase();
  try {
    if (req.method === "GET") {
      const { data } = await readJson(fichier(email));
      res.setHeader("cache-control", "no-store");
      res.status(200).json({ prefs: nettoie(data && data.prefs) });
      return;
    }
    if (req.method === "PUT" || req.method === "POST") {
      const prefs = nettoie(req.body && req.body.prefs);
      const { sha } = await readJson(fichier(email));
      await writeJson(fichier(email), { email, updatedAt: Date.now(), prefs }, "chore(prefs): préférences d'affichage", sha);
      res.setHeader("cache-control", "no-store");
      res.status(200).json({ prefs });
      return;
    }
    res.status(405).json({ error: "Methode non supportee." });
  } catch (e) {
    fail(res, e);
  }
};
