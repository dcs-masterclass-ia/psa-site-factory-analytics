// Page Paramètres : validation des préférences (sans réseau : on teste le nettoyage via un faux store).
const test = require("node:test");
const assert = require("node:assert");
const path = require("path");

const store = path.join(__dirname, "..", "..", "api", "_lib", "store.js");
const auth = path.join(__dirname, "..", "..", "api", "_lib", "auth.js");
let fichiers = {};
require.cache[require.resolve(store)] = { id: store, filename: store, loaded: true, exports: {
  readJson: async (f) => ({ data: fichiers[f] || null, sha: fichiers[f] ? "s" : null }),
  writeJson: async (f, d) => { fichiers[f] = d; },
} };
require.cache[require.resolve(auth)] = { id: auth, filename: auth, loaded: true, exports: {
  verifySessionFromRequest: (req) => req.session || null,
} };
const handler = require("../../api/preferences.js");

const res = () => { const r = { code: 200, body: null, headers: {} }; r.status = (c) => { r.code = c; return r; }; r.json = (b) => { r.body = b; return r; }; r.setHeader = (k, v) => { r.headers[k] = v; }; return r; };

test("préférences : refuse sans session", async () => {
  const r = res(); await handler({ method: "GET" }, r); assert.strictEqual(r.code, 401);
});

test("préférences : ne garde que des valeurs connues et borne le périmètre", async () => {
  fichiers = {};
  const s = { email: "m@exemple.test", role: "full" };
  const r = res();
  await handler({ method: "PUT", session: s, body: { prefs: { theme: "dark", lang: "xx", accueil: "tb", periode: "7", comparaison: "year", avatar: "qa",
    perimetre: { mode: "sites", sites: ["OPEL FR", "OPEL FR", "", "PEUGEOT FR"] }, injecte: "<script>" } } }, r);
  assert.strictEqual(r.code, 200);
  assert.deepStrictEqual(r.body.prefs, { theme: "dark", accueil: "tb", periode: "7", comparaison: "year", avatar: "qa", perimetre: { mode: "sites", sites: ["OPEL FR", "PEUGEOT FR"] } });
  const g = res(); await handler({ method: "GET", session: s }, g);
  assert.deepStrictEqual(g.body.prefs, r.body.prefs);
});
