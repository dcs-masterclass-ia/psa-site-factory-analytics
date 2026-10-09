/**
 * Vue "limitee" des fichiers data/*.json (profils GA4 / Search Console /
 * PageSpeed uniquement) : retire tout ce qui vient du back-office leads.
 * Echoue ferme : si une cle "leads" subsiste apres nettoyage, on leve une
 * erreur plutot que de servir la donnee.
 */

const LEADS_RE = /\bleads?\b/i;
const V2_KEYS = ["v2", "v2Weekly", "v2channels", "v2steps"]; // v2_date reste : simple date de bascule, sert de repere sur la courbe de conversion

function stripLeads(data) {
  if (!data || typeof data !== "object" || Array.isArray(data)) return data;
  delete data.leads;
  for (const k of V2_KEYS) delete data[k];
  const ins = data.insights;
  if (ins && typeof ins === "object") {
    delete ins.leads;
    for (const cat of Object.keys(ins)) {
      if (Array.isArray(ins[cat])) ins[cat] = ins[cat].filter(it => !LEADS_RE.test(JSON.stringify(it)));
    }
  }
  if (/"leads?(Daily|PerDay|ParDevice|Total)?"\s*:/i.test(JSON.stringify(data))) {
    throw new Error("stripLeads : cle leads residuelle");
  }
  return data;
}

module.exports = { stripLeads };
