/**
 * Calendrier d'événements : ce qui explique une cassure de courbe (campagne lancée, bouton ajouté, bascule V2, offre commerciale,
 * changement de balisage…). Stocké dans le repo de données PRIVÉ (events/events.json, via api/_lib/store.js).
 *
 * Un événement : { id, date: AAAA-MM-JJ, fin?: AAAA-MM-JJ, type, titre, detail?, sites: [] (vide = tous), auteur, createdAt }
 *
 * Routes (session valide obligatoire, cf. middleware.js) :
 *   GET  /api/events                      -> { events: [...], peutEcrire }   (profil complet ET limité : lecture seule pour le limité)
 *   POST /api/events {action:"save", event}      crée (sans id) ou met à jour — profil complet seulement
 *   POST /api/events {action:"delete", id}       l'auteur, ou tout profil complet
 *
 * Concurrence : lecture-modification-écriture d'un seul fichier, dernier gagnant (même compromis que api/tickets.js).
 */

const crypto = require("crypto");
const { verifySessionFromRequest } = require("./_lib/auth");
const { fail } = require("./_lib/errors");
const { readJson, writeJson } = require("./_lib/store");

const FILE = "events/events.json";
const TYPES = ["campagne", "site", "v2", "offre", "tracking", "autre"];
const MAX_EVENTS = 1000;
const MAX_FILE_BYTES = 900 * 1024;

const txt = (v, max) => String(v == null ? "" : v).replace(/\u0000/g, "").trim().slice(0, max);
const isoDate = v => (/^\d{4}-\d{2}-\d{2}$/.test(String(v || "")) && !isNaN(Date.parse(v)) ? String(v) : null);

function nettoie(e) {
  e = e && typeof e === "object" ? e : {};
  const date = isoDate(e.date);
  let fin = isoDate(e.fin);
  if (fin && date && fin < date) fin = null;
  return {
    date,
    fin,
    type: TYPES.includes(e.type) ? e.type : "autre",
    titre: txt(e.titre, 120),
    detail: txt(e.detail, 600),
    sites: Array.isArray(e.sites) ? e.sites.slice(0, 120).map(s => txt(s, 60)).filter(Boolean) : [],
  };
}

module.exports = async function handler(req, res) {
  const session = verifySessionFromRequest(req);
  if (!session || !session.email) { res.status(401).json({ error: "Non authentifie." }); return; }
  const email = String(session.email).toLowerCase();
  const gere = session.role === "full";

  try {
    if (req.method === "GET") {
      const { data } = await readJson(FILE);
      const events = (data && Array.isArray(data.events)) ? data.events : [];
      res.setHeader("cache-control", "no-store");
      res.status(200).json({ events: events.sort((a, b) => String(b.date).localeCompare(String(a.date))), peutEcrire: gere, moi: email });
      return;
    }
    if (req.method !== "POST") { res.status(405).json({ error: "Methode non supportee." }); return; }
    if (!gere) { res.status(403).json({ error: "Acces non autorise pour ce profil." }); return; }

    const body = req.body && typeof req.body === "object" ? req.body : {};
    const { data, sha } = await readJson(FILE);
    let events = (data && Array.isArray(data.events)) ? data.events : [];
    const now = Date.now();

    if (body.action === "save") {
      const n = nettoie(body.event);
      if (!n.date) { res.status(400).json({ error: "Indique la date de l'événement." }); return; }
      if (n.titre.length < 3) { res.status(400).json({ error: "Donne un titre à l'événement." }); return; }
      const id = txt(body.event && body.event.id, 40);
      let ev;
      if (id) {
        const i = events.findIndex(x => x.id === id);
        if (i < 0) { res.status(404).json({ error: "Événement introuvable." }); return; }
        ev = Object.assign(events[i], n, { updatedAt: now, modifiePar: email });
      } else {
        if (events.length >= MAX_EVENTS) { res.status(507).json({ error: "Trop d'événements stockés." }); return; }
        ev = Object.assign({ id: "E-" + now.toString(36) + crypto.randomBytes(2).toString("hex"), createdAt: now, auteur: email }, n, { updatedAt: now, modifiePar: email });
        events.push(ev);
      }
      await ecrit(events, sha, `événement ${ev.id} — ${email}`);
      res.status(200).json({ ok: true, event: ev });
      return;
    }

    if (body.action === "delete") {
      const id = txt(body.id, 40);
      if (!events.some(x => x.id === id)) { res.status(404).json({ error: "Événement introuvable." }); return; }
      events = events.filter(x => x.id !== id);
      await ecrit(events, sha, `suppression événement ${id}`);
      res.status(200).json({ ok: true });
      return;
    }

    res.status(400).json({ error: "Action inconnue." });
  } catch (e) {
    fail(res, 500, "Erreur serveur.", e, "events");
  }
};

async function ecrit(events, sha, message) {
  let l = events;
  let payload = { updatedAt: Date.now(), events: l };
  while (Buffer.byteLength(JSON.stringify(payload)) > MAX_FILE_BYTES && l.length > 1) {
    l = l.slice(0, -1);
    payload = { updatedAt: Date.now(), events: l };
  }
  await writeJson(FILE, payload, `chore(events): ${message}`, sha);
}
