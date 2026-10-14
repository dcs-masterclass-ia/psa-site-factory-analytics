/**
 * Leads heure par heure (profil complet seulement : leads back-office).
 * Lit leads_horaire.json du repo de données, tenu à jour toutes les 30 minutes par .github/workflows/leads-horaire.yml
 * à partir du suivi des leads du monitor (créneaux de 30 min, aujourd'hui / hier / moyenne des 4 mêmes jours).
 *
 *   GET /api/leads-horaire -> { genere, horaire: { date, creneauxEcoules, flotte:{aujourdhui,hier,baseline}, sites:{...} } | null }
 */

const { verifySessionFromRequest } = require("./_lib/auth");
const { fail } = require("./_lib/errors");
const { readJson } = require("./_lib/store");

module.exports = async function handler(req, res) {
  const session = verifySessionFromRequest(req);
  if (!session || !session.email) { res.status(401).json({ error: "Non authentifie." }); return; }
  if (session.role !== "full") { res.status(403).json({ error: "Acces non autorise pour ce profil." }); return; }
  if (req.method !== "GET") { res.status(405).json({ error: "Methode non supportee." }); return; }
  try {
    const { data } = await readJson("leads_horaire.json");
    res.setHeader("cache-control", "no-store");
    res.status(200).json({ genere: (data && data.genere) || null, horaire: (data && data.horaire) || null });
  } catch (e) {
    fail(res, e);
  }
};
