// Tests de api/ticket-decision.js sans réseau (magasin remplacé). Lancer : node --test tests/api/
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("path");
const racine = path.resolve(__dirname, "../..");
const storePath = require.resolve(path.join(racine, "api/_lib/store.js"));
let fichier = null;
require.cache[storePath] = { id: storePath, filename: storePath, loaded: true, exports: {
  readJson: async () => ({ data: JSON.parse(JSON.stringify(fichier)), sha: "1" }),
  writeJson: async (_p, data) => { fichier = JSON.parse(JSON.stringify(data)); return { sha: "2" }; },
} };
process.env.TICKETS_LINK_SECRET = "s3cret";
const handler = require(path.join(racine, "api/ticket-decision.js"));
const lien = (id, a, exp = Date.now() + 1e6) => ({ id, a, exp: String(exp), sig: handler.signe(id, a, String(exp)) });

function appelle(method, query, body) {
  return new Promise(resolve => {
    const res = { code: 200, headers: {}, setHeader(k, v) { this.headers[k] = v; }, status(c) { this.code = c; return this; }, send(h) { resolve({ code: this.code, html: h }); } };
    handler({ method, query, body }, res);
  });
}
test.beforeEach(() => { fichier = { tickets: [{ id: "T-1", titre: "Total", auteur: "a@b.c", statut: "nouveau", commentaires: [] }] }; });

test("signature invalide ou expirée : 400", async () => {
  assert.equal((await appelle("GET", { ...lien("T-1", "accept"), sig: "x" })).code, 400);
  assert.equal((await appelle("GET", lien("T-1", "accept", Date.now() - 1000))).code, 400);
});
test("GET ne décide jamais, POST accepte une seule fois", async () => {
  const q = lien("T-1", "accept");
  assert.equal((await appelle("GET", q)).code, 200);
  assert.equal(fichier.tickets[0].decision, undefined);
  assert.equal((await appelle("POST", {}, q)).code, 200);
  assert.equal(fichier.tickets[0].decision.choix, "accepte");
  assert.equal(fichier.tickets[0].statut, "en_cours");
  const r = await appelle("POST", {}, lien("T-1", "refuse"));
  assert.match(r.html, /Déjà décidé/);
  assert.equal(fichier.tickets[0].statut, "en_cours");
});
test("refus : statut refuse + commentaire système", async () => {
  await appelle("POST", {}, lien("T-1", "refuse"));
  assert.equal(fichier.tickets[0].statut, "refuse");
  assert.equal(fichier.tickets[0].commentaires[0].systeme, true);
});

test("validation de mise en ligne : seulement si le correctif attend, une seule fois, sans changer le statut", async () => {
  assert.equal((await appelle("POST", {}, lien("T-1", "merge"))).code, 409);
  fichier.tickets[0].agent = { etat: "attente_validation", pr: "https://github.com/x/y/pull/1" };
  assert.equal((await appelle("POST", {}, lien("T-1", "merge"))).code, 200);
  assert.equal(fichier.tickets[0].validation.choix, "accepte");
  assert.equal(fichier.tickets[0].statut, "nouveau");
  assert.match((await appelle("POST", {}, lien("T-1", "abandon"))).html, /Déjà décidé/);
});

test("demander des précisions : question envoyée à l'auteur (visible, ticket en attente), sans décision", async () => {
  const q = lien("T-1", "ask");
  const g = await appelle("GET", q);
  assert.equal(g.code, 200);
  assert.match(g.html, /textarea/);
  assert.equal((await appelle("POST", {}, { ...q, texte: "   " })).code, 400);
  assert.equal((await appelle("POST", {}, { ...q, texte: "Sur quel onglet exactement ?" })).code, 200);
  const t = fichier.tickets[0];
  assert.equal(t.attente, "auteur");
  assert.equal(t.commentaires[0].texte, "Sur quel onglet exactement ?");
  assert.equal(t.commentaires[0].systeme, undefined);
  assert.equal(t.decision, undefined);
});

test("réponse préparée pour une question : envoyer (message à l'auteur + résolu), abandonner, bug", async () => {
  fichier.tickets[0].reponse = { etat: "attente", texte: "Les deux chiffres sont justes.", verdict: "reponse" };
  const q = lien("T-1", "send");
  const g = await appelle("GET", q);
  assert.match(g.html, /Les deux chiffres sont justes/);
  assert.equal(fichier.tickets[0].statut, "nouveau");
  assert.equal((await appelle("POST", {}, q)).code, 200);
  const t = fichier.tickets[0];
  assert.equal(t.statut, "resolu");
  assert.equal(t.reponse.etat, "envoyee");
  assert.equal(t.commentaires.slice(-1)[0].texte, "Les deux chiffres sont justes.");
  assert.equal(t.commentaires.slice(-1)[0].systeme, undefined);
  assert.match((await appelle("POST", {}, lien("T-1", "drop"))).html, /Déjà traité/);
});

test("réponse modifiée avant envoi ; ne pas répondre ; traiter comme un bug", async () => {
  fichier.tickets[0].reponse = { etat: "attente", texte: "brouillon", verdict: "reponse" };
  await appelle("POST", {}, { ...lien("T-1", "edit"), texte: "Version corrigée par M." });
  assert.equal(fichier.tickets[0].commentaires.slice(-1)[0].texte, "Version corrigée par M.");
  fichier.tickets[0].reponse = { etat: "attente", texte: "x", verdict: "reponse" }; fichier.tickets[0].statut = "nouveau";
  await appelle("POST", {}, lien("T-1", "drop"));
  assert.equal(fichier.tickets[0].reponse.etat, "abandon");
  assert.equal(fichier.tickets[0].statut, "nouveau");
  fichier.tickets[0].reponse = { etat: "attente", texte: "x", verdict: "bug_possible", bug: "chiffre faux" };
  await appelle("POST", {}, lien("T-1", "tobug"));
  assert.equal(fichier.tickets[0].triage.categorie, "bug");
  assert.equal(fichier.tickets[0].decision.choix, "accepte");
  assert.equal(fichier.tickets[0].statut, "en_cours");
});

test("commentaire d'un utilisateur : répondre (message équipe-converge) et rouvrir une question terminée", async () => {
  fichier.tickets[0].statut = "resolu";
  fichier.tickets[0].triage = { categorie: "question" };
  fichier.tickets[0].reponse = { etat: "envoyee", texte: "ancienne réponse" };
  fichier.tickets[0].commentaires = [{ auteur: "a@b.c", texte: "Je pense qu'il faut changer cela", at: 1 }];
  const r = lien("T-1", "reply");
  const g = await appelle("GET", r);
  assert.match(g.html, /Je pense qu&#39;il faut|Je pense qu'il faut/);
  await appelle("POST", {}, { ...r, texte: "Bien reçu, on regarde." });
  assert.equal(fichier.tickets[0].commentaires.slice(-1)[0].texte, "Bien reçu, on regarde.");
  assert.equal(fichier.tickets[0].statut, "resolu");
  await appelle("POST", {}, lien("T-1", "reopen"));
  assert.equal(fichier.tickets[0].statut, "en_cours");
  assert.equal(fichier.tickets[0].reponse, undefined);
  assert.match((await appelle("POST", {}, lien("T-1", "reopen"))).html, /Déjà ouvert/);
});
