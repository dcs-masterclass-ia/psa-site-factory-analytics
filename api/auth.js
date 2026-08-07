/**
 * Verifie le jeton d'identite Google (ID token JWT) envoye par le client
 * apres connexion via Google Identity Services, et pose un cookie de
 * session signe si le compte appartient au domaine autorise.
 *
 * Verification du jeton via l'endpoint tokeninfo de Google (Google verifie
 * la signature pour nous et renvoie les claims decodes) -- meme discipline
 * zero-dependance (fetch brut) que le reste du repo, largement suffisant
 * pour le volume d'authentification d'un outil interne.
 *
 * Variables d'environnement Vercel a creer :
 *   GOOGLE_CLIENT_ID     client OAuth Google (Web application)
 *   ALLOWED_DOMAIN       domaine autorise, ex. autobiz.com
 *   AUTH_COOKIE_SECRET   secret aleatoire (ex. `openssl rand -hex 32`)
 */

const { sign } = require("./_lib/auth");

const MAX_AGE_S = 60 * 60 * 24 * 7; // 7 jours

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.status(405).json({ error: "Methode non autorisee." });
    return;
  }

  const clientId = process.env.GOOGLE_CLIENT_ID;
  const allowedDomain = (process.env.ALLOWED_DOMAIN || "").toLowerCase();
  if (!clientId || !allowedDomain) {
    res.status(500).json({ error: "Configuration serveur incomplete (GOOGLE_CLIENT_ID / ALLOWED_DOMAIN)." });
    return;
  }

  const { credential } = req.body || {};
  if (!credential) {
    res.status(400).json({ error: "credential manquant." });
    return;
  }

  try {
    const r = await fetch("https://oauth2.googleapis.com/tokeninfo?id_token=" + encodeURIComponent(credential));
    const info = await r.json();
    if (!r.ok || info.error) {
      res.status(403).json({ error: "Jeton Google invalide." });
      return;
    }
    if (info.aud !== clientId) {
      res.status(403).json({ error: "Jeton Google invalide (audience)." });
      return;
    }
    if (info.iss !== "accounts.google.com" && info.iss !== "https://accounts.google.com") {
      res.status(403).json({ error: "Jeton Google invalide (emetteur)." });
      return;
    }
    if (info.email_verified !== "true") {
      res.status(403).json({ error: "Email Google non verifie." });
      return;
    }
    const email = String(info.email || "").toLowerCase();
    if (!email.endsWith("@" + allowedDomain)) {
      res.status(403).json({ error: `Acces reserve aux comptes @${allowedDomain}.` });
      return;
    }

    const token = sign({ email, exp: Date.now() + MAX_AGE_S * 1000 });
    res.setHeader("Set-Cookie", [
      `psf_session=${token}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${MAX_AGE_S}`,
      `psf_user_email=${encodeURIComponent(email)}; Path=/; Secure; SameSite=Lax; Max-Age=${MAX_AGE_S}`,
    ]);
    res.status(200).json({ ok: true, email });
  } catch (e) {
    res.status(500).json({ error: String(e && e.message ? e.message : e) });
  }
};
