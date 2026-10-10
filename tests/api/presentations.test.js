// api/presentations.js sans réseau (magasin et session simulés). node --test tests/api/presentations.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("path");
const racine = path.resolve(__dirname, "../..");
const storePath = require.resolve(path.join(racine, "api/_lib/store.js"));
const authPath = require.resolve(path.join(racine, "api/_lib/auth.js"));
let fichier = null, fichierTpl = null, sha = 0, session = null;
require.cache[storePath] = { id: storePath, filename: storePath, loaded: true, exports: {
  readJson: async p => { const f = p.includes("templates") ? fichierTpl : fichier; return { data: f ? JSON.parse(JSON.stringify(f)) : null, sha: String(sha) }; },
  writeJson: async (p, d) => { const c = JSON.parse(JSON.stringify(d)); if (p.includes("templates")) fichierTpl = c; else fichier = c; sha++; return { sha: String(sha) }; } } };
const vraiAuth = require(authPath);
require.cache[authPath].exports = { ...vraiAuth, verifySessionFromRequest: () => session };
const handler = require(path.join(racine, "api/presentations.js"));
const appelle = (method, body) => new Promise(resolve => {
  const res = { code: 200, setHeader() {}, status(c) { this.code = c; return this; }, json(o) { resolve({ code: this.code, body: o }); } };
  handler({ method, body, headers: {} }, res);
});
const brief = { titre: "Stellantis BELUX T3-2026", client: "Stellantis", langue: "en", perimetre: { pays: ["be", "LU"], marques: ["Peugeot", "Citroën"] },
  periode: { type: "trimestre", annee: 2026, indice: 3 }, comparaisons: { precedente: true, n1: true }, modules: ["global", "trafic_marque", "inconnu"],
  contact: { nom: "B. Moumni", fonction: "DKAM", email: "b.moumni@autobiz.com" },
  pointsOuverts: [{ titre: "Pop-in", texte: "À déployer" }, { titre: "", texte: "" }],
  prochainesEtapes: [{ item: "Promo Master", responsable: "autobiz", statut: "en_cours", echeance: "sept-26" }, { item: "", responsable: "x" }], commentaire: "RAS" };
test.beforeEach(() => { fichier = null; fichierTpl = null; sha = 0; session = { email: "m.foureau@autobiz.com", role: "full" }; });

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
  for (const m of [{ titre: "" }, { client: "" }, { perimetre: { pays: [] } }, { periode: { type: "trimestre", annee: 1999, indice: 9 } }, { modules: ["x"] }])
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

test("périodicités : mois, semestre, année ; indice hors bornes refusé ; ancien format lisible", async () => {
  const ok = async periode => (await appelle("POST", { action: "save", brief: { ...brief, periode } })).body;
  assert.deepEqual((await ok({ type: "mois", annee: 2026, indice: 9 })).brief.periode, { type: "mois", annee: 2026, indice: 9 });
  assert.deepEqual((await ok({ type: "semestre", annee: 2026, indice: 2 })).brief.periode, { type: "semestre", annee: 2026, indice: 2 });
  assert.deepEqual((await ok({ type: "annee", annee: 2025 })).brief.periode, { type: "annee", annee: 2025, indice: null });
  assert.equal((await appelle("POST", { action: "save", brief: { ...brief, periode: { type: "mois", annee: 2026, indice: 13 } } })).code, 400);
  assert.equal((await appelle("POST", { action: "save", brief: { ...brief, periode: { type: "trimestre", annee: 2026 } } })).code, 400);
  assert.deepEqual((await ok({ annee: 2026, trimestre: 2 })).brief.periode, { type: "trimestre", annee: 2026, indice: 2 });   // ancien format
  const ancien = await appelle("POST", { action: "save", brief: { ...brief, comparaisons: { qoq: true, yoy: false } } });
  assert.deepEqual(ancien.body.brief.comparaisons, { precedente: true, n1: false });
});

const modele = { nom: "BELUX trimestriel", description: "Reporting trimestriel Stellantis", config: { client: "Stellantis", langue: "en", periodicite: "trimestre",
  perimetre: { pays: ["be", "lu"], marques: [] }, comparaisons: { precedente: true, n1: true }, modules: ["global", "trafic_marque", "x"], contact: { nom: "B. Moumni" }, commentaire: "",
  periode: { type: "mois", annee: 2020, indice: 1 }, pointsOuverts: [{ titre: "ne doit pas être gardé", texte: "" }] } };

test("modèles : création nettoyée (sans période ni points ouverts), liste, mise à jour", async () => {
  const c = await appelle("POST", { action: "save_template", template: modele });
  assert.equal(c.code, 200);
  const t = c.body.template;
  assert.match(t.id, /^M-/);
  assert.deepEqual(t.config.perimetre.pays, ["BE", "LU"]);
  assert.deepEqual(t.config.modules, ["global", "trafic_marque"]);
  assert.equal(t.config.periodicite, "trimestre");
  assert.equal(t.config.periode, undefined); assert.equal(t.config.pointsOuverts, undefined);
  const l = await appelle("GET");
  assert.equal(l.body.templates.length, 1);
  const u = await appelle("POST", { action: "save_template", template: { ...modele, id: t.id, nom: "BELUX T (v2)" } });
  assert.equal(u.body.template.nom, "BELUX T (v2)");
  assert.equal(fichierTpl.templates.length, 1);
});

test("modèles : validation, suppression par l'auteur seulement", async () => {
  assert.equal((await appelle("POST", { action: "save_template", template: { ...modele, nom: "x" } })).code, 400);
  assert.equal((await appelle("POST", { action: "save_template", template: { ...modele, config: { ...modele.config, perimetre: { pays: [] } } } })).code, 400);
  assert.equal((await appelle("POST", { action: "save_template", template: { ...modele, config: { ...modele.config, modules: [] } } })).code, 400);
  const c = await appelle("POST", { action: "save_template", template: modele });
  session = { email: "autre@autobiz.com", role: "full" };
  assert.equal((await appelle("POST", { action: "delete_template", id: c.body.template.id })).code, 403);
  session = { email: "m.foureau@autobiz.com", role: "full" };
  assert.equal((await appelle("POST", { action: "delete_template", id: c.body.template.id })).code, 200);
  assert.equal(fichierTpl.templates.length, 0);
  assert.equal((await appelle("POST", { action: "delete_template", id: "M-nope" })).code, 404);
});
