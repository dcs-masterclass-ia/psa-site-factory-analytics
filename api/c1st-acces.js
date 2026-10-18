/**
 * Accès à l'onglet C1ST : code mensuel (voir _lib/c1st-acces.js).
 *   GET              -> { ouvert, admin }          (ouvert = cookie psf_c1st valide ce mois-ci)
 *   GET ?code=1      -> { code }                   (adresses de C1ST_ADMIN_EMAILS seulement : pour le communiquer à l'équipe)
 *   POST { code }    -> 200 + cookie psf_c1st      (5 essais / 15 min par adresse et par IP, au mieux : mémoire de l'instance)
 *   POST { action:"revoquer" } -> (admin) nouvelle révision : nouveau code, tous les cookies invalidés ; renvoie le nouveau code
 *   DELETE           -> efface le cookie
 */
const { verifySessionFromRequest, parseCookies, presentationsAllowed } = require("./_lib/auth");
const A = require("./_lib/c1st-acces");
const { fail } = require("./_lib/errors");

const essais = new Map();                       // clé -> [horodatages]
const FENETRE = 15 * 60 * 1000, MAX = 5;
function limite(cle) {
  const now = Date.now(), l = (essais.get(cle) || []).filter((t) => now - t < FENETRE);
  essais.set(cle, l);
  return l.length >= MAX;
}
const note = (cle) => essais.set(cle, [...(essais.get(cle) || []), Date.now()]);

module.exports = async function handler(req, res) {
  res.setHeader("cache-control", "no-store");
  const session = verifySessionFromRequest(req);
  if (!session || !session.email) { res.status(401).json({ error: "Non authentifie." }); return; }
  const email = String(session.email).toLowerCase();
  if (session.role !== "full" || !presentationsAllowed(email)) { res.status(403).json({ error: "Acces non autorise pour ce profil." }); return; }
  try {
    await A.charge();
    const cookies = parseCookies(req.headers.cookie);
    const ouvert = A.cookieValide(email, cookies.psf_c1st);
    const admin = A.admins().includes(email);
    if (req.method === "GET") {
      if (req.query && req.query.code && admin) { res.status(200).json({ code: A.codeDuMois(), mois: A.moisParis() }); return; }
      res.status(200).json({ ouvert, admin }); return;
    }
    if (req.method === "POST") {
      if (req.body && req.body.action === "revoquer") {
        if (!admin) { res.status(403).json({ error: "Acces non autorise pour ce profil." }); return; }
        await A.revoque(email);
        console.warn("[c1st-acces] accès révoqués par", email);
        res.setHeader("Set-Cookie", `psf_c1st=${A.valeurCookie(email)}; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=${A.secondesJusquaFinDeMois()}`);
        res.status(200).json({ ouvert: true, code: A.codeDuMois() }); return;
      }
      const ip = String((req.headers["x-forwarded-for"] || "").split(",")[0] || "ip").trim();
      const k1 = "e:" + email, k2 = "i:" + ip;
      if (limite(k1) || limite(k2)) { res.status(429).json({ error: "Trop d'essais. Réessaie dans 15 minutes." }); return; }
      const code = req.body && req.body.code;
      if (!A.codeValide(code)) {
        note(k1); note(k2);
        console.warn("[c1st-acces] code refusé pour", email);
        res.status(403).json({ error: "Code incorrect." }); return;
      }
      res.setHeader("Set-Cookie", `psf_c1st=${A.valeurCookie(email)}; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=${A.secondesJusquaFinDeMois()}`);
      res.status(200).json({ ouvert: true }); return;
    }
    if (req.method === "DELETE") {
      res.setHeader("Set-Cookie", "psf_c1st=; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=0");
      res.status(200).json({ ouvert: false }); return;
    }
    res.status(405).json({ error: "Methode non supportee." });
  } catch (e) {
    fail(res, 500, "Erreur serveur.", e, "c1st-acces");
  }
};
