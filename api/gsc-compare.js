/**
 * Tableau Search Console dynamique (pages ou requetes) sur une plage de
 * dates arbitraire, compare a la meme duree juste avant -- demande du
 * 10/08/2026 ("je selectionne du 1er au 10 juillet, le tableau m'affiche
 * la difference par rapport au 20-30 juin").
 *
 * Interroge l'API Search Console EN DIRECT (pas le pipeline batch) : la
 * donnee stockee dans data/<site>.json est mensuelle (searchMonth), sans
 * resolution jour -- une comparaison sur des dates arbitraires ne peut
 * pas en etre deduite sans interpoler, ce que ce projet s'interdit
 * (jamais de chiffre invente). D'ou cet appel a la demande plutot qu'un
 * nouveau stockage quotidien (aurait fait exploser la taille des
 * data/*.json pour un usage occasionnel).
 *
 * Reutilise le compte de service DEJA autorise sur Search Console par le
 * pipeline (meme cle que GA4_SERVICE_ACCOUNT cote GitHub Actions, deposee
 * ici sous GSC_SERVICE_ACCOUNT) -- voir api/_lib/google.js.
 */

const { loadSiteRaw } = require("./_lib/data");
const { verifySessionFromRequest } = require("./_lib/auth");
const { accessToken } = require("./_lib/google");

const SCOPE = "https://www.googleapis.com/auth/webmasters.readonly";
const ROW_LIMIT = 50;

function joursEntre(debut, fin) {
  return Math.round((new Date(fin + "T00:00:00Z") - new Date(debut + "T00:00:00Z")) / 86400000) + 1;
}
function decale(iso, n) {
  const d = new Date(iso + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

async function interroger(siteUrl, token, dimension, debut, fin) {
  const r = await fetch(
    "https://www.googleapis.com/webmasters/v3/sites/" + encodeURIComponent(siteUrl) + "/searchAnalytics/query",
    {
      method: "POST",
      headers: { authorization: "Bearer " + token, "content-type": "application/json" },
      body: JSON.stringify({ startDate: debut, endDate: fin, dimensions: [dimension], rowLimit: ROW_LIMIT }),
    }
  );
  const json = await r.json();
  if (!r.ok) throw new Error("Search Console : " + (json.error && json.error.message || r.status));
  return json.rows || [];
}

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

  const { site, debut, fin, dimension } = req.body || {};
  if (!site || !debut || !fin) {
    res.status(400).json({ error: "site, debut et fin sont requis." });
    return;
  }
  const dim = dimension === "query" ? "query" : "page";

  const data = loadSiteRaw(site);
  const siteUrl = data && data.gscProperty;
  if (!siteUrl) {
    res.status(200).json({ error: "Aucune propriete Search Console connue pour ce site (pas encore decouverte par le pipeline)." });
    return;
  }

  const jours = joursEntre(debut, fin);
  const prevFin = decale(debut, -1);
  const prevDebut = decale(prevFin, -(jours - 1));

  try {
    const token = await accessToken(SCOPE);
    const [actuel, precedent] = await Promise.all([
      interroger(siteUrl, token, dim, debut, fin),
      interroger(siteUrl, token, dim, prevDebut, prevFin),
    ]);

    const prevMap = new Map(precedent.map(r => [r.keys[0], r]));
    const lignes = actuel.map(r => {
      const cle = r.keys[0];
      const p = prevMap.get(cle);
      return {
        cle,
        clics: r.clicks, impressions: r.impressions, ctr: r.ctr * 100, position: r.position,
        clicsPrec: p ? p.clicks : null, impressionsPrec: p ? p.impressions : null,
        positionPrec: p ? p.position : null,
        clicsDeltaPct: p && p.clicks ? (r.clicks - p.clicks) / p.clicks * 100 : null,
      };
    }).sort((a, b) => b.clics - a.clics);

    res.status(200).json({
      dimension: dim, siteUrl,
      periode: { debut, fin, jours },
      periodePrecedente: { debut: prevDebut, fin: prevFin },
      lignes,
    });
  } catch (e) {
    res.status(500).json({ error: String(e && e.message ? e.message : e) });
  }
};
