/**
 * Reponse d'erreur serveur : message generique au client, detail dans les
 * logs Vercel uniquement (jamais d'e.message, de corps GitHub ou de chemin
 * interne renvoyes au navigateur).
 */
function fail(res, status, publicMsg, err, tag) {
  console.error("[" + (tag || "api") + "]", err);
  res.status(status).json({ error: publicMsg });
}

module.exports = { fail };
