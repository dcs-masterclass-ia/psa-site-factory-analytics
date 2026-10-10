// api/alertes.js sans réseau. node --test tests/api/alertes.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("path");
const racine = path.resolve(__dirname, "../..");
const storePath = require.resolve(path.join(racine, "api/_lib/store.js"));
const authPath = require.resolve(path.join(racine, "api/_lib/auth.js"));
let fichiers = {}, session = { email: "m.foureau@autobiz.com", role: "full" };
require.cache[storePath] = { id: storePath, filename: storePath, loaded: true, exports: {
  readJson: async p => ({ data: fichiers[p] ? JSON.parse(JSON.stringify(fichiers[p])) : null, sha: "s" }),
  writeJson: async (p, d) => { fichiers[p] = JSON.parse(JSON.stringify(d)); return { sha: "n" }; } } };
const vraiAuth = require(authPath);
require.cache[authPath].exports = { ...vraiAuth, verifySessionFromRequest: () => session };
const handler = require(path.join(racine, "api/alertes.js"));
const appelle = (method, body) => new Promise(resolve => {
  const res = { code: 200, setHeader() {}, status(c) { this.code = c; return this; }, json(o) { resolve({ code: this.code, body: o }); } };
  handler({ method, body, headers: {} }, res);
});

test("lecture : seuils par défaut, alertes du pipeline, profil limité en lecture seule", async () => {
  fichiers["alertes.json"] = { genere: "2026-10-10", alertes: [{ site: "OPEL FR", regle: "sessions", titre: "Chute des sessions" }] };
  session = { email: "l@autobiz.com", role: "limited" };
  const r = await appelle("GET");
  assert.equal(r.code, 200);
  assert.equal(r.body.config.sessionsPct, 25);
  assert.equal(r.body.alertes.length, 1);
  assert.equal(r.body.peutEcrire, false);
  assert.equal((await appelle("POST", { action: "save_config", config: { sessionsPct: 10 } })).code, 403);
  session = { email: "m.foureau@autobiz.com", role: "full" };
});

test("enregistrement des seuils : bornés et nettoyés", async () => {
  const r = await appelle("POST", { action: "save_config", config: { sessionsPct: 1, convPts: "2.5", etapePts: 999, volumeMin: "abc", notifier: true, inconnu: 5 } });
  assert.equal(r.code, 200);
  assert.deepEqual(r.body.config, { sessionsPct: 5, convPts: 2.5, etapePts: 30, fraicheurJours: 3, volumeMin: 500, notifier: true });
  assert.equal(fichiers["alertes/config.json"].config.notifier, true);
  assert.equal((await appelle("POST", { action: "autre" })).code, 400);
  assert.equal((await appelle("GET")).body.config.convPts, 2.5);
});
