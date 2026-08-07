/**
 * Vercel Edge Middleware -- s'execute sur CHAQUE requete pour les chemins
 * du matcher ci-dessous, avant meme les fichiers statiques. C'est la seule
 * facon de proteger reellement data/*.json (servis statiquement) : un
 * simple ecran de connexion cote client dans index.html ne bloque rien
 * puisque n'importe qui peut recuperer les JSON directement par leur URL.
 *
 * Runtime Edge = Web Crypto (crypto.subtle), pas le module Node "crypto" --
 * cf. api/_lib/auth.js pour l'equivalent Node qui signe le meme cookie.
 */

export const config = {
  matcher: ["/data/:path*", "/api/agent", "/api/refresh"],
};

function parseCookies(header) {
  const out = {};
  (header || "").split(";").forEach(part => {
    const i = part.indexOf("=");
    if (i < 0) return;
    out[part.slice(0, i).trim()] = decodeURIComponent(part.slice(i + 1).trim());
  });
  return out;
}

async function hmacHex(secret, message) {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]
  );
  const sigBuf = await crypto.subtle.sign("HMAC", key, enc.encode(message));
  return [...new Uint8Array(sigBuf)].map(b => b.toString(16).padStart(2, "0")).join("");
}

function b64urlDecode(str) {
  const pad = str.length % 4 === 0 ? "" : "=".repeat(4 - (str.length % 4));
  const b64 = str.replace(/-/g, "+").replace(/_/g, "/") + pad;
  return atob(b64);
}

async function verifySession(token, secret) {
  if (!token || !secret) return null;
  const idx = token.lastIndexOf(".");
  if (idx < 0) return null;
  const payload = token.slice(0, idx);
  const sig = token.slice(idx + 1);
  const expected = await hmacHex(secret, payload);
  if (expected !== sig) return null;
  try {
    const data = JSON.parse(b64urlDecode(payload));
    if (!data.exp || Date.now() > data.exp) return null;
    return data;
  } catch (e) {
    return null;
  }
}

export default async function middleware(request) {
  const secret = process.env.AUTH_COOKIE_SECRET;
  const cookies = parseCookies(request.headers.get("cookie"));
  const session = await verifySession(cookies.psf_session, secret);
  if (session) return; // laisse passer

  return new Response(JSON.stringify({ error: "Non authentifie." }), {
    status: 401,
    headers: { "content-type": "application/json" },
  });
}
