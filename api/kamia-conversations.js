/**
 * Historique des conversations KamIA, persiste par profil connecte dans le
 * repo de donnees prive (voir api/_lib/store.js). Remplace l'ancien
 * stockage localStorage cote navigateur, qui ne survivait pas au
 * changement de poste.
 *
 * Modele : un fichier JSON par utilisateur, kamia/<hash email>.json,
 *   { email, updatedAt, conversations: [ { id, title, createdAt,
 *     updatedAt, messages, history, scope } ] }
 * Le client reste maitre de la liste (il envoie l'ensemble complet a
 * chaque flush) ; le serveur ne fait que valider, borner et ecrire.
 *
 * Routes (session valide obligatoire, cf. middleware.js) :
 *   GET    /api/kamia-conversations           -> { conversations: [meta...] }  (sans messages)
 *   GET    /api/kamia-conversations?id=<id>   -> { conversation: {...complet} }
 *   PUT    /api/kamia-conversations           body { upsert: [conv...], delete: [id...] }
 *                                             -> fusionne dans le fichier existant
 *
 * PUT est volontairement un merge (et non un "remplace tout") : le client
 * ne charge en memoire que les conversations ouvertes, il ne pourrait pas
 * renvoyer l'ensemble complet sans risquer d'ecraser les autres.
 *
 * Protege par middleware.js en amont ; la verification ci-dessous est une
 * defense en profondeur (meme discipline qu'api/agent.js).
 */

const crypto = require("crypto");
const { verifySessionFromRequest } = require("./_lib/auth");
const { readJson, writeJson } = require("./_lib/store");

const MAX_CONVERSATIONS = 200;
const MAX_FILE_BYTES = 900 * 1024; // garde-fou : l'API Contents renvoie le contenu jusqu'a ~1 Mo

function fileFor(email) {
  const hash = crypto.createHash("sha256").update(String(email).toLowerCase()).digest("hex").slice(0, 32);
  return `kamia/${hash}.json`;
}

// ne garde que les champs de liste (pas les messages, potentiellement lourds)
function toMeta(c) {
  return {
    id: c.id,
    title: c.title || "Conversation",
    createdAt: c.createdAt || c.updatedAt || 0,
    updatedAt: c.updatedAt || c.createdAt || 0,
    messageCount: Array.isArray(c.messages) ? c.messages.length : 0,
  };
}

// normalise / borne une conversation venant du client (donnees non fiables)
function sanitizeConversation(c) {
  if (!c || typeof c !== "object") return null;
  const id = String(c.id || "").slice(0, 80);
  if (!id) return null;
  const messages = Array.isArray(c.messages) ? c.messages.slice(0, 400).map(m => ({
    role: m && m.role === "assistant" ? "assistant" : "user",
    text: String((m && m.text) || "").slice(0, 20000),
    hasAgents: !!(m && m.hasAgents),
    agentBadges: Array.isArray(m && m.agentBadges) ? m.agentBadges.slice(0, 12).map(String) : [],
    charts: Array.isArray(m && m.charts) ? m.charts.slice(0, 6) : [],
    attachmentNames: Array.isArray(m && m.attachmentNames) ? m.attachmentNames.slice(0, 3).map(String) : [],
  })) : [];
  return {
    id,
    title: String(c.title || "Conversation").slice(0, 120) || "Conversation",
    createdAt: Number(c.createdAt) || Date.now(),
    updatedAt: Number(c.updatedAt) || Date.now(),
    messages,
    history: Array.isArray(c.history) ? c.history.slice(0, 200) : [],
    scope: Array.isArray(c.scope) ? c.scope.slice(0, 64).map(String) : [],
  };
}

module.exports = async function handler(req, res) {
  const session = verifySessionFromRequest(req);
  if (!session || !session.email) {
    res.status(401).json({ error: "Non authentifie." });
    return;
  }
  const filePath = fileFor(session.email);

  try {
    if (req.method === "GET") {
      const { data } = await readJson(filePath);
      const conversations = (data && Array.isArray(data.conversations)) ? data.conversations : [];
      const id = req.query && req.query.id;
      if (id) {
        const conv = conversations.find(c => c.id === id);
        if (!conv) { res.status(404).json({ error: "Conversation introuvable." }); return; }
        res.status(200).json({ conversation: conv });
        return;
      }
      res.status(200).json({
        conversations: conversations
          .map(toMeta)
          .sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0)),
      });
      return;
    }

    if (req.method === "PUT") {
      const body = req.body || {};
      const upsert = Array.isArray(body.upsert) ? body.upsert : [];
      const del = Array.isArray(body.delete) ? body.delete.map(String) : [];
      if (!upsert.length && !del.length) { res.status(400).json({ error: "upsert[] ou delete[] attendu." }); return; }

      const { data, sha } = await readJson(filePath);
      const existing = (data && Array.isArray(data.conversations)) ? data.conversations : [];

      const byId = new Map(existing.map(c => [c.id, c]));
      for (const raw of upsert) {
        const c = sanitizeConversation(raw);
        if (c) byId.set(c.id, c);
      }
      for (const id of del) byId.delete(id);

      let cleaned = [...byId.values()]
        .sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0))
        .slice(0, MAX_CONVERSATIONS);

      let payload = { email: String(session.email).toLowerCase(), updatedAt: Date.now(), conversations: cleaned };

      // si trop volumineux, on rogne les conversations les plus anciennes
      // jusqu'a repasser sous la limite (jamais laisser un write echouer
      // silencieusement cote GitHub sur un fichier > ~1 Mo).
      while (Buffer.byteLength(JSON.stringify(payload)) > MAX_FILE_BYTES && payload.conversations.length > 1) {
        payload.conversations.pop();
      }

      await writeJson(
        filePath,
        payload,
        `chore(kamia): historique conversations (${payload.conversations.length}) — ${session.email}`,
        sha,
      );
      res.status(200).json({ ok: true, updatedAt: payload.updatedAt, kept: payload.conversations.length });
      return;
    }

    res.status(405).json({ error: "Methode non autorisee." });
  } catch (e) {
    console.error("[kamia-conversations]", e);
    res.status(502).json({ error: "Stockage indisponible.", detail: String(e && e.message || e) });
  }
};
