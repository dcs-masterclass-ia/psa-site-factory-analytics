/**
 * Authentification serveur-a-serveur Google (JWT Bearer, compte de
 * service) -- zero dependance (crypto natif de Node), meme discipline que
 * le reste du repo (cf. api/_lib/auth.js). Reutilisable pour toute API
 * Google necessitant ce compte de service (Search Console pour l'instant).
 *
 * Variable d'environnement Vercel a creer :
 *   GSC_SERVICE_ACCOUNT   contenu JSON complet de la cle du compte de
 *                         service (le meme que GA4_SERVICE_ACCOUNT cote
 *                         GitHub Actions -- deja autorise sur Search
 *                         Console par le pipeline existant, pas besoin
 *                         d'un nouvel acces).
 */

const crypto = require("crypto");

function b64url(bufOrStr) {
  return Buffer.from(bufOrStr).toString("base64url");
}

// cache memoire du jeton d'acces : persiste entre invocations sur une
// meme instance "chaude" (courant sur Vercel pour des appels rapproches),
// disparait sur une instance froide -- simple optimisation, pas critique
// pour la correction (un jeton expire est juste redemande).
let _cache = null; // { token, exp }

async function accessToken(scope) {
  if (_cache && _cache.scope === scope && _cache.exp > Date.now() + 60000) {
    return _cache.token;
  }

  const raw = process.env.GSC_SERVICE_ACCOUNT;
  if (!raw) throw new Error("GSC_SERVICE_ACCOUNT non configure sur le serveur (variable d'environnement Vercel).");
  let key;
  try {
    key = JSON.parse(raw);
  } catch (e) {
    throw new Error("GSC_SERVICE_ACCOUNT n'est pas un JSON valide.");
  }
  if (!key.private_key || !key.client_email) {
    throw new Error("GSC_SERVICE_ACCOUNT incomplet (private_key/client_email manquant).");
  }

  const now = Math.floor(Date.now() / 1000);
  const header = { alg: "RS256", typ: "JWT" };
  const claims = {
    iss: key.client_email,
    scope,
    aud: "https://oauth2.googleapis.com/token",
    iat: now,
    exp: now + 3600,
  };
  const unsigned = b64url(JSON.stringify(header)) + "." + b64url(JSON.stringify(claims));
  const signature = crypto.sign("RSA-SHA256", Buffer.from(unsigned), key.private_key);
  const jwt = unsigned + "." + b64url(signature);

  const r = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: "grant_type=" + encodeURIComponent("urn:ietf:params:oauth:grant-type:jwt-bearer") +
      "&assertion=" + encodeURIComponent(jwt),
  });
  const json = await r.json();
  if (!r.ok || !json.access_token) {
    throw new Error("Echec d'authentification Google : " + (json.error_description || json.error || r.status));
  }
  _cache = { token: json.access_token, exp: Date.now() + json.expires_in * 1000, scope };
  return _cache.token;
}

module.exports = { accessToken };
