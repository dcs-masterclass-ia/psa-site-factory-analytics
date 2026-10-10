// Tests de api/tickets.js sans réseau : le magasin (repo de données) et la
// session sont remplacés par des doubles. Lancer : node --test tests/api/
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("path");

const racine = path.resolve(__dirname, "../..");
const storePath = require.resolve(path.join(racine, "api/_lib/store.js"));
const authPath = require.resolve(path.join(racine, "api/_lib/auth.js"));

let fichier = null, sha = 0, session = null;
require.cache[storePath] = { id: storePath, filename: storePath, loaded: true, exports: {
  readJson: async () => ({ data: fichier ? JSON.parse(JSON.stringify(fichier)) : null, sha: String(sha) }),
  writeJson: async (_p, data) => { fichier = JSON.parse(JSON.stringify(data)); sha++; return { sha: String(sha) }; },
} };
const vraiAuth = require(authPath);
require.cache[authPath].exports = { ...vraiAuth, verifySessionFromRequest: () => session };
const handler = require(path.join(racine, "api/tickets.js"));

function appelle(method, body) {
  return new Promise(resolve => {
    const res = { code: 200, headers: {}, setHeader(k, v) { this.headers[k] = v; }, status(c) { this.code = c; return this; }, json(o) { resolve({ code: this.code, body: o }); } };
    handler({ method, body, headers: {} }, res);
  });
}
const valide = { action: "create", type: "bug", titre: "Leads FR faux", description: "Le total FR ne correspond pas au BO sur septembre.", priorite: "haute",
  contexte: { source: "tb", sites: ["PEUGEOT FR"], nbSites: 1, periode: { from: "2026-09-01", to: "2026-09-30" }, onglet: "Tableau" } };

test.beforeEach(() => { fichier = null; sha = 0; session = { email: "m.foureau@autobiz.com", role: "full" }; });

test("sans session : 401", async () => {
  session = null;
  assert.equal((await appelle("GET")).code, 401);
});

test("création valide : ticket nouveau, auteur = session, contexte nettoyé", async () => {
  const r = await appelle("POST", valide);
  assert.equal(r.code, 200);
  assert.match(r.body.ticket.id, /^T-\d{8}-[0-9a-f]{4}$/);
  assert.equal(r.body.ticket.statut, "nouveau");
  assert.equal(r.body.ticket.auteur, "m.foureau@autobiz.com");
  assert.equal(fichier.tickets.length, 1);
});

test("validation : type inconnu, titre court, description courte", async () => {
  assert.equal((await appelle("POST", { ...valide, type: "hack" })).code, 400);
  assert.equal((await appelle("POST", { ...valide, titre: "x" })).code, 400);
  assert.equal((await appelle("POST", { ...valide, description: "court" })).code, 400);
  assert.equal(fichier, null);
});

test("entrées hostiles : champs tronqués, source inconnue ignorée", async () => {
  const r = await appelle("POST", { ...valide, titre: "A".repeat(500), description: "B".repeat(10000), contexte: { source: "evil", sites: new Array(50).fill("S"), nbSites: 99999, periode: { from: "pas-une-date", to: 5 } } });
  assert.equal(r.code, 200);
  assert.equal(r.body.ticket.titre.length, 120);
  assert.equal(r.body.ticket.description.length, 3000);
  assert.equal(r.body.ticket.contexte.source, null);
  assert.equal(r.body.ticket.contexte.sites.length, 6);
  assert.equal(r.body.ticket.contexte.nbSites, 1000);
  assert.equal(r.body.ticket.contexte.periode.from, null);
});

test("profil limité : peut créer, ne voit que les siens, ne peut pas changer le statut", async () => {
  session = { email: "b.moumni@autobiz.com", role: "limited" };
  const c = await appelle("POST", valide);
  assert.equal(c.code, 200);
  session = { email: "autre@autobiz.com", role: "limited" };
  await appelle("POST", { ...valide, titre: "Autre ticket" });
  session = { email: "b.moumni@autobiz.com", role: "limited" };
  const l = await appelle("GET");
  assert.equal(l.body.tickets.length, 1);
  assert.equal(l.body.peutGerer, false);
  assert.equal((await appelle("POST", { action: "status", id: c.body.ticket.id, statut: "resolu" })).code, 403);
});

test("profil limité : ticket d'un autre = introuvable (pas de fuite)", async () => {
  const c = await appelle("POST", valide);
  session = { email: "b.moumni@autobiz.com", role: "limited" };
  assert.equal((await appelle("POST", { action: "comment", id: c.body.ticket.id, texte: "coucou" })).code, 404);
});

test("profil complet : voit tout, change le statut, historique tracé", async () => {
  session = { email: "b.moumni@autobiz.com", role: "limited" };
  const c = await appelle("POST", valide);
  session = { email: "m.foureau@autobiz.com", role: "full" };
  assert.equal((await appelle("GET")).body.tickets.length, 1);
  const s = await appelle("POST", { action: "status", id: c.body.ticket.id, statut: "en_cours" });
  assert.equal(s.body.ticket.statut, "en_cours");
  assert.equal(s.body.ticket.commentaires.at(-1).systeme, true);
  assert.equal((await appelle("POST", { action: "status", id: c.body.ticket.id, statut: "nimportequoi" })).code, 400);
});

test("commentaire : l'auteur peut commenter son ticket, texte vide refusé", async () => {
  session = { email: "b.moumni@autobiz.com", role: "limited" };
  const c = await appelle("POST", valide);
  assert.equal((await appelle("POST", { action: "comment", id: c.body.ticket.id, texte: "   " })).code, 400);
  const r = await appelle("POST", { action: "comment", id: c.body.ticket.id, texte: "Précision : septembre uniquement" });
  assert.equal(r.code, 200);
  assert.equal(r.body.ticket.commentaires.length, 1);
});

test("limite de 10 tickets par jour et par personne", async () => {
  for (let i = 0; i < 10; i++) assert.equal((await appelle("POST", { ...valide, titre: "Ticket " + i })).code, 200);
  assert.equal((await appelle("POST", valide)).code, 429);
});

test("méthode inconnue et action inconnue", async () => {
  assert.equal((await appelle("DELETE")).code, 405);
  assert.equal((await appelle("POST", { action: "supprimer-tout" })).code, 404);
});
