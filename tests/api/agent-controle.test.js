// Contrôle des chiffres dans la boucle de l'agent (modèle et outils simulés). node --test tests/api/agent-controle.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("path");
const racine = path.resolve(__dirname, "../..");
process.env.AUTH_COOKIE_SECRET = "x";
const ancrePath = require.resolve(path.join(racine, "api/_lib/anthropic.js"));
const toolsPath = require.resolve(path.join(racine, "api/_lib/tools.js"));
const authPath = require.resolve(path.join(racine, "api/_lib/auth.js"));
let scenario = [], appels = 0, messagesVus = [];
require.cache[ancrePath] = { id: ancrePath, filename: ancrePath, loaded: true, exports: {
  callClaudeStream: async function* ({ messages }) { messagesVus.push(JSON.parse(JSON.stringify(messages))); const r = scenario[appels++]; yield { type: "message-complete", content: r.content, stop_reason: r.stop }; },
  callClaude: async () => ({ content: [] }) } };
const vraiTools = require(toolsPath);
require.cache[toolsPath].exports = { ...vraiTools, runTool: async (name, input, preuves) => {
  const synthese = { total: 1908, moyenne_par_jour: 112.2, nb_jours: 17 };
  preuves.brut.push(JSON.stringify([81, 85])); preuves.calcule.push(JSON.stringify(synthese));
  return { synthese }; } };
const vraiAuth = require(authPath);
require.cache[authPath].exports = { ...vraiAuth, verifySessionFromRequest: () => ({ email: "m@x.c", role: "full" }) };
const handler = require(path.join(racine, "api/agent.js"));
const appelle = () => new Promise(resolve => handler({ method: "POST", body: { question: "Combien de leads depuis le début du mois ?" }, query: {}, headers: {} },
  { setHeader() {}, status(c) { this.code = c; return this; }, json(o) { resolve({ code: this.code, body: o }); } }));
const outil = { stop: "tool_use", content: [{ type: "tool_use", id: "t1", name: "get_series", input: { site: "OPEL FR", metric: "leads" } }] };
const texte = t => ({ stop: "end_turn", content: [{ type: "text", text: t }] });

test("réponse fausse -> rappel automatique -> réponse corrigée, aucun avertissement", async () => {
  scenario = [outil, texte("OPEL FR a généré 1 777 leads."), texte("OPEL FR a généré 1 908 leads.")]; appels = 0; messagesVus = [];
  const r = await appelle();
  assert.equal(r.code, 200);
  assert.equal(r.body.answer, "OPEL FR a généré 1 908 leads.");
  assert.equal(r.body.verifie, true);
  const rappel = JSON.stringify(messagesVus[2]);
  assert.match(rappel, /Controle automatique/); assert.match(rappel, /1 777/);
});
test("le modèle persiste dans l'erreur -> la réponse porte un avertissement honnête", async () => {
  scenario = [outil, texte("1 777 leads."), texte("Toujours 1 777 leads.")]; appels = 0; messagesVus = [];
  const r = await appelle();
  assert.equal(r.body.verifie, false);
  assert.match(r.body.answer, /Chiffres non verifies par les outils : 1 777/);
});
test("réponse juste du premier coup -> aucun rappel", async () => {
  scenario = [outil, texte("1 908 leads, soit 112,2 par jour.")]; appels = 0; messagesVus = [];
  const r = await appelle();
  assert.equal(r.body.verifie, true); assert.equal(appels, 2);
});
