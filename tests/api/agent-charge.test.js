// Garde-fou : api/agent.js et ses outils doivent se charger (une faute de syntaxe dans le prompt a cassé KamIA en production le 18/10/2026).
const test = require("node:test");
const assert = require("node:assert/strict");
test("api/agent.js, tools.js et grounding.js se chargent", () => {
  process.env.AUTH_COOKIE_SECRET = "x";
  assert.equal(typeof require("../../api/agent"), "function");
  assert.ok(Array.isArray(require("../../api/_lib/tools").TOOLS));
  assert.equal(typeof require("../../api/_lib/grounding").nonVerifies, "function");
});
