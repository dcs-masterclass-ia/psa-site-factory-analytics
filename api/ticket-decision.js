/**
 * Décision sur un ticket depuis la carte Teams : Accepter / Refuser.
 *
 * Les boutons de la carte ouvrent GET /api/ticket-decision?id=&a=accept|refuse&exp=&sig= ; la page affiche une
 * confirmation (un simple GET -- aperçu de lien, antivirus -- ne décide jamais), le bouton envoie un POST.
 * Authentification par lien signé (HMAC-SHA256 de "id|action|exp" avec TICKETS_LINK_SECRET, validité 7 jours),
 * route publique côté middleware : le lien lui-même est le secret.
 *
 * Effet : ticket.decision = { choix, at, via:"teams" } ; accept -> statut en_cours (le workflow de modification
 * autonome ne traite QUE les tickets acceptés) ; refuse -> statut refuse. Un commentaire système prévient l'auteur.
 * Une décision n'est prise qu'une fois.
 */
const crypto = require("crypto");
const { readJson, writeJson } = require("./_lib/store");

const FILE = "tickets/tickets.json";
const ACTIONS = { accept: "accepte", refuse: "refuse" };
const AUTEUR = "decision-teams";

const signe = (id, a, exp) => crypto.createHmac("sha256", process.env.TICKETS_LINK_SECRET || "").update(`${id}|${a}|${exp}`).digest("hex");

function lienValide(q) {
  const secret = process.env.TICKETS_LINK_SECRET;
  const { id, a, exp, sig } = q;
  if (!secret || !id || !ACTIONS[a] || !/^\d+$/.test(String(exp)) || !sig) return false;
  if (Number(exp) < Date.now()) return false;
  const attendu = Buffer.from(signe(id, a, exp)), recu = Buffer.from(String(sig));
  return attendu.length === recu.length && crypto.timingSafeEqual(attendu, recu);
}

const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
function page(res, code, titre, corps, formulaire) {
  res.setHeader("content-type", "text/html; charset=utf-8");
  res.setHeader("cache-control", "no-store");
  res.status(code).send(`<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Converge — ticket</title>
<body style="font:16px/1.5 system-ui,sans-serif;background:#f6f6f8;display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0">
<div style="background:#fff;border-radius:18px;box-shadow:0 10px 40px rgba(30,20,70,.12);padding:28px 32px;max-width:460px;margin:16px">
<h2 style="margin:0 0 8px;font-size:20px">${esc(titre)}</h2><div style="color:#4b4b4f">${corps}</div>${formulaire || ""}</div></body>`);
}

module.exports = async function handler(req, res) {
  const q = req.method === "POST" ? { ...(req.query || {}), ...(req.body && typeof req.body === "object" ? req.body : {}) } : (req.query || {});
  if (!lienValide(q)) { page(res, 400, "Lien invalide ou expiré", "Ce lien n'est plus valable. Utilise la carte la plus récente ou le suivi des tickets."); return; }
  try {
    const { data, sha } = await readJson(FILE);
    const tickets = (data && Array.isArray(data.tickets)) ? data.tickets : [];
    const t = tickets.find(x => x.id === q.id);
    if (!t) { page(res, 404, "Ticket introuvable", "Ce ticket n'existe plus."); return; }
    const verbe = q.a === "accept" ? "Accepter" : "Refuser";
    if (t.decision) { page(res, 200, "Déjà décidé", `Ce ticket a déjà été <b>${t.decision.choix === "accepte" ? "accepté" : "refusé"}</b>.`); return; }
    if (req.method !== "POST") {
      const form = `<form method="post" style="margin-top:18px"><input type="hidden" name="id" value="${esc(q.id)}"><input type="hidden" name="a" value="${esc(q.a)}"><input type="hidden" name="exp" value="${esc(q.exp)}"><input type="hidden" name="sig" value="${esc(q.sig)}">
<button style="font:600 15px system-ui;border:0;border-radius:12px;padding:11px 20px;color:#fff;background:${q.a === "accept" ? "#2b8f62" : "#c24a44"};cursor:pointer">${verbe} ce ticket</button></form>`;
      page(res, 200, `${verbe} ce ticket ?`, `<b>${esc(t.titre)}</b><br><span style="font-size:14px;color:#6d727a">${esc((t.triage && t.triage.categorie) || t.type)} · ${esc(t.auteur)}</span>`, form);
      return;
    }
    const now = Date.now();
    t.decision = { choix: ACTIONS[q.a], at: now, via: "teams" };
    (t.commentaires = t.commentaires || []).push({ auteur: AUTEUR, systeme: true, at: now,
      texte: q.a === "accept" ? "Statut : " + t.statut + " → en_cours" : "Statut : " + t.statut + " → refuse" });
    t.statut = q.a === "accept" ? "en_cours" : "refuse";
    t.updatedAt = now;
    await writeJson(FILE, { updatedAt: now, tickets }, `chore(tickets): ${t.id} — décision ${ACTIONS[q.a]} (Teams)`, sha);
    page(res, 200, q.a === "accept" ? "Ticket accepté" : "Ticket refusé",
      q.a === "accept" ? "C'est pris en compte : la modification démarre automatiquement." : "Le ticket est refusé. L'auteur en sera informé.");
  } catch (e) {
    console.error("[ticket-decision]", e && e.message);
    page(res, 500, "Erreur serveur", "La décision n'a pas pu être enregistrée. Réessaie dans un instant.");
  }
};
module.exports.signe = signe;
