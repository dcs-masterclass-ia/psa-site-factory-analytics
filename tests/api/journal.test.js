// Journal de connexion (api/_lib/journal.js) : sans réseau, magasin remplacé. Lancer : node --test tests/api/*.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("path");
const racine = path.resolve(__dirname, "../..");
const storePath = require.resolve(path.join(racine, "api/_lib/store.js"));
let fichier = null, panne = false;
require.cache[storePath] = { id: storePath, filename: storePath, loaded: true, exports: {
  readJson: async () => { if (panne) throw new Error("réseau"); return { data: fichier ? JSON.parse(JSON.stringify(fichier)) : null, sha: "1" }; },
  writeJson: async (_p, data) => { fichier = JSON.parse(JSON.stringify(data)); return { sha: "2" }; },
} };
const J = require(path.join(racine, "api/_lib/journal.js"));
const req = (h) => ({ headers: Object.assign({ "x-forwarded-for": "203.0.113.7, 10.0.0.1", "x-vercel-ip-country": "FR", "user-agent": "Mozilla/5.0" }, h) });

test("une connexion réussie est consignée avec adresse, pays et navigateur", async () => {
  fichier = null;
  await J.consigne(req(), { ok: true, email: "a@exemple.test" });
  assert.equal(fichier.evts.length, 1);
  assert.deepEqual([fichier.evts[0].ok, fichier.evts[0].email, fichier.evts[0].ip, fichier.evts[0].pays], [true, "a@exemple.test", "203.0.113.7", "FR"]);
});

test("un refus garde son motif, et le journal est plafonné à 2000 lignes", async () => {
  fichier = { evts: Array.from({ length: 2000 }, (_, i) => ({ t: i, ok: true, email: "x" })) };
  await J.consigne(req(), { ok: false, motif: "compte_non_autorise", email: "z@gmail.com" });
  assert.equal(fichier.evts.length, 2000);
  assert.equal(fichier.evts[1999].motif, "compte_non_autorise");
  assert.equal(fichier.evts[0].t, 1);
});

test("une panne du magasin ne bloque jamais la connexion", async () => {
  panne = true;
  await assert.doesNotReject(() => J.consigne(req(), { ok: true, email: "a@exemple.test" }));
  panne = false;
});
