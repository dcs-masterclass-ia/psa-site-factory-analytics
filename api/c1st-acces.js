/**
 * Accès à l'onglet C1ST : code mensuel (voir _lib/c1st-acces.js).
 *   GET              -> { ouvert, admin }          (ouvert = cookie psf_c1st valide ce mois-ci)
 *   GET ?code=1      -> { code }                   (adresses de C1ST_ADMIN_EMAILS seulement : pour le communiquer à l'équipe)
 *   POST { code }    -> 200 + cookie psf_c1st      (3 codes faux : adresse SUSPENDUE de tout le dashboard, voir _lib/c1st-acces.js ; réactivation par un admin)
 *   GET ?bans=1 / POST { action:"reactiver", email } -> (admin) liste des adresses suspendues / réactivation
 *   POST { action:"revoquer" } -> (admin) nouvelle révision : nouveau code, tous les cookies invalidés ; renvoie le nouveau code
 *   PATCH            -> renouvelle l'inactivité (5 min) tant que la personne est active ; 403 si déjà verrouillé
 *   DELETE           -> efface le cookie (« Verrouiller maintenant »)
 */
const { verifySessionFromRequest, parseCookies, presentationsAllowed } = require("./_lib/auth");
const A = require("./_lib/c1st-acces");
const { fail } = require("./_lib/errors");

module.exports = async function handler(req, res) {
  res.setHeader("cache-control", "no-store");
  const session = verifySessionFromRequest(req);
  if (!session || !session.email) { res.status(401).json({ error: "Non authentifie." }); return; }
  const email = String(session.email).toLowerCase();
  if (session.role !== "full" || !presentationsAllowed(email)) { res.status(403).json({ error: "Acces non autorise pour ce profil." }); return; }
  try {
    await A.charge();
    const cookies = parseCookies(req.headers.cookie);
    const ck = A.cookieValide(email, cookies.psf_c1st), ouvert = ck.ok;
    const admin = A.admins().includes(email);
    if (req.method === "GET") {
      if (req.query && req.query.bans && admin) { res.status(200).json({ bans: await A.listeBans() }); return; }
      if (req.query && req.query.code && admin) { res.status(200).json({ code: A.codeDuMois(), mois: A.moisParis() }); return; }
      res.status(200).json({ ouvert, admin }); return;
    }
    if (req.method === "POST") {
      if (req.body && req.body.action === "reactiver") {
        if (!admin) { res.status(403).json({ error: "Acces non autorise pour ce profil." }); return; }
        const ok = await A.reactive(String(req.body.email || ""));
        console.warn("[c1st-acces] réactivation de", req.body.email, "par", email, ok ? "" : "(inconnue)");
        res.status(200).json({ ok, bans: await A.listeBans() }); return;
      }
      if (req.body && req.body.action === "revoquer") {
        if (!admin) { res.status(403).json({ error: "Acces non autorise pour ce profil." }); return; }
        await A.revoque(email);
        console.warn("[c1st-acces] accès révoqués par", email);
        res.setHeader("Set-Cookie", `psf_c1st=${A.valeurCookie(email)}; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=${Math.ceil(A.INACTIVITE_MS / 1000)}`);
        res.status(200).json({ ouvert: true, code: A.codeDuMois() }); return;
      }
      const code = req.body && req.body.code;
      if (!A.codeValide(code)) {
        const r = await A.echec(email);
        console.warn("[c1st-acces] code refusé pour", email, r.suspendu ? "-> adresse suspendue" : "");
        if (r.suspendu) { res.status(403).json({ error: "Accès suspendu après 3 codes incorrects. Contacte l'administrateur.", suspendu: true }); return; }
        res.status(403).json({ error: `Code incorrect. Il te reste ${r.restants} essai${r.restants > 1 ? "s" : ""} avant la suspension de ton accès.` }); return;
      }
      await A.succes(email);
      res.setHeader("Set-Cookie", `psf_c1st=${A.valeurCookie(email)}; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=${Math.ceil(A.INACTIVITE_MS / 1000)}`);
      res.status(200).json({ ouvert: true }); return;
    }
    if (req.method === "PATCH") {                 // « je suis actif » : renouvelle les 5 minutes (jamais au-delà de 4 h après la saisie du code)
      if (!ouvert) { res.status(403).json({ error: "Verrouille.", verrouille: true }); return; }
      res.setHeader("Set-Cookie", `psf_c1st=${A.valeurCookie(email, ck.t0)}; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=${Math.ceil(A.INACTIVITE_MS / 1000)}`);
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
