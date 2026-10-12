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
const { lance } = require("./_lib/dispatch");

const FILE = "tickets/tickets.json";
const ACTIONS = { accept: "accepte", refuse: "refuse", merge: "accepte", abandon: "refuse", ask: "precision", send: "envoi", edit: "envoi", drop: "abandon", tobug: "bug" };
const REPONSE = { send: true, edit: true, drop: true, tobug: true }; // décision sur la réponse (ou le bug détecté) préparée pour une question
const VALIDATION = { merge: true, abandon: true }; // 2e décision : mise en ligne du correctif préparé par l'agent
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
    if (REPONSE[q.a]) {
      const rep = t.reponse;
      if (!rep || rep.etat !== "attente") { page(res, 200, "Déjà traité", "Cette réponse a déjà été traitée, ou aucune n'est en attente."); return; }
      const titres = { send: "Envoyer la réponse", edit: "Modifier puis envoyer la réponse", drop: "Ne pas répondre", tobug: "Traiter comme un bug" };
      if (req.method !== "POST") {
        const champs = ["id", "a", "exp", "sig"].map(k => `<input type="hidden" name="${k}" value="${esc(q[k])}">`).join("");
        const couleur = q.a === "drop" ? "#c24a44" : "#2b8f62";
        const zone = q.a === "edit" ? `<textarea name="texte" required maxlength="3000" rows="10" style="width:100%;box-sizing:border-box;font:15px/1.5 system-ui;border:1px solid #dcdce2;border-radius:12px;padding:10px;margin-top:10px">${esc(rep.texte)}</textarea>`
          : (q.a === "send" ? `<div style="white-space:pre-wrap;background:#f6f6f8;border-radius:12px;padding:12px;margin-top:10px;font-size:14.5px">${esc(rep.texte)}</div>` : (rep.bug ? `<div style="white-space:pre-wrap;background:#fdf3e3;border-radius:12px;padding:12px;margin-top:10px;font-size:14px">${esc(rep.bug)}</div>` : ""));
        page(res, 200, `${titres[q.a]} ?`, `<b>${esc(t.titre)}</b><br><span style="font-size:14px;color:#6d727a">de ${esc(t.auteur)}</span>${zone}`,
          `<form method="post" style="margin-top:16px">${champs}<button style="font:600 15px system-ui;border:0;border-radius:12px;padding:11px 20px;color:#fff;background:${couleur};cursor:pointer">${titres[q.a]}</button></form>`);
        return;
      }
      const now = Date.now();
      if (q.a === "send" || q.a === "edit") {
        const texte = String(q.a === "edit" ? q.texte : rep.texte).replace(/\u0000/g, "").trim().slice(0, 3000);
        if (!texte) { page(res, 400, "Réponse vide", "Écris la réponse avant d'envoyer."); return; }
        (t.commentaires = t.commentaires || []).push({ auteur: AUTEUR, systeme: true, at: now, texte: `Statut : ${t.statut} → resolu` });
        t.commentaires.push({ auteur: "equipe-converge", texte, at: now + 1 });
        t.statut = "resolu"; rep.etat = "envoyee"; rep.texte = texte;
      } else if (q.a === "drop") {
        rep.etat = "abandon";
      } else { // tobug : l'analyse a trouvé une anomalie, M. la fait traiter par l'agent de correction
        t.triage = { ...(t.triage || {}), categorie: "bug", niveau: 2, raison: "anomalie confirmée à partir de l'analyse de la question", methode: "agent", at: now };
        t.decision = { choix: "accepte", at: now, via: "teams" };
        (t.commentaires = t.commentaires || []).push({ auteur: AUTEUR, systeme: true, at: now, texte: `Statut : ${t.statut} → en_cours` });
        t.commentaires.push({ auteur: AUTEUR, systeme: true, at: now + 1, texte: "Une anomalie est confirmée : un correctif est en préparation." });
        t.statut = "en_cours"; rep.etat = "bug";
      }
      t.updatedAt = now + 1;
      await writeJson(FILE, { updatedAt: now, tickets }, `chore(tickets): ${t.id} — réponse ${rep.etat} (Teams)`, sha);
      if (q.a === "tobug") await lance("tickets-agent.yml");
      page(res, 200, { send: "Réponse envoyée", edit: "Réponse envoyée", drop: "Rien n'est envoyé", tobug: "Traité comme un bug" }[q.a],
        { send: "L'auteur est alerté dans le dashboard.", edit: "L'auteur est alerté dans le dashboard.", drop: "Aucune réponse n'est envoyée à l'auteur.", tobug: "Le correctif démarre automatiquement." }[q.a]);
      return;
    }
    if (q.a === "ask") {
      if (t.decision || t.agent) { page(res, 200, "Déjà décidé", "Ce ticket a déjà une décision : la précision n'est plus possible."); return; }
      if (req.method !== "POST") {
        const form = `<form method="post" style="margin-top:14px"><input type="hidden" name="id" value="${esc(q.id)}"><input type="hidden" name="a" value="ask"><input type="hidden" name="exp" value="${esc(q.exp)}"><input type="hidden" name="sig" value="${esc(q.sig)}">
<textarea name="texte" required maxlength="1000" rows="5" placeholder="Ex. : sur quel onglet exactement ? Peux-tu donner un exemple ?" style="width:100%;box-sizing:border-box;font:15px system-ui;border:1px solid #dcdce2;border-radius:12px;padding:10px"></textarea>
<button style="margin-top:12px;font:600 15px system-ui;border:0;border-radius:12px;padding:11px 20px;color:#fff;background:#7c63ee;cursor:pointer">Envoyer à l'auteur</button></form>`;
        page(res, 200, "Demander des précisions", `<b>${esc(t.titre)}</b><br><span style="font-size:14px;color:#6d727a">Ta question sera envoyée à ${esc(t.auteur)}, qui sera alerté dans le dashboard.</span>`, form);
        return;
      }
      const texte = String(q.texte || "").replace(/\u0000/g, "").trim().slice(0, 1000);
      if (!texte) { page(res, 400, "Question vide", "Écris ta question avant d'envoyer."); return; }
      const now = Date.now();
      (t.commentaires = t.commentaires || []).push({ auteur: "equipe-converge", texte, at: now });
      t.attente = "auteur";
      t.updatedAt = now;
      await writeJson(FILE, { updatedAt: now, tickets }, `chore(tickets): ${t.id} — précision demandée (Teams)`, sha);
      page(res, 200, "Question envoyée", "L'auteur est alerté dans le dashboard. Tu recevras une carte Teams dès qu'il répond.");
      return;
    }
    const verbe = { accept: "Accepter", refuse: "Refuser", merge: "Mettre en ligne", abandon: "Abandonner" }[q.a];
    const positif = q.a === "accept" || q.a === "merge";
    if (VALIDATION[q.a]) {
      if (!t.agent || t.agent.etat !== "attente_validation") { page(res, 409, "Rien à valider", "Aucune modification n'attend de validation pour ce ticket."); return; }
      if (t.validation) { page(res, 200, "Déjà décidé", `La mise en ligne a déjà été <b>${t.validation.choix === "accepte" ? "validée" : "abandonnée"}</b>.`); return; }
    } else if (t.decision) { page(res, 200, "Déjà décidé", `Ce ticket a déjà été <b>${t.decision.choix === "accepte" ? "accepté" : "refusé"}</b>.`); return; }
    if (req.method !== "POST") {
      const form = `<form method="post" style="margin-top:18px"><input type="hidden" name="id" value="${esc(q.id)}"><input type="hidden" name="a" value="${esc(q.a)}"><input type="hidden" name="exp" value="${esc(q.exp)}"><input type="hidden" name="sig" value="${esc(q.sig)}">
<button style="font:600 15px system-ui;border:0;border-radius:12px;padding:11px 20px;color:#fff;background:${positif ? "#2b8f62" : "#c24a44"};cursor:pointer">${verbe}${VALIDATION[q.a] ? "" : " ce ticket"}</button></form>`;
      page(res, 200, `${verbe} ce ticket ?`, `<b>${esc(t.titre)}</b><br><span style="font-size:14px;color:#6d727a">${esc((t.triage && t.triage.categorie) || t.type)} · ${esc(t.auteur)}</span>`, form);
      return;
    }
    const now = Date.now();
    if (VALIDATION[q.a]) {
      t.validation = { choix: ACTIONS[q.a], at: now, via: "teams" };
      t.updatedAt = now;
      await writeJson(FILE, { updatedAt: now, tickets }, `chore(tickets): ${t.id} — mise en ligne ${ACTIONS[q.a]} (Teams)`, sha);
      if (positif) await lance("tickets-agent.yml");
      page(res, 200, positif ? "Mise en ligne validée" : "Modification abandonnée",
        positif ? "La modification sera mise en ligne dans quelques minutes." : "La modification est abandonnée : rien n'est mis en ligne.");
      return;
    }
    t.decision = { choix: ACTIONS[q.a], at: now, via: "teams" };
    (t.commentaires = t.commentaires || []).push({ auteur: AUTEUR, systeme: true, at: now,
      texte: q.a === "accept" ? "Statut : " + t.statut + " → en_cours" : "Statut : " + t.statut + " → refuse" });
    t.statut = q.a === "accept" ? "en_cours" : "refuse";
    t.updatedAt = now;
    await writeJson(FILE, { updatedAt: now, tickets }, `chore(tickets): ${t.id} — décision ${ACTIONS[q.a]} (Teams)`, sha);
    if (q.a === "accept") await lance("tickets-agent.yml");
    page(res, 200, q.a === "accept" ? "Ticket accepté" : "Ticket refusé",
      q.a === "accept" ? "C'est pris en compte : la modification démarre automatiquement." : "Le ticket est refusé. L'auteur en sera informé.");
  } catch (e) {
    console.error("[ticket-decision]", e && e.message);
    page(res, 500, "Erreur serveur", "La décision n'a pas pu être enregistrée. Réessaie dans un instant.");
  }
};
module.exports.signe = signe;
