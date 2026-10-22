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
 *   ALLOWED_EMAILS       (optionnel) liste blanche d'adresses separees par des
 *                        virgules ; si definie, elle remplace le controle de domaine
 *   AUTH_COOKIE_SECRET   secret aleatoire (ex. `openssl rand -hex 32`)
 */

const { sign, allowedEmails, limitedEmails, roleFor, presentationsAllowed, MAX_SESSION_MS } = require("./_lib/auth");
const { fail } = require("./_lib/errors");
const C1 = require("./_lib/c1st-acces");
const J = require("./_lib/journal");

const MAX_AGE_S = MAX_SESSION_MS / 1000; // 1 h, voir _lib/auth.js

module.exports = async function handler(req, res) {
  if (req.method !== "POST") {
    res.status(405).json({ error: "Methode non autorisee." });
    return;
  }

  const clientId = process.env.GOOGLE_CLIENT_ID;
  const allowedDomain = (process.env.ALLOWED_DOMAIN || "").toLowerCase();
  const allowList = allowedEmails().concat(limitedEmails());
  if (!clientId || (!allowedDomain && !allowList.length)) {
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
      await J.consigne(req, { ok: false, motif: "jeton_invalide" });
      res.status(403).json({ error: "Jeton Google invalide." });
      return;
    }
    if (info.aud !== clientId) {
      await J.consigne(req, { ok: false, motif: "jeton_audience" });
      res.status(403).json({ error: "Jeton Google invalide (audience)." });
      return;
    }
    if (info.iss !== "accounts.google.com" && info.iss !== "https://accounts.google.com") {
      await J.consigne(req, { ok: false, motif: "jeton_emetteur" });
      res.status(403).json({ error: "Jeton Google invalide (emetteur)." });
      return;
    }
    if (info.email_verified !== "true") {
      await J.consigne(req, { ok: false, motif: "email_non_verifie" });
      res.status(403).json({ error: "Email Google non verifie." });
      return;
    }
    const email = String(info.email || "").toLowerCase();
    if (allowList.length) {
      if (!roleFor(email)) {
        await J.consigne(req, { ok: false, motif: "compte_non_autorise", email });
        res.status(403).json({ error: "Acces reserve aux comptes autorises." });
        return;
      }
    } else if (!email.endsWith("@" + allowedDomain)) {
      await J.consigne(req, { ok: false, motif: "domaine_non_autorise", email });
      res.status(403).json({ error: `Acces reserve aux comptes @${allowedDomain}.` });
      return;
    }

    try { if (await C1.estSuspendu(email)) { await J.consigne(req, { ok: false, motif: "suspendu", email }); res.status(403).json({ error: "Acces suspendu. Contacte l'administrateur." , suspendu: true }); return; } }
    catch (e) { console.error("[auth] liste de suspensions illisible", e); }       // illisible : on n'empêche pas la connexion, le middleware revérifie
    await J.consigne(req, { ok: true, email });
    const token = sign({ email, exp: Date.now() + MAX_AGE_S * 1000 });
    res.setHeader("Set-Cookie", [
      `psf_session=${token}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${MAX_AGE_S}`,
      `psf_user_email=${encodeURIComponent(email)}; Path=/; Secure; SameSite=Lax; Max-Age=${MAX_AGE_S}`,
      // pour l'interface seulement (masquer les onglets) ; l'acces reel est
      // controle cote serveur a chaque requete (middleware + api/data.js)
      `psf_role=${roleFor(email) === "limited" ? "limited" : "full"}; Path=/; Secure; SameSite=Lax; Max-Age=${MAX_AGE_S}`,
      // fonctionnalités verrouillées (interface seulement ; contrôle réel côté serveur) : « pres » = onglet Présentations
      `psf_feat=${presentationsAllowed(email) ? "pres" : ""}; Path=/; Secure; SameSite=Lax; Max-Age=${MAX_AGE_S}`,
    ]);
    res.status(200).json({ ok: true, email });
  } catch (e) {
    fail(res, 500, "Erreur d'authentification.", e, "auth");
  }
};
