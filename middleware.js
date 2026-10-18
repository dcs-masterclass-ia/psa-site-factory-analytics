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

// Protection par defaut : TOUTE route /api/* exige une session, sauf les trois
// points d'entree publics (connexion, config OAuth, deconnexion). Une future
// route oubliee ici reste donc fermee. /data/* (JSON business) idem.
export const config = {
  matcher: ["/data/:path*", "/api/((?!auth$|config$|logout$|ticket-decision$).*)"],
};

// Meme valeur que MAX_SESSION_MS dans api/_lib/auth.js (1 h absolue).
const MAX_SESSION_MS = 60 * 60 * 1000;

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
    if (data.exp - Date.now() > MAX_SESSION_MS + 60 * 1000) return null;
    return data;
  } catch (e) {
    return null;
  }
}

// Roles : memes regles que roleFor() dans api/_lib/auth.js (a garder alignees).
function parseList(v) {
  return (v || "").split(",").map(e => e.trim().toLowerCase()).filter(Boolean);
}
function roleFor(email) {
  const full = parseList(process.env.ALLOWED_EMAILS), limited = parseList(process.env.LIMITED_EMAILS);
  if (!full.length && !limited.length) return "full";
  const e = String(email || "").toLowerCase();
  if (full.includes(e)) return "full";
  if (limited.includes(e)) return "limited";
  return null;
}

// Profil "limited" (GA4 / Search Console / PageSpeed) : jamais /data/* en
// direct (il passe par /api/data, qui retire les leads back-office), et
// seulement ces routes API.
const LIMITED_API = ["/api/data", "/api/gsc-compare", "/api/gsc-page-queries", "/api/perf-ticket", "/api/tickets", "/api/events", "/api/alertes", "/api/indexation", "/api/preferences"];

// Code d'accès mensuel C1ST : meme calcul que api/_lib/c1st-acces.js (cookie psf_c1st = HMAC(adresse, mois de Paris, revision)).
function moisParis() {
  const p = new Intl.DateTimeFormat("fr-CA", { timeZone: "Europe/Paris", year: "numeric", month: "2-digit" }).formatToParts(new Date());
  return p.find(x => x.type === "year").value + "-" + p.find(x => x.type === "month").value;
}
// Compteur du bouton « Révoquer les accès » (c1st/revision.json du repo de donnees prive), 15 s de cache ; illisible et jamais lu -> on refuse.
let revStore = null, revLu = 0;
async function revisionC1st() {
  if (revStore !== null && Date.now() - revLu < 15000) return revStore;
  try {
    const r = await fetch(`https://api.github.com/repos/${process.env.KAMIA_STORE_REPO || "dcs-masterclass-ia/psa-site-factory-data"}/contents/c1st/revision.json?ref=${process.env.KAMIA_STORE_BRANCH || "main"}`,
      { headers: { Authorization: `Bearer ${process.env.DATA_REPO_TOKEN}`, Accept: "application/vnd.github.raw+json", "X-GitHub-Api-Version": "2022-11-28" } });
    if (r.status === 404) { revStore = "0"; revLu = Date.now(); }
    else if (r.ok) { const j = await r.json(); revStore = String((j && j.rev) || "0"); revLu = Date.now(); }
  } catch (e) { /* garde la derniere valeur connue */ }
  return revStore;
}
async function cookieC1stValide(email, valeur) {
  const s = process.env.C1ST_CODE_SECRET || process.env.AUTH_COOKIE_SECRET;
  const rs = await revisionC1st();
  const [t0, ts, sig] = String(valeur || "").split(".");
  if (!s || rs === null || !/^\d+$/.test(t0 || "") || !/^\d+$/.test(ts || "") || !sig) return false;
  const now = Date.now();
  // 5 min d'inactivite max (cookie renouvele tant que la personne est active), 4 h au plus apres la saisie du code : memes bornes que api/_lib/c1st-acces.js
  if (now - Number(ts) > 5 * 60 * 1000 || now - Number(t0) > 4 * 3600 * 1000 || Number(ts) > now + 60000) return false;
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey("raw", enc.encode(s + "|c1st"), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const buf = await crypto.subtle.sign("HMAC", key, enc.encode(`cookie|${String(email).toLowerCase()}|${moisParis()}|${process.env.C1ST_CODE_REV || "0"}:${rs}|${t0}|${ts}`));
  const attendu = [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0")).join("");
  if (attendu.length !== sig.length) return false;
  let diff = 0;
  for (let i = 0; i < attendu.length; i++) diff |= attendu.charCodeAt(i) ^ sig.charCodeAt(i);
  return diff === 0;
}

const json = (status, body) => new Response(JSON.stringify(body), {
  status,
  headers: { "content-type": "application/json" },
});

export default async function middleware(request) {
  // Defense en profondeur : l'historique profond et les conversations KamIA ne
  // sont jamais servis en statique (scripts/fetch-data.sh les retire deja du
  // deploiement) ; 404 quoi qu'il arrive, meme avec une session valide.
  if (/^\/data\/(history|kamia)(\/|$)/i.test(new URL(request.url).pathname)) {
    return json(404, { error: "Introuvable." });
  }
  // Maintenance (MAINTENANCE=1) : plus aucune donnee ni API, quel que soit le profil.
  // La page, elle, reste accessible (voilee et bloquee, cf. index.html).
  if (/^(1|true|oui)$/i.test(process.env.MAINTENANCE || "")) {
    return new Response(JSON.stringify({ error: "Maintenance en cours.", maintenance: true }), {
      status: 503,
      headers: { "content-type": "application/json", "retry-after": "300", "cache-control": "no-store" },
    });
  }
  const secret = process.env.AUTH_COOKIE_SECRET;
  const cookies = parseCookies(request.headers.get("cookie"));
  const session = await verifySession(cookies.psf_session, secret);
  const role = session ? roleFor(session.email) : null;
  if (!role) return json(401, { error: "Non authentifie." });
  // C1ST (données CRM Salesforce) : réservé aux adresses de PRESENTATIONS_EMAILS, comme l'onglet Présentations.
  if (/^\/data\/c1st(\/|$)/i.test(new URL(request.url).pathname) && !parseList(process.env.PRESENTATIONS_EMAILS).includes(String(session.email || "").toLowerCase())) {
    return json(403, { error: "Acces non autorise pour ce profil." });
  }
  if (/^\/data\/c1st(\/|$)/i.test(new URL(request.url).pathname) && !(await cookieC1stValide(session.email, cookies.psf_c1st))) {
    return json(403, { error: "Code d'acces C1ST requis.", code: "c1st_code" });
  }
  if (role === "limited") {
    const path = new URL(request.url).pathname.replace(/\/+$/, "");
    if (!LIMITED_API.includes(path)) return json(403, { error: "Acces non autorise pour ce profil." });
  }
  return; // laisse passer
}
