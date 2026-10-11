/**
 * Indexation des pages principales (pipeline/indexation.py -> data repo : indexation.json). Donnée Search Console, sans lead : lisible par
 * les profils complet et limité. GET /api/indexation -> { genere, sites: { "PEUGEOT FR": { propriete, pages: [...] } } }
 */

const { verifySessionFromRequest } = require("./_lib/auth");
const { fail } = require("./_lib/errors");
const { readJson } = require("./_lib/store");

module.exports = async function handler(req, res) {
  const session = verifySessionFromRequest(req);
  if (!session || !session.email) { res.status(401).json({ error: "Non authentifie." }); return; }
  if (req.method !== "GET") { res.status(405).json({ error: "Methode non supportee." }); return; }
  try {
    const { data } = await readJson("indexation.json");
    res.setHeader("cache-control", "no-store");
    res.status(200).json({ genere: (data && data.genere) || null, sites: (data && data.sites) || {} });
  } catch (e) {
    fail(res, 500, "Erreur serveur.", e, "indexation");
  }
};
