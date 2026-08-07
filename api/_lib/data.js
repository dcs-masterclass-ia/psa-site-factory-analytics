/**
 * Lecture des data/<slug>.json deja produits par le pipeline -- l'assistant
 * ne fait aucun appel GA4/GSC supplementaire, il lit ce que le dashboard
 * affiche deja.
 */

const fs = require("fs");
const path = require("path");

function siteSlug(nom) {
  return String(nom).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

function listSites() {
  try {
    const idx = JSON.parse(fs.readFileSync(path.join(process.cwd(), "data", "index.json"), "utf8"));
    return idx.sites || [];
  } catch (e) {
    return [];
  }
}

function loadSiteRaw(nom) {
  const p = path.join(process.cwd(), "data", siteSlug(nom) + ".json");
  if (!fs.existsSync(p)) return null;
  try {
    return JSON.parse(fs.readFileSync(p, "utf8"));
  } catch (e) {
    return null;
  }
}

// Retire/allege les champs les plus volumineux ou les moins utiles a une
// synthese narrative (canalQuotidien = detail jour par jour par canal,
// trop volumineux ; requetes/pages GSC tronquees au top 5) pour garder un
// contexte raisonnable en tokens tout en gardant tout le reste (leads,
// daily, funnelMonth, v2/v2Weekly, insights...).
function compactSite(raw) {
  if (!raw) return null;
  const { canalQuotidien, ...rest } = raw;
  const searchMonth = {};
  for (const [mois, bloc] of Object.entries(rest.searchMonth || {})) {
    searchMonth[mois] = {
      ...bloc,
      queries: (bloc.queries || []).slice(0, 5),
      pages: (bloc.pages || []).slice(0, 5),
    };
  }
  return { ...rest, searchMonth };
}

function loadSite(nom) {
  return compactSite(loadSiteRaw(nom));
}

module.exports = { siteSlug, listSites, loadSite, loadSiteRaw, compactSite };
