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
 * Périodicité : mois | trimestre | semestre | annee ; periode = { type, annee, indice }
 * (indice : 1-12, 1-4, 1-2, null). Les anciens briefs { annee, trimestre } restent lisibles.
 *
 * Modèles (presentations/templates.json) : la configuration réutilisable d'un brief
 * (client, langue, périodicité, périmètre, comparaisons, modules, contact, commentaire),
 * sans la période ni les points ouverts / prochaines étapes (propres à chaque édition).
 *
 * Routes :
 *   GET  /api/presentations                          -> { briefs, templates, moi }
 *   POST /api/presentations {action:"save", brief}   crée (sans id) ou met à jour
 *   POST /api/presentations {action:"delete", id}    l'auteur seulement
 *   POST /api/presentations {action:"save_template", template:{id?, nom, description, config}}
 *   POST /api/presentations {action:"delete_template", id}   l'auteur seulement
 *
 * Concurrence : lecture-modification-écriture d'un seul fichier, dernier gagnant
 * (même compromis que api/tickets.js).
 */

const crypto = require("crypto");
const { verifySessionFromRequest } = require("./_lib/auth");
const { fail } = require("./_lib/errors");
const { readJson, writeJson } = require("./_lib/store");

const FILE = "presentations/briefs.json";
const FILE_TPL = "presentations/templates.json";
const MAX_TEMPLATES = 60;
const TYPES_PERIODE = ["mois", "trimestre", "semestre", "annee"];
const MAX_INDICE = { mois: 12, trimestre: 4, semestre: 2, annee: 0 };
const MAX_BRIEFS = 200;
const MAX_FILE_BYTES = 900 * 1024;
const MODULES = ["global", "marques", "projets", "trafic_marque", "sources", "cta", "crm", "points_ouverts", "prochaines_etapes"];
const LANGUES = ["fr", "en"];
const STATUTS_ACTION = ["a_faire", "en_cours", "fait", "bloque"];

const txt = (v, max) => String(v == null ? "" : v).replace(/\u0000/g, "").trim().slice(0, max);
const liste = (v, max, f) => (Array.isArray(v) ? v.slice(0, max).map(f).filter(Boolean) : []);

function nettoiePeriode(p) {
  p = p && typeof p === "object" ? p : {};
  // ancien format : { annee, trimestre }
  const type = TYPES_PERIODE.includes(p.type) ? p.type : (p.trimestre != null ? "trimestre" : null);
  const annee = parseInt(p.annee, 10);
  const brut = parseInt(p.indice != null ? p.indice : p.trimestre, 10);
  const max = type ? MAX_INDICE[type] : 0;
  return {
    type,
    annee: annee >= 2020 && annee <= 2100 ? annee : null,
    indice: type && max > 0 && brut >= 1 && brut <= max ? brut : null,
  };
}

function nettoieCommun(b) {
  b = b && typeof b === "object" ? b : {};
  const c = b.comparaisons || {};
  return {
    client: txt(b.client, 80),
    langue: LANGUES.includes(b.langue) ? b.langue : "fr",
    perimetre: {
      pays: liste(b.perimetre && b.perimetre.pays, 8, p => (/^[A-Za-z]{2}$/.test(String(p)) ? String(p).toUpperCase() : null)),
      marques: liste(b.perimetre && b.perimetre.marques, 24, m => txt(m, 40) || null),
    },
    comparaisons: { precedente: !!(c.precedente != null ? c.precedente : c.qoq), n1: !!(c.n1 != null ? c.n1 : c.yoy) },
    modules: liste(b.modules, MODULES.length, m => (MODULES.includes(m) ? m : null)).filter((m, i, a) => a.indexOf(m) === i),
    contact: { nom: txt(b.contact && b.contact.nom, 80), fonction: txt(b.contact && b.contact.fonction, 80), email: txt(b.contact && b.contact.email, 120) },
    commentaire: txt(b.commentaire, 2000),
  };
}

function nettoie(b) {
  b = b && typeof b === "object" ? b : {};
  return Object.assign(nettoieCommun(b), {
    titre: txt(b.titre, 120),
    periode: nettoiePeriode(b.periode),
    pointsOuverts: liste(b.pointsOuverts, 8, p => (p && (txt(p.titre, 100) || txt(p.texte, 600)) ? { titre: txt(p.titre, 100), texte: txt(p.texte, 600) } : null)),
    prochainesEtapes: liste(b.prochainesEtapes, 15, e => (e && txt(e.item, 160)
      ? { item: txt(e.item, 160), responsable: txt(e.responsable, 60), statut: STATUTS_ACTION.includes(e.statut) ? e.statut : "a_faire", echeance: txt(e.echeance, 30) } : null)),
  });
}

function nettoieModele(t) {
  t = t && typeof t === "object" ? t : {};
  const cfg = t.config && typeof t.config === "object" ? t.config : {};
  return {
    nom: txt(t.nom, 80),
    description: txt(t.description, 300),
    config: Object.assign(nettoieCommun(cfg), { periodicite: TYPES_PERIODE.includes(cfg.periodicite) ? cfg.periodicite : "trimestre" }),
  };
}

function valide(n) {
  if (n.titre.length < 3) return "Donne un titre au brief.";
  if (!n.client) return "Indique le client.";
  if (!n.perimetre.pays.length) return "Choisis au moins un pays.";
  if (!n.periode.type || !n.periode.annee || (n.periode.type !== "annee" && !n.periode.indice)) return "Choisis la période.";
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
      const [{ data }, { data: dt }] = await Promise.all([readJson(FILE), readJson(FILE_TPL)]);
      const briefs = (data && Array.isArray(data.briefs)) ? data.briefs : [];
      const templates = (dt && Array.isArray(dt.templates)) ? dt.templates : [];
      res.setHeader("cache-control", "no-store");
      res.status(200).json({ briefs: briefs.sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0)), templates: templates.sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0)), moi: email });
      return;
    }
    if (req.method !== "POST") { res.status(405).json({ error: "Methode non supportee." }); return; }

    const body = req.body && typeof req.body === "object" ? req.body : {};

    if (body.action === "save_template" || body.action === "delete_template") {
      const { data: dt, sha: shaT } = await readJson(FILE_TPL);
      let tpls = (dt && Array.isArray(dt.templates)) ? dt.templates : [];
      const nowT = Date.now();
      if (body.action === "save_template") {
        const n = nettoieModele(body.template);
        if (n.nom.length < 3) { res.status(400).json({ error: "Donne un nom au modèle." }); return; }
        if (!n.config.client) { res.status(400).json({ error: "Indique le client du modèle." }); return; }
        if (!n.config.perimetre.pays.length) { res.status(400).json({ error: "Choisis au moins un pays." }); return; }
        if (!n.config.modules.length) { res.status(400).json({ error: "Choisis au moins un module." }); return; }
        const id = txt(body.template && body.template.id, 40);
        let tpl;
        if (id) {
          const i = tpls.findIndex(x => x.id === id);
          if (i < 0) { res.status(404).json({ error: "Modèle introuvable." }); return; }
          tpl = Object.assign(tpls[i], n, { updatedAt: nowT, modifiePar: email });
        } else {
          if (tpls.length >= MAX_TEMPLATES) { res.status(507).json({ error: "Trop de modèles stockés." }); return; }
          tpl = Object.assign({ id: "M-" + nowT.toString(36) + crypto.randomBytes(2).toString("hex"), createdAt: nowT, auteur: email }, n, { updatedAt: nowT, modifiePar: email });
          tpls.push(tpl);
        }
        await writeJson(FILE_TPL, { updatedAt: nowT, templates: tpls }, `chore(presentations): modèle ${tpl.id} — ${email}`, shaT);
        res.status(200).json({ ok: true, template: tpl });
        return;
      }
      const idT = txt(body.id, 40);
      const t = tpls.find(x => x.id === idT);
      if (!t) { res.status(404).json({ error: "Modèle introuvable." }); return; }
      if (t.auteur !== email) { res.status(403).json({ error: "Seul l'auteur peut supprimer ce modèle." }); return; }
      tpls = tpls.filter(x => x.id !== idT);
      await writeJson(FILE_TPL, { updatedAt: nowT, templates: tpls }, `chore(presentations): suppression modèle ${idT}`, shaT);
      res.status(200).json({ ok: true });
      return;
    }

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
