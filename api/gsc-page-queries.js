/**
 * Requêtes Search Console pour UNE page precise (pivot "clic sur une page
 * -> ses requetes", demande du 23/09/2026) -- appel live a l'API Search
 * Console (searchAnalytics.query, dimension "query", filtre dimension
 * "page" = equals), exactement comme gsc-compare.js pour la meme raison :
 * searchMonth stocke les requetes et les pages separement, jamais croisees
 * page x requete, donc rien a deduire des donnees deja stockees sans
 * interpoler (ce que ce projet s'interdit).
 *
 * Reserve a un seul site precis (pas de "Marche entier") : une page n'a de
 * sens que rattachee a une propriete GSC precise.
 */

const { loadSiteRaw } = require("./_lib/data");
const { verifySessionFromRequest } = require("./_lib/auth");
const { accessToken } = require("./_lib/google");

const SCOPE = "https://www.googleapis.com/auth/webmasters.readonly";
const ROW_LIMIT = 50;

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.status(405).json({ error: "Methode non autorisee." });
    return;
  }
  const session = verifySessionFromRequest(req);
  if (!session) {
    res.status(401).json({ error: "Non authentifie." });
    return;
  }

  const { site, page, debut, fin } = req.body || {};
  if (!site || !page || !debut || !fin) {
    res.status(400).json({ error: "site, page, debut et fin sont requis." });
    return;
  }

  const data = loadSiteRaw(site);
  const siteUrl = data && data.gscProperty;
  if (!siteUrl) {
    res.status(200).json({ error: "Aucune propriete Search Console connue pour ce site." });
    return;
  }

  try {
    const token = await accessToken(SCOPE);
    const r = await fetch(
      "https://www.googleapis.com/webmasters/v3/sites/" + encodeURIComponent(siteUrl) + "/searchAnalytics/query",
      {
        method: "POST",
        headers: { authorization: "Bearer " + token, "content-type": "application/json" },
        body: JSON.stringify({
          startDate: debut, endDate: fin, dimensions: ["query"], rowLimit: ROW_LIMIT,
          dimensionFilterGroups: [{ filters: [{ dimension: "page", operator: "equals", expression: page }] }],
        }),
      }
    );
    const json = await r.json();
    if (!r.ok) throw new Error("Search Console : " + (json.error && json.error.message || r.status));
    const lignes = (json.rows || [])
      .map(row => ({ cle: row.keys[0], clics: row.clicks, impressions: row.impressions, ctr: row.ctr * 100, position: row.position }))
      .sort((a, b) => b.clics - a.clics);

    res.status(200).json({ page, siteUrl, periode: { debut, fin }, lignes });
  } catch (e) {
    res.status(500).json({ error: String(e && e.message ? e.message : e) });
  }
};
