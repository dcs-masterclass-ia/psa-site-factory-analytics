// api/presentations.js sans réseau (magasin et session simulés). node --test tests/api/presentations.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("path");
const racine = path.resolve(__dirname, "../..");
const storePath = require.resolve(path.join(racine, "api/_lib/store.js"));
const authPath = require.resolve(path.join(racine, "api/_lib/auth.js"));
let fichier = null, sha = 0, session = null;
require.cache[storePath] = { id: storePath, filename: storePath, loaded: true, exports: {
  readJson: async () => ({ data: fichier ? JSON.parse(JSON.stringify(fichier)) : null, sha: String(sha) }),
  writeJson: async (_p, d) => { fichier = JSON.parse(JSON.stringify(d)); sha++; return { sha: String(sha) }; } } };
const vraiAuth = require(authPath);
require.cache[authPath].exports = { ...vraiAuth, verifySessionFromRequest: () => session };
const handler = require(path.join(racine, "api/presentations.js"));
const appelle = (method, body) => new Promise(resolve => {
  const res = { code: 200, setHeader() {}, status(c) { this.code = c; return this; }, json(o) { resolve({ code: this.code, body: o }); } };
  handler({ method, body, headers: {} }, res);
});
const brief = { titre: "Stellantis BELUX T3-2026", client: "Stellantis", langue: "en", perimetre: { pays: ["be", "LU"], marques: ["Peugeot", "Citroën"] },
  periode: { annee: 2026, trimestre: 3 }, comparaisons: { qoq: true, yoy: true }, modules: ["global", "trafic_marque", "inconnu"],
  contact: { nom: "B. Moumni", fonction: "DKAM", email: "b.moumni@autobiz.com" },
  pointsOuverts: [{ titre: "Pop-in", texte: "À déployer" }, { titre: "", texte: "" }],
  prochainesEtapes: [{ item: "Promo Master", responsable: "autobiz", statut: "en_cours", echeance: "sept-26" }, { item: "", responsable: "x" }], commentaire: "RAS" };
test.beforeEach(() => { fichier = null; sha = 0; session = { email: "m.foureau@autobiz.com", role: "full" }; });

test("sans session 401, profil limité 403", async () => {
  session = null; assert.equal((await appelle("GET")).code, 401);
  session = { email: "b.moumni@autobiz.com", role: "limited" };
  assert.equal((await appelle("GET")).code, 403);
  assert.equal((await appelle("POST", { action: "save", brief })).code, 403);
});
test("création : nettoyée (pays en majuscules, module inconnu et lignes vides retirés)", async () => {
  const r = await appelle("POST", { action: "save", brief });
  assert.equal(r.code, 200);
  const b = r.body.brief;
  assert.match(b.id, /^B-/); assert.equal(b.statut, "brouillon");
  assert.deepEqual(b.perimetre.pays, ["BE", "LU"]);
  assert.deepEqual(b.modules, ["global", "trafic_marque"]);
  assert.equal(b.pointsOuverts.length, 1); assert.equal(b.prochainesEtapes.length, 1);
  assert.equal(b.auteur, "m.foureau@autobiz.com");
});
test("validation : titre, client, pays, période, modules", async () => {
  for (const m of [{ titre: "" }, { client: "" }, { perimetre: { pays: [] } }, { periode: { annee: 1999, trimestre: 9 } }, { modules: ["x"] }])
    assert.equal((await appelle("POST", { action: "save", brief: { ...brief, ...m } })).code, 400);
  assert.equal(fichier, null);
});
test("mise à jour par id, autre auteur peut modifier, introuvable = 404", async () => {
  const c = await appelle("POST", { action: "save", brief });
  session = { email: "autre@autobiz.com", role: "full" };
  const u = await appelle("POST", { action: "save", brief: { ...brief, id: c.body.brief.id, titre: "Titre modifié" } });
  assert.equal(u.body.brief.titre, "Titre modifié"); assert.equal(u.body.brief.modifiePar, "autre@autobiz.com");
  assert.equal(fichier.briefs.length, 1);
  assert.equal((await appelle("POST", { action: "save", brief: { ...brief, id: "B-nope" } })).code, 404);
});
test("suppression : l'auteur seulement", async () => {
  const c = await appelle("POST", { action: "save", brief });
  session = { email: "autre@autobiz.com", role: "full" };
  assert.equal((await appelle("POST", { action: "delete", id: c.body.brief.id })).code, 403);
  session = { email: "m.foureau@autobiz.com", role: "full" };
  assert.equal((await appelle("POST", { action: "delete", id: c.body.brief.id })).code, 200);
  assert.equal(fichier.briefs.length, 0);
});
test("entrées hostiles tronquées, GET trié", async () => {
  const r = await appelle("POST", { action: "save", brief: { ...brief, titre: "T".repeat(500), commentaire: "C".repeat(9999) } });
  assert.equal(r.body.brief.titre.length, 120); assert.equal(r.body.brief.commentaire.length, 2000);
  assert.equal((await appelle("GET")).body.briefs.length, 1);
  assert.equal((await appelle("PUT")).code, 405);
});
