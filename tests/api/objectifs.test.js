// api/objectifs.js sans réseau. node --test tests/api/objectifs.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("path");
const racine = path.resolve(__dirname, "../..");
const storePath = require.resolve(path.join(racine, "api/_lib/store.js"));
const authPath = require.resolve(path.join(racine, "api/_lib/auth.js"));
let fichier = null, sha = 0, session = { email: "m.foureau@autobiz.com", role: "full" };
require.cache[storePath] = { id: storePath, filename: storePath, loaded: true, exports: {
  readJson: async () => ({ data: fichier ? JSON.parse(JSON.stringify(fichier)) : null, sha: String(sha) }),
  writeJson: async (p, d) => { fichier = JSON.parse(JSON.stringify(d)); sha++; return { sha: String(sha) }; } } };
const vraiAuth = require(authPath);
require.cache[authPath].exports = { ...vraiAuth, verifySessionFromRequest: () => session };
const handler = require(path.join(racine, "api/objectifs.js"));
const appelle = (method, body) => new Promise(resolve => {
  const res = { code: 200, setHeader() {}, status(c) { this.code = c; return this; }, json(o) { resolve({ code: this.code, body: o }); } };
  handler({ method, body, headers: {} }, res);
});

test("profil limité : refusé ; session absente : 401", async () => {
  session = { email: "l@autobiz.com", role: "limited" };
  assert.equal((await appelle("GET")).code, 403);
  session = null;
  assert.equal((await appelle("GET")).code, 401);
  session = { email: "m.foureau@autobiz.com", role: "full" };
});

test("enregistrement fusionné, suppression d'une cible, validation", async () => {
  const a = await appelle("POST", { action: "save", annee: "2026", cibles: { "PEUGEOT FR": 120000, "OPEL FR": "55000.4" } });
  assert.equal(a.code, 200);
  assert.deepEqual(a.body.annees["2026"], { "PEUGEOT FR": 120000, "OPEL FR": 55000 });
  const b = await appelle("POST", { action: "save", annee: "2026", cibles: { "OPEL FR": null, "DS FR": 9000 } });
  assert.deepEqual(b.body.annees["2026"], { "PEUGEOT FR": 120000, "DS FR": 9000 });
  assert.equal((await appelle("POST", { action: "save", annee: "26", cibles: {} })).code, 400);
  assert.equal((await appelle("POST", { action: "autre" })).code, 400);
  assert.deepEqual((await appelle("GET")).body.annees["2026"], { "PEUGEOT FR": 120000, "DS FR": 9000 });
});
