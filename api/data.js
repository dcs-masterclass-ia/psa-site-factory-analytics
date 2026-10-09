/**
 * Sert data/<nom>.json. Les comptes au profil "limited" (GA4 / Search Console
 * / PageSpeed) ne peuvent pas lire /data/* directement (le middleware les
 * refuse) : ils passent ici, et la reponse est nettoyee de toute donnee leads
 * back-office. Les comptes "full" recoivent le fichier tel quel.
 */

const fs = require("fs");
const path = require("path");
const { verifySessionFromRequest } = require("./_lib/auth");
const { stripLeads } = require("./_lib/limited");
const { fail } = require("./_lib/errors");

const NAME_RE = /^[a-z0-9][a-z0-9-]{0,80}$/;

module.exports = async function handler(req, res) {
  if (req.method !== "GET") {
    res.status(405).json({ error: "Methode non autorisee." });
    return;
  }
  const session = verifySessionFromRequest(req);
  if (!session) {
    res.status(401).json({ error: "Non authentifie." });
    return;
  }
  const name = String((req.query && req.query.f) || "").replace(/\.json$/, "");
  if (!NAME_RE.test(name)) {
    res.status(400).json({ error: "Nom de fichier invalide." });
    return;
  }
  const file = path.join(process.cwd(), "data", name + ".json");
  if (!fs.existsSync(file)) {
    res.status(404).json({ error: "Introuvable." });
    return;
  }
  try {
    let data = JSON.parse(fs.readFileSync(file, "utf8"));
    if (session.role === "limited") {
      data = stripLeads(data);
    }
    res.setHeader("Cache-Control", "private, no-store");
    res.status(200).json(data);
  } catch (e) {
    fail(res, 500, "Donnees indisponibles.", e, "data");
  }
};
