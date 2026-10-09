/**
 * Signature/verification des cookies de session (Node, cote fonctions
 * serverless). Le meme secret AUTH_COOKIE_SECRET est utilise cote
 * middleware.js (Edge Runtime, Web Crypto) -- les deux calculent le meme
 * HMAC-SHA256, seule l'API differe.
 */

const crypto = require("crypto");

// Duree de vie absolue d'une session : 1 h, puis reconnexion Google. verify()
// refuse aussi tout jeton dont l'expiration depasse cette fenetre (+60 s de
// tolerance d'horloge), ce qui invalide d'un coup les anciens cookies de 7 j.
const MAX_SESSION_MS = 60 * 60 * 1000;

function b64url(str) {
  return Buffer.from(str, "utf8").toString("base64url");
}
function fromB64url(str) {
  return Buffer.from(str, "base64url").toString("utf8");
}

function sign(payloadObj) {
  const secret = process.env.AUTH_COOKIE_SECRET;
  if (!secret) throw new Error("AUTH_COOKIE_SECRET non configure sur le serveur.");
  const payload = b64url(JSON.stringify(payloadObj));
  const sig = crypto.createHmac("sha256", secret).update(payload).digest("hex");
  return payload + "." + sig;
}

function verify(token) {
  try {
    const secret = process.env.AUTH_COOKIE_SECRET;
    if (!secret || !token) return null;
    const idx = token.lastIndexOf(".");
    if (idx < 0) return null;
    const payload = token.slice(0, idx);
    const sig = token.slice(idx + 1);
    const expected = crypto.createHmac("sha256", secret).update(payload).digest("hex");
    const a = Buffer.from(expected);
    const b = Buffer.from(sig);
    if (a.length !== b.length || !crypto.timingSafeEqual(a, b)) return null;
    const data = JSON.parse(fromB64url(payload));
    if (!data.exp || Date.now() > data.exp) return null;
    if (data.exp - Date.now() > MAX_SESSION_MS + 60 * 1000) return null;
    return data;
  } catch (e) {
    return null;
  }
}

function parseCookies(header) {
  const out = {};
  (header || "").split(";").forEach(part => {
    const i = part.indexOf("=");
    if (i < 0) return;
    out[part.slice(0, i).trim()] = decodeURIComponent(part.slice(i + 1).trim());
  });
  return out;
}

// Roles. ALLOWED_EMAILS = acces complet ; LIMITED_EMAILS = GA4 / Search Console /
// PageSpeed uniquement (jamais les leads back-office). Aucune des deux definie
// = comportement historique (controle de domaine a la connexion, tout le monde
// "full"). Des qu'une liste est definie, seules les adresses listees passent.
function parseList(v) {
  return (v || "").split(",").map(e => e.trim().toLowerCase()).filter(Boolean);
}
function allowedEmails() { return parseList(process.env.ALLOWED_EMAILS); }
function limitedEmails() { return parseList(process.env.LIMITED_EMAILS); }

function roleFor(email) {
  const full = allowedEmails(), limited = limitedEmails();
  if (!full.length && !limited.length) return "full";
  const e = String(email || "").toLowerCase();
  if (full.includes(e)) return "full";
  if (limited.includes(e)) return "limited";
  return null;
}

function isEmailAllowed(email) { return roleFor(email) !== null; }

function verifySessionFromRequest(req) {
  const cookies = parseCookies(req.headers.cookie);
  const session = verify(cookies.psf_session);
  if (!session) return null;
  const role = roleFor(session.email);
  if (!role) return null;
  return { ...session, role };
}

module.exports = { MAX_SESSION_MS, sign, verify, parseCookies, verifySessionFromRequest, allowedEmails, limitedEmails, roleFor, isEmailAllowed };
