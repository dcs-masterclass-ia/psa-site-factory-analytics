/**
 * Briefs de présentation client : le questionnaire de l'onglet « Présentations »
 * (client, périmètre, période, modules, points ouverts, plan d'actions…).
 * Stockés dans le repo de données PRIVÉ (presentations/briefs.json, via
 * api/_lib/store.js). Profil complet uniquement (l'onglet est masqué aux profils
 * limités et la route n'est pas dans LIMITED_API de middleware.js).
 *
 * Un brief est la « commande » d'une présentation : le générateur de PPTX
 * (à venir) le lira tel quel. Statuts : brouillon -> (demandee -> generee).
 *
 * Routes :
 *   GET  /api/presentations                    -> { briefs: [...], moi }
 *   POST /api/presentations {action:"save", brief}   crée (sans id) ou met à jour
 *   POST /api/presentations {action:"delete", id}    l'auteur seulement
 *
 * Concurrence : lecture-modification-écriture d'un seul fichier, dernier gagnant
 * (même compromis que api/tickets.js).
 */

const crypto = require("crypto");
const { verifySessionFromRequest } = require("./_lib/auth");
const { fail } = require("./_lib/errors");
const { readJson, writeJson } = require("./_lib/store");

const FILE = "presentations/briefs.json";
const MAX_BRIEFS = 200;
const MAX_FILE_BYTES = 900 * 1024;
const MODULES = ["global", "marques", "projets", "trafic_marque", "sources", "cta", "crm", "points_ouverts", "prochaines_etapes"];
const LANGUES = ["fr", "en"];
const STATUTS_ACTION = ["a_faire", "en_cours", "fait", "bloque"];

const txt = (v, max) => String(v == null ? "" : v).replace(/\u0000/g, "").trim().slice(0, max);
const liste = (v, max, f) => (Array.isArray(v) ? v.slice(0, max).map(f).filter(Boolean) : []);

function nettoie(b) {
  b = b && typeof b === "object" ? b : {};
  const annee = parseInt(b.periode && b.periode.annee, 10);
  const trim = parseInt(b.periode && b.periode.trimestre, 10);
  return {
    titre: txt(b.titre, 120),
    client: txt(b.client, 80),
    langue: LANGUES.includes(b.langue) ? b.langue : "fr",
    perimetre: {
      pays: liste(b.perimetre && b.perimetre.pays, 8, p => (/^[A-Za-z]{2}$/.test(String(p)) ? String(p).toUpperCase() : null)),
      marques: liste(b.perimetre && b.perimetre.marques, 24, m => txt(m, 40) || null),
    },
    periode: { annee: annee >= 2020 && annee <= 2100 ? annee : null, trimestre: trim >= 1 && trim <= 4 ? trim : null },
    comparaisons: { qoq: !!(b.comparaisons && b.comparaisons.qoq), yoy: !!(b.comparaisons && b.comparaisons.yoy) },
    modules: liste(b.modules, MODULES.length, m => (MODULES.includes(m) ? m : null)).filter((m, i, a) => a.indexOf(m) === i),
    contact: { nom: txt(b.contact && b.contact.nom, 80), fonction: txt(b.contact && b.contact.fonction, 80), email: txt(b.contact && b.contact.email, 120) },
    pointsOuverts: liste(b.pointsOuverts, 8, p => (p && (txt(p.titre, 100) || txt(p.texte, 600)) ? { titre: txt(p.titre, 100), texte: txt(p.texte, 600) } : null)),
    prochainesEtapes: liste(b.prochainesEtapes, 15, e => (e && txt(e.item, 160)
      ? { item: txt(e.item, 160), responsable: txt(e.responsable, 60), statut: STATUTS_ACTION.includes(e.statut) ? e.statut : "a_faire", echeance: txt(e.echeance, 30) } : null)),
    commentaire: txt(b.commentaire, 2000),
  };
}

function valide(n) {
  if (n.titre.length < 3) return "Donne un titre au brief.";
  if (!n.client) return "Indique le client.";
  if (!n.perimetre.pays.length) return "Choisis au moins un pays.";
  if (!n.periode.annee || !n.periode.trimestre) return "Choisis la période (trimestre et année).";
  if (!n.modules.length) return "Choisis au moins un module.";
  return null;
}

module.exports = async function handler(req, res) {
  const session = verifySessionFromRequest(req);
  if (!session || !session.email) { res.status(401).json({ error: "Non authentifie." }); return; }
  if (session.role !== "full") { res.status(403).json({ error: "Acces non autorise pour ce profil." }); return; }
  const email = String(session.email).toLowerCase();

  try {
    if (req.method === "GET") {
      const { data } = await readJson(FILE);
      const briefs = (data && Array.isArray(data.briefs)) ? data.briefs : [];
      res.setHeader("cache-control", "no-store");
      res.status(200).json({ briefs: briefs.sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0)), moi: email });
      return;
    }
    if (req.method !== "POST") { res.status(405).json({ error: "Methode non supportee." }); return; }

    const body = req.body && typeof req.body === "object" ? req.body : {};
    const { data, sha } = await readJson(FILE);
    let briefs = (data && Array.isArray(data.briefs)) ? data.briefs : [];
    const now = Date.now();

    if (body.action === "save") {
      const n = nettoie(body.brief);
      const err = valide(n);
      if (err) { res.status(400).json({ error: err }); return; }
      const id = txt(body.brief && body.brief.id, 40);
      let brief;
      if (id) {
        const i = briefs.findIndex(x => x.id === id);
        if (i < 0) { res.status(404).json({ error: "Brief introuvable." }); return; }
        brief = Object.assign(briefs[i], n, { updatedAt: now, modifiePar: email });
      } else {
        if (briefs.length >= MAX_BRIEFS) { res.status(507).json({ error: "Trop de briefs stockés." }); return; }
        brief = Object.assign({ id: "B-" + now.toString(36) + crypto.randomBytes(2).toString("hex"), statut: "brouillon", createdAt: now, auteur: email }, n, { updatedAt: now, modifiePar: email });
        briefs.push(brief);
      }
      await ecrit(briefs, sha, `brief ${brief.id} — ${email}`);
      res.status(200).json({ ok: true, brief });
      return;
    }

    if (body.action === "delete") {
      const id = txt(body.id, 40);
      const b = briefs.find(x => x.id === id);
      if (!b) { res.status(404).json({ error: "Brief introuvable." }); return; }
      if (b.auteur !== email) { res.status(403).json({ error: "Seul l'auteur peut supprimer ce brief." }); return; }
      briefs = briefs.filter(x => x.id !== id);
      await ecrit(briefs, sha, `suppression brief ${id}`);
      res.status(200).json({ ok: true });
      return;
    }

    res.status(400).json({ error: "Action inconnue." });
  } catch (e) {
    fail(res, 500, "Erreur serveur.", e, "presentations");
  }
};

async function ecrit(briefs, sha, message) {
  let l = briefs;
  let payload = { updatedAt: Date.now(), briefs: l };
  while (Buffer.byteLength(JSON.stringify(payload)) > MAX_FILE_BYTES && l.length > 1) {
    l = l.slice(0, -1);
    payload = { updatedAt: Date.now(), briefs: l };
  }
  await writeJson(FILE, payload, `chore(presentations): ${message}`, sha);
}
