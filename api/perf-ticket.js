/**
 * Redige un ticket Jira (titre + corps copiable) a partir des mesures
 * PageSpeed Insights reelles d'un site -- appele par le bouton "Ticket
 * Jira" de l'onglet Performance. Ne CREE rien dans Jira (pas d'API Jira
 * configuree cote serveur) : renvoie juste un texte pret a coller, comme
 * demande. Reutilise loadSite/callClaude comme le reste de l'assistant
 * (api/_lib/tools.js, api/agent.js) pour rester sur les memes donnees que
 * celles deja affichees au KAM, jamais une nouvelle mesure.
 */

const { callClaude } = require("./_lib/anthropic");
const { loadSite } = require("./_lib/data");
const { verifySessionFromRequest } = require("./_lib/auth");

// Meme profil que les agents specialistes (api/_lib/tools.js) : redige un
// texte structure a partir de donnees deja fournies, tache ciblee et
// courte -- Haiku suffit, pas besoin de Sonnet/Opus ici non plus.
// PAS de parametre "effort" : Haiku 4.5 le rejette (voir _lib/tools.js).
const TICKET_MODEL = "claude-haiku-4-5";

const SYSTEM = `Tu rediges des tickets Jira pour l'equipe technique du reseau PSA Site Factory, a partir de mesures PageSpeed Insights (Lighthouse) reelles sur le site de reprise d'un concessionnaire. Sois concret et actionnable : appuie-toi toujours sur les chiffres fournis, jamais de conseil generique du type "optimisez vos images" sans le relier a une metrique precise.

Reponds en deux parties separees par une ligne "---" seule (rien d'autre sur cette ligne) :
1. Un titre de ticket court (une seule ligne, sans prefixe "Titre :", sans guillemets).
2. Le corps du ticket : texte simple copiable tel quel dans Jira (pas de markdown complexe, pas de titres "##"), avec ces sections dans cet ordre : Contexte, Impact, Actions suggerees (liste a tirets "-"), Criteres d'acceptation (liste a tirets "-").`;

function decoupe(texte) {
  const brut = String(texte || "").trim();
  const parts = brut.split(/\n\s*---\s*\n/);
  if (parts.length >= 2 && parts[0].trim()) {
    return { title: parts[0].trim(), body: parts.slice(1).join("\n---\n").trim() };
  }
  return { title: "", body: brut };
}

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.status(405).json({ error: "Methode non autorisee." });
    return;
  }

  const session = verifySessionFromRequest(req);
  if (!session) {
    res.status(401).json({ error: "Non authentifie." });
    return;
  }

  const { site } = req.body || {};
  if (!site || typeof site !== "string") {
    res.status(400).json({ error: "site requis." });
    return;
  }

  const data = loadSite(site);
  const ps = data && data.pagespeed;
  const m = ps && ps.mobile;
  const opportunites = (m && m.opportunites) || [];
  if (!ps || opportunites.length === 0) {
    res.status(200).json({ empty: true });
    return;
  }

  const resume = {
    site,
    releve: ps.releve,
    scoreMobile: m.score,
    scoreDesktop: ps.desktop && ps.desktop.score,
    lcpMs: m.lcp, cls: m.cls, tbtMs: m.tbt, fcpMs: m.fcp, siMs: m.si,
    terrain: m.terrain || null,
    opportunites: opportunites.map(o => ({ titre: o.titre, gainMs: o.gainMs })),
  };

  try {
    const resp = await callClaude({
      model: TICKET_MODEL,
      system: SYSTEM,
      messages: [{ role: "user", content: "Donnees PageSpeed (JSON) :\n" + JSON.stringify(resume) }],
      maxTokens: 1000,
    });
    const text = (resp.content || []).filter(b => b.type === "text").map(b => b.text).join("\n");
    const { title, body } = decoupe(text);
    if (!body) {
      res.status(502).json({ error: "Reponse vide du modele." });
      return;
    }
    res.status(200).json({ title: title || ("Optimisation performance -- " + site), body });
  } catch (e) {
    res.status(500).json({ error: String(e && e.message ? e.message : e) });
  }
};
