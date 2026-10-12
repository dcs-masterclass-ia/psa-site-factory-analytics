/**
 * Tri automatique d'un ticket à sa création (miroir de pipeline/tickets_auto.py : mêmes règles, à garder synchronisées).
 * Catégories : donnee_simple (niveau 1), bug (niveau 2), gros_chantier (niveau 3), question (niveau 0).
 * En cas de doute on monte d'un niveau, jamais l'inverse. Le texte du ticket sert à classer, jamais d'instruction.
 */
const crypto = require("crypto");

const CATEGORIES = {
  donnee_simple: { label: "Ajout simple", niveau: 1, suite: "Une modification automatique est préparée après ton accord." },
  bug: { label: "Bug", niveau: 2, suite: "Un correctif est préparé et testé, puis validé avant mise en ligne." },
  gros_chantier: { label: "Gros chantier", niveau: 3, suite: "La demande est importante : un cadrage (effort, plan, risques) est préparé pour décision." },
  question: { label: "Question", niveau: 0, suite: "Une réponse est rédigée." },
};
const MOTS_GROS = /nouvel(le)?s? (onglet|module|page|source|tableau de bord|dashboard)|refonte|refondre|nouvelle? (fonctionnalit|int[ée]gration|api)|automatis|intégrer|integrer|migration|import|synchronis|multi-?langue|droits|permissions|authentification/i;
const MOTS_SIMPLE = /ajouter|ajout|colonne|total|libell|renomm|afficher|montrer|tooltip|info-?bulle|trier|tri |pourcentage|effectif|couleur/i;

function classer(t) {
  const texte = `${t.titre || ""} ${t.description || ""}`;
  if (t.type === "question") return ["question", "type déclaré : question"];
  if (t.type === "bug") return ["bug", "type déclaré : bug"];
  if (MOTS_GROS.test(texte) || (t.description || "").length > 700) return ["gros_chantier", "demande large (nouveau module/source ou description longue)"];
  if (MOTS_SIMPLE.test(texte)) return ["donnee_simple", "ajout ciblé sur un écran existant"];
  return ["gros_chantier", "périmètre pas assez clair pour une modification automatique"];
}

/** Pose ticket.triage + un commentaire système visible par l'auteur. Idempotent. */
function trier(ticket, now = Date.now()) {
  if (ticket.triage) return ticket;
  const [cat, raison] = classer(ticket);
  const c = CATEGORIES[cat];
  ticket.triage = { categorie: cat, niveau: c.niveau, raison, methode: "regles", at: now };
  (ticket.commentaires = ticket.commentaires || []).push({ auteur: "converge-auto", systeme: true, at: now, texte: `Ticket reçu et trié : ${c.label}. ${c.suite}` });
  ticket.updatedAt = now;
  return ticket;
}

/** Lien signé (même calcul que api/ticket-decision.js et pipeline/tickets_auto.py). */
function lienDecision(id, action, secret, now = Date.now()) {
  const exp = now + 7 * 86400 * 1000;
  const sig = crypto.createHmac("sha256", secret).update(`${id}|${action}|${exp}`).digest("hex");
  return `https://converge-tradein.vercel.app/api/ticket-decision?id=${id}&a=${action}&exp=${exp}&sig=${sig}`;
}

module.exports = { CATEGORIES, classer, trier, lienDecision };
