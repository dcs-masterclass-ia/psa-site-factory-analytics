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
  const avant = A.codeDuMois("2026-11"), ck = A.valeurCookie("a@b.c", Date.now(), Date.now(), "2026-11");
  process.env.C1ST_CODE_REV = "2";
  assert.notStrictEqual(avant, A.codeDuMois("2026-11"));
  assert.ok(!A.cookieValide("a@b.c", ck, "2026-11").ok);
  delete process.env.C1ST_CODE_REV;
});
test("révocation (bouton) : même effet qu'une nouvelle révision", () => {
  const avant = A.codeDuMois("2026-11"), ck = A.valeurCookie("a@b.c", Date.now(), Date.now(), "2026-11");
  A._setRev("nouvelle");
  assert.notStrictEqual(avant, A.codeDuMois("2026-11"));
  assert.ok(!A.cookieValide("a@b.c", ck, "2026-11").ok);
  A._setRev("0");
});
test("cookie lié à l'adresse et au mois", () => {
  const ck = A.valeurCookie("a@b.c", Date.now(), Date.now(), "2026-11");
  assert.ok(A.cookieValide("A@b.c", ck, "2026-11").ok);
  assert.ok(!A.cookieValide("z@b.c", ck, "2026-11").ok);
  assert.ok(!A.cookieValide("a@b.c", ck, "2026-12").ok);
  assert.ok(!A.cookieValide("a@b.c", ck.slice(0, -2) + "00", "2026-11").ok);
});
test("verrouillage : 5 min d'inactivité, 4 h au maximum, renouvellement sans prolonger t0", () => {
  const t0 = Date.now() - 3600000, M = "2026-11";
  assert.ok(A.cookieValide("a@b.c", A.valeurCookie("a@b.c", t0, Date.now() - 4 * 60000, M), M).ok);          // actif il y a 4 min
  assert.ok(!A.cookieValide("a@b.c", A.valeurCookie("a@b.c", t0, Date.now() - 6 * 60000, M), M).ok);         // inactif depuis 6 min
  const vieux = Date.now() - 5 * 3600000;
  assert.ok(!A.cookieValide("a@b.c", A.valeurCookie("a@b.c", vieux, Date.now(), M), M).ok);                 // 5 h après la saisie du code, même actif
  assert.ok(!A.cookieValide("a@b.c", A.valeurCookie("a@b.c", Date.now(), Date.now() + 3600000, M), M).ok);  // horodatage dans le futur
});

// ---- suspension après 3 codes faux (magasin simulé)
function faux() {
  let fichier = null, sha = 0;
  return { lis: async () => ({ data: fichier ? JSON.parse(JSON.stringify(fichier)) : null, sha: String(sha) }), ecris: async (_p, d) => { fichier = JSON.parse(JSON.stringify(d)); sha++; }, etat: () => fichier };
}
test("3 codes faux : suspension ; un bon code remet le compteur à zéro ; réactivation", async () => {
  const f = faux(); A._setStore(f.lis, f.ecris);
  assert.deepStrictEqual(await A.echec("x@b.c"), { restants: 2, suspendu: false });
  await A.succes("x@b.c");
  assert.deepStrictEqual(await A.echec("x@b.c"), { restants: 2, suspendu: false });          // compteur reparti de zéro
  assert.deepStrictEqual(await A.echec("X@b.c"), { restants: 1, suspendu: false });
  assert.ok(!(await A.estSuspendu("x@b.c")));
  assert.deepStrictEqual(await A.echec("x@b.c"), { restants: 0, suspendu: true });
  assert.ok(await A.estSuspendu("x@b.c"));
  assert.ok(await A.reactive("x@b.c"));
  assert.ok(!(await A.estSuspendu("x@b.c")));
});
test("un administrateur n'est jamais suspendu", async () => {
  const f = faux(); A._setStore(f.lis, f.ecris);
  process.env.C1ST_ADMIN_EMAILS = "chef@b.c";
  for (let i = 0; i < 5; i++) assert.strictEqual((await A.echec("chef@b.c")).suspendu, false);
  assert.ok(!(await A.estSuspendu("chef@b.c")));
  delete process.env.C1ST_ADMIN_EMAILS;
});
