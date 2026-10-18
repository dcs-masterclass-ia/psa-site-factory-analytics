/**
 * Code d'accès mensuel de l'onglet C1ST (en plus de la session Google et de PRESENTATIONS_EMAILS).
 * Le code est DÉRIVÉ, rien à stocker : HMAC(secret, "code|AAAA-MM|révision") ramené à 10 caractères lisibles.
 * Il change donc tout seul le 1er de chaque mois (heure de Paris). Révision d'urgence : changer la variable Vercel C1ST_CODE_REV
 * (n'importe quelle valeur) et redéployer : nouveau code et anciens cookies invalidés tout de suite.
 * Après saisie, un cookie psf_c1st (HMAC lié à l'adresse, au mois et à la révision) est posé jusqu'à la fin du mois ; middleware.js le revérifie
 * (même calcul, Web Crypto) avant de servir /data/c1st/*. Secret : C1ST_CODE_SECRET, à défaut AUTH_COOKIE_SECRET.
 */
const crypto = require("crypto");

const ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";   // sans I, O, 0, 1

function cle() {
  const s = process.env.C1ST_CODE_SECRET || process.env.AUTH_COOKIE_SECRET;
  if (!s) throw new Error("Secret du code C1ST non configuré.");
  return s + "|c1st";
}
function rev() { return String(process.env.C1ST_CODE_REV || "0"); }

/** « AAAA-MM » à Paris. */
function moisParis(date = new Date()) {
  const p = new Intl.DateTimeFormat("fr-CA", { timeZone: "Europe/Paris", year: "numeric", month: "2-digit" }).formatToParts(date);
  return p.find((x) => x.type === "year").value + "-" + p.find((x) => x.type === "month").value;
}
function hmac(message) { return crypto.createHmac("sha256", cle()).update(message).digest(); }

function codeDuMois(mois = moisParis()) {
  const b = hmac(`code|${mois}|${rev()}`);
  let out = "";
  for (let i = 0; i < 10; i++) out += ALPHABET[b[i] % ALPHABET.length];
  return out.slice(0, 5) + "-" + out.slice(5);
}
const normalise = (c) => String(c || "").toUpperCase().replace(/[^A-Z0-9]/g, "");

function codeValide(saisi, mois = moisParis()) {
  const a = Buffer.from(normalise(saisi)), b = Buffer.from(normalise(codeDuMois(mois)));
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}
function valeurCookie(email, mois = moisParis()) {
  return hmac(`cookie|${String(email).toLowerCase()}|${mois}|${rev()}`).toString("hex");
}
function cookieValide(email, valeur, mois = moisParis()) {
  const a = Buffer.from(String(valeur || "")), b = Buffer.from(valeurCookie(email, mois));
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}
/** Secondes jusqu'au début du mois suivant (Paris, approximé à 1 h près : le HMAC porte le mois, le cookie ne peut pas servir au mois suivant). */
function secondesJusquaFinDeMois() {
  const n = new Date(); const fin = new Date(Date.UTC(n.getUTCFullYear(), n.getUTCMonth() + 1, 1));
  return Math.max(60, Math.min(32 * 86400, Math.floor((fin - n) / 1000)));
}
const admins = () => (process.env.C1ST_ADMIN_EMAILS || "").split(",").map((e) => e.trim().toLowerCase()).filter(Boolean);

module.exports = { codeDuMois, codeValide, valeurCookie, cookieValide, moisParis, secondesJusquaFinDeMois, admins, normalise };
