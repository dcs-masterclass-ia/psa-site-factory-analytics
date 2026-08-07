/**
 * Signature/verification des cookies de session (Node, cote fonctions
 * serverless). Le meme secret AUTH_COOKIE_SECRET est utilise cote
 * middleware.js (Edge Runtime, Web Crypto) -- les deux calculent le meme
 * HMAC-SHA256, seule l'API differe.
 */

const crypto = require("crypto");

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

function verifySessionFromRequest(req) {
  const cookies = parseCookies(req.headers.cookie);
  return verify(cookies.psf_session);
}

module.exports = { sign, verify, parseCookies, verifySessionFromRequest };
