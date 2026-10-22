/**
 * Journal de connexion : chaque tentative de connexion (reussie ou refusee) est consignee dans le repo de donnees PRIVE
 * (securite/connexions.json, jamais servi en statique : cf. scripts/fetch-data.sh). Lu par pipeline/securite_veille.py, qui previent sur Teams.
 * Ne bloque JAMAIS la connexion : toute erreur est avalee (message generique dans les journaux, sans donnee).
 */
const store = require("./store");

const CHEMIN = "securite/connexions.json";
const MAX = 2000;

function ipDe(req) {
  const h = req.headers || {};
  return String(h["x-forwarded-for"] || h["x-real-ip"] || "").split(",")[0].trim().replace(/^::ffff:/i, "");
}

async function consigne(req, evt) {
  try {
    const h = req.headers || {};
    const ligne = Object.assign({
      t: Date.now(),
      ip: ipDe(req),
      pays: String(h["x-vercel-ip-country"] || ""),
      ua: String(h["user-agent"] || "").slice(0, 90),
    }, evt);
    const cur = await store.readJson(CHEMIN);
    const evts = ((cur.data && cur.data.evts) || []).concat([ligne]).slice(-MAX);
    await store.writeJson(CHEMIN, { evts }, "chore(securite): journal de connexion", cur.sha);
  } catch (e) {
    console.error("[journal] ecriture impossible");
  }
}

module.exports = { consigne, ipDe, CHEMIN };
