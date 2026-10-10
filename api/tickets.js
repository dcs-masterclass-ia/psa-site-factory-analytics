/**
 * Tickets du dashboard : signaler un bug dans les données, demander une
 * optimisation, poser une question. Stockés dans le repo de données PRIVÉ
 * (tickets/tickets.json, via api/_lib/store.js) -- jamais dans le repo de code,
 * qui est public.
 *
 * Modèle d'un ticket :
 *   { id, type: bug|optimisation|question, priorite: normale|haute,
 *     titre, description, statut: nouveau|en_cours|resolu|refuse,
 *     createdAt, updatedAt, auteur, contexte: { source, sites[], nbSites,
 *     periode:{from,to}, onglet }, commentaires: [ { auteur, texte, at, systeme } ] }
 *
 * Routes (session valide obligatoire, cf. middleware.js) :
 *   GET  /api/tickets                       -> { tickets: [...], peutGerer }
 *        profil complet : tous les tickets ; profil limité : les siens seulement
 *   POST /api/tickets {action:"create",...} -> crée (profils complet ET limité)
 *   POST /api/tickets {action:"comment", id, texte}
 *        -> l'auteur du ticket, ou un profil complet
 *   POST /api/tickets {action:"status", id, statut}
 *        -> profil complet seulement
 *
 * Notification optionnelle : si TICKETS_WEBHOOK_URL (webhook Teams, carte
 * adaptative) est défini, chaque nouveau ticket y est posté (best effort, un
 * échec n'empêche jamais la création).
 *
 * Concurrence : lecture-modification-écriture sur un seul fichier ; deux
 * créations à la milliseconde peuvent s'écraser (dernier gagnant). Risque jugé
 * acceptable pour quelques utilisateurs ; à repasser en un fichier par ticket si
 * l'usage grossit.
 */

const crypto = require("crypto");
const { verifySessionFromRequest } = require("./_lib/auth");
const { fail } = require("./_lib/errors");
const { readJson, writeJson } = require("./_lib/store");

const FILE = "tickets/tickets.json";
const TYPES = ["bug", "optimisation", "question"];
const PRIORITES = ["normale", "haute"];
const STATUTS = ["nouveau", "en_cours", "resolu", "refuse"];
const SOURCES = ["ga", "sc", "ps", "tb", "gcp"];
const MAX_TICKETS = 500;
const MAX_PAR_JOUR = 10;
const MAX_FILE_BYTES = 900 * 1024;
const LIBELLE_TYPE = { bug: "Bug de données", optimisation: "Optimisation", question: "Question" };

const txt = (v, max) => String(v == null ? "" : v).replace(/\u0000/g, "").trim().slice(0, max);
const isoDate = v => (/^\d{4}-\d{2}-\d{2}$/.test(String(v || "")) ? String(v) : null);

function newId() {
  const d = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  return `T-${d}-${crypto.randomBytes(2).toString("hex")}`;
}

function nettoieContexte(c) {
  c = c && typeof c === "object" ? c : {};
  return {
    source: SOURCES.includes(c.source) ? c.source : null,
    sites: Array.isArray(c.sites) ? c.sites.slice(0, 6).map(s => txt(s, 60)).filter(Boolean) : [],
    nbSites: Math.max(0, Math.min(1000, parseInt(c.nbSites, 10) || 0)),
    periode: { from: isoDate(c.periode && c.periode.from), to: isoDate(c.periode && c.periode.to) },
    onglet: txt(c.onglet, 40),
  };
}

function valideCreation(b) {
  const type = TYPES.includes(b.type) ? b.type : null;
  const titre = txt(b.titre, 120);
  const description = txt(b.description, 3000);
  if (!type) return { erreur: "Type de ticket invalide." };
  if (titre.length < 3) return { erreur: "Le titre est trop court." };
  if (description.length < 10) return { erreur: "Décris le problème ou la demande en quelques mots de plus." };
  return {
    ok: {
      type,
      priorite: PRIORITES.includes(b.priorite) ? b.priorite : "normale",
      titre,
      description,
      contexte: nettoieContexte(b.contexte),
    },
  };
}

async function notifie(ticket) {
  const url = process.env.TICKETS_WEBHOOK_URL;
  if (!url) return;
  try {
    const ctx = ticket.contexte || {};
    const carte = {
      type: "message",
      attachments: [{
        contentType: "application/vnd.microsoft.card.adaptive",
        content: {
          $schema: "http://adaptivecards.io/schemas/adaptive-card.json",
          type: "AdaptiveCard", version: "1.4",
          body: [
            { type: "TextBlock", size: "Medium", weight: "Bolder", wrap: true,
              text: `${ticket.priorite === "haute" ? "🔴 " : ""}${LIBELLE_TYPE[ticket.type]} — ${ticket.titre}` },
            { type: "TextBlock", wrap: true, text: ticket.description.slice(0, 600) },
            { type: "FactSet", facts: [
              { title: "Ticket", value: ticket.id },
              { title: "Auteur", value: ticket.auteur },
              { title: "Contexte", value: `${ctx.onglet || "?"} · ${ctx.nbSites || "?"} site(s)` },
            ] },
          ],
        },
      }],
    };
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 3000);
    await fetch(url, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(carte), signal: ctrl.signal });
    clearTimeout(t);
  } catch (e) {
    console.error("[tickets:notify]", e && e.message);
  }
}

module.exports = async function handler(req, res) {
  const session = verifySessionFromRequest(req);
  if (!session || !session.email) { res.status(401).json({ error: "Non authentifie." }); return; }
  const email = String(session.email).toLowerCase();
  const gere = session.role === "full";

  try {
    if (req.method === "GET") {
      const { data } = await readJson(FILE);
      const tous = (data && Array.isArray(data.tickets)) ? data.tickets : [];
      const visibles = gere ? tous : tous.filter(t => t.auteur === email);
      res.setHeader("cache-control", "no-store");
      res.status(200).json({ tickets: visibles.sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0)), peutGerer: gere, moi: email });
      return;
    }

    if (req.method !== "POST") { res.status(405).json({ error: "Methode non supportee." }); return; }
    const body = req.body && typeof req.body === "object" ? req.body : {};
    const action = body.action;
    const { data, sha } = await readJson(FILE);
    const tickets = (data && Array.isArray(data.tickets)) ? data.tickets : [];
    const now = Date.now();

    if (action === "create") {
      const v = valideCreation(body);
      if (v.erreur) { res.status(400).json({ error: v.erreur }); return; }
      const recents = tickets.filter(t => t.auteur === email && now - (t.createdAt || 0) < 86400000).length;
      if (recents >= MAX_PAR_JOUR) { res.status(429).json({ error: `Limite de ${MAX_PAR_JOUR} tickets par jour atteinte.` }); return; }
      if (tickets.length >= MAX_TICKETS) { res.status(507).json({ error: "Trop de tickets stockés, contacte l'administrateur." }); return; }
      const ticket = { id: newId(), ...v.ok, statut: "nouveau", createdAt: now, updatedAt: now, auteur: email, commentaires: [] };
      tickets.push(ticket);
      await ecrit(tickets, sha, `ticket ${ticket.id} — ${email}`);
      await notifie(ticket);
      res.status(200).json({ ok: true, ticket });
      return;
    }

    const id = txt(body.id, 40);
    const ticket = tickets.find(t => t.id === id);
    if (!ticket || (!gere && ticket.auteur !== email)) { res.status(404).json({ error: "Ticket introuvable." }); return; }

    if (action === "comment") {
      const texte = txt(body.texte, 1000);
      if (texte.length < 1) { res.status(400).json({ error: "Commentaire vide." }); return; }
      if ((ticket.commentaires || []).length >= 50) { res.status(400).json({ error: "Trop de commentaires sur ce ticket." }); return; }
      (ticket.commentaires = ticket.commentaires || []).push({ auteur: email, texte, at: now });
      ticket.updatedAt = now;
      await ecrit(tickets, sha, `ticket ${id} — commentaire`);
      res.status(200).json({ ok: true, ticket });
      return;
    }

    if (action === "status") {
      if (!gere) { res.status(403).json({ error: "Acces non autorise pour ce profil." }); return; }
      if (!STATUTS.includes(body.statut)) { res.status(400).json({ error: "Statut invalide." }); return; }
      if (ticket.statut !== body.statut) {
        (ticket.commentaires = ticket.commentaires || []).push({ auteur: email, texte: `Statut : ${ticket.statut} → ${body.statut}`, at: now, systeme: true });
        ticket.statut = body.statut;
        ticket.updatedAt = now;
        await ecrit(tickets, sha, `ticket ${id} — statut ${body.statut}`);
      }
      res.status(200).json({ ok: true, ticket });
      return;
    }

    res.status(400).json({ error: "Action inconnue." });
  } catch (e) {
    fail(res, 500, "Erreur serveur.", e, "tickets");
  }
};

async function ecrit(tickets, sha, message) {
  let liste = tickets;
  let payload = { updatedAt: Date.now(), tickets: liste };
  // garde-fou taille : on retire d'abord les plus anciens tickets résolus/refusés
  while (Buffer.byteLength(JSON.stringify(payload)) > MAX_FILE_BYTES && liste.length > 1) {
    const i = liste.findIndex(t => t.statut === "resolu" || t.statut === "refuse");
    liste = liste.filter((_, k) => k !== (i >= 0 ? i : 0));
    payload = { updatedAt: Date.now(), tickets: liste };
  }
  await writeJson(FILE, payload, `chore(tickets): ${message}`, sha);
}
