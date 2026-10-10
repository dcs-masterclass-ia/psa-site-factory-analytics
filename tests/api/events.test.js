// api/events.js sans réseau (magasin et session simulés). node --test tests/api/events.test.js
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
const handler = require(path.join(racine, "api/events.js"));
const appelle = (method, body) => new Promise(resolve => {
  const res = { code: 200, setHeader() {}, status(c) { this.code = c; return this; }, json(o) { resolve({ code: this.code, body: o }); } };
  handler({ method, body, headers: {} }, res);
});

test("session absente : 401", async () => {
  const s = session; session = null;
  assert.equal((await appelle("GET")).code, 401);
  session = s;
});

test("création, lecture triée, mise à jour, suppression", async () => {
  const c = await appelle("POST", { action: "save", event: { date: "2026-09-02", type: "campagne", titre: "Lancement Search Q3", sites: ["PEUGEOT FR"] } });
  assert.equal(c.code, 200);
  assert.match(c.body.event.id, /^E-/);
  await appelle("POST", { action: "save", event: { date: "2026-10-01", type: "v2", titre: "Bascule V2 FR", fin: "2026-09-01" } });   // fin < date : ignorée
  const l = await appelle("GET");
  assert.equal(l.body.events.length, 2);
  assert.equal(l.body.events[0].date, "2026-10-01");           // plus récent d'abord
  assert.equal(l.body.events[0].fin, null);
  const u = await appelle("POST", { action: "save", event: { id: c.body.event.id, date: "2026-09-03", titre: "Lancement Search Q3 (décalé)", type: "inconnu" } });
  assert.equal(u.body.event.type, "autre");
  assert.equal(u.body.event.date, "2026-09-03");
  assert.equal((await appelle("POST", { action: "delete", id: c.body.event.id })).code, 200);
  assert.equal((await appelle("GET")).body.events.length, 1);
});

test("validation et droits : profil limité en lecture seule", async () => {
  assert.equal((await appelle("POST", { action: "save", event: { date: "pas-une-date", titre: "xxx" } })).code, 400);
  assert.equal((await appelle("POST", { action: "save", event: { date: "2026-09-02", titre: "x" } })).code, 400);
  assert.equal((await appelle("POST", { action: "delete", id: "E-nope" })).code, 404);
  session = { email: "limite@autobiz.com", role: "limited" };
  assert.equal((await appelle("GET")).code, 200);
  assert.equal((await appelle("GET")).body.peutEcrire, false);
  assert.equal((await appelle("POST", { action: "save", event: { date: "2026-09-02", titre: "Interdit" } })).code, 403);
  session = { email: "m.foureau@autobiz.com", role: "full" };
});
