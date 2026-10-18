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
// Révision = variable Vercel C1ST_CODE_REV + compteur du bouton « Révoquer les accès » (c1st/revision.json du repo de données privé, lu avec 15 s de cache).
const { readJson, writeJson } = require("./store");
const FICHIER_REV = "c1st/revision.json";
let revStore = "0", revLu = 0;
function rev() { return String(process.env.C1ST_CODE_REV || "0") + ":" + revStore; }
/** À appeler avant tout calcul. Si la lecture échoue et qu'aucune valeur n'est connue : erreur (on refuse plutôt que d'ouvrir). */
async function charge() {
  if (Date.now() - revLu < 15000) return;
  try { const { data } = await readJson(FICHIER_REV); revStore = String((data && data.rev) || "0"); revLu = Date.now(); }
  catch (e) { if (!revLu) throw e; }
}
/** Bouton d'urgence : nouvelle révision -> nouveau code, tous les cookies invalidés (≤ 15 s sur les autres instances). */
async function revoque(par) {
  const { sha } = await readJson(FICHIER_REV);
  const nouvelle = Date.now().toString(36) + crypto.randomBytes(3).toString("hex");
  await writeJson(FICHIER_REV, { rev: nouvelle, at: new Date().toISOString(), par }, "chore(c1st): révocation des accès", sha);
  revStore = nouvelle; revLu = Date.now();
}

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
// Cookie « verrouillage automatique » : t0.ts.hmac(adresse, mois, révision, t0, ts). Valide 5 min après le dernier renouvellement (ts, renouvelé tant que la personne est active) et 4 h après la saisie du code (t0).
const INACTIVITE_MS = 5 * 60 * 1000, DUREE_MAX_MS = 4 * 3600 * 1000;
function valeurCookie(email, t0 = Date.now(), ts = Date.now(), mois = moisParis()) {
  return `${t0}.${ts}.` + hmac(`cookie|${String(email).toLowerCase()}|${mois}|${rev()}|${t0}|${ts}`).toString("hex");
}
/** -> { ok, t0 } */
function cookieValide(email, valeur, mois = moisParis(), now = Date.now()) {
  const [t0, ts, sig] = String(valeur || "").split(".");
  if (!/^\d+$/.test(t0 || "") || !/^\d+$/.test(ts || "") || !sig) return { ok: false };
  if (now - Number(ts) > INACTIVITE_MS || now - Number(t0) > DUREE_MAX_MS || Number(ts) > now + 60000) return { ok: false };
  const a = Buffer.from(sig), b = Buffer.from(valeurCookie(email, t0, ts, mois).split(".")[2]);
  return a.length === b.length && crypto.timingSafeEqual(a, b) ? { ok: true, t0: Number(t0) } : { ok: false };
}
const admins = () => (process.env.C1ST_ADMIN_EMAILS || "").split(",").map((e) => e.trim().toLowerCase()).filter(Boolean);

module.exports = { charge, revoque, _setRev: (v) => { revStore = v; revLu = Date.now(); }, codeDuMois, codeValide, valeurCookie, cookieValide, moisParis, INACTIVITE_MS, admins, normalise };
