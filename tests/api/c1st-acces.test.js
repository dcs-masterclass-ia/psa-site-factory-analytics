// Code d'accès mensuel C1ST : dérivé, change chaque mois, révision d'urgence, cookie lié à l'adresse et au mois.
const test = require("node:test");
const assert = require("node:assert");
process.env.AUTH_COOKIE_SECRET = "secret-de-test";
const A = require("../../api/_lib/c1st-acces");

test("le code est stable dans le mois, change le mois suivant, 10 caractères", () => {
  const c = A.codeDuMois("2026-11");
  assert.match(c, /^[A-Z2-9]{5}-[A-Z2-9]{5}$/);
  assert.strictEqual(c, A.codeDuMois("2026-11"));
  assert.notStrictEqual(c, A.codeDuMois("2026-12"));
});
test("saisie tolérante (minuscules, sans tiret) mais exacte", () => {
  const c = A.codeDuMois();
  assert.ok(A.codeValide(c.toLowerCase().replace("-", " ")));
  assert.ok(!A.codeValide("AAAAA-AAAAA"));
  assert.ok(!A.codeValide(""));
});
test("révision d'urgence : nouveau code, anciens cookies invalides", () => {
  const avant = A.codeDuMois("2026-11"), ck = A.valeurCookie("a@b.c", "2026-11");
  process.env.C1ST_CODE_REV = "2";
  assert.notStrictEqual(avant, A.codeDuMois("2026-11"));
  assert.ok(!A.cookieValide("a@b.c", ck, "2026-11"));
  delete process.env.C1ST_CODE_REV;
});
test("révocation (bouton) : même effet qu'une nouvelle révision", () => {
  const avant = A.codeDuMois("2026-11"), ck = A.valeurCookie("a@b.c", "2026-11");
  A._setRev("nouvelle");
  assert.notStrictEqual(avant, A.codeDuMois("2026-11"));
  assert.ok(!A.cookieValide("a@b.c", ck, "2026-11"));
  A._setRev("0");
});
test("cookie lié à l'adresse et au mois", () => {
  const ck = A.valeurCookie("a@b.c", "2026-11");
  assert.ok(A.cookieValide("A@b.c", ck, "2026-11"));
  assert.ok(!A.cookieValide("z@b.c", ck, "2026-11"));
  assert.ok(!A.cookieValide("a@b.c", ck, "2026-12"));
});
