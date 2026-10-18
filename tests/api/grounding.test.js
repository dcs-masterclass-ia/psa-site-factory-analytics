// Contrôle des chiffres de KamIA. node --test tests/api/grounding.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const { nonVerifies, nombres } = require("../../api/_lib/grounding");

const synthese = JSON.stringify({ synthese: { nb_jours: 17, total: 1908, moyenne_par_jour: 112.2, maximum: { jour: "2026-10-10", valeur: 164 } } });
const preuves = { brut: [JSON.stringify({ daily: [81, 85, 78, 67, 130] })], calcule: [synthese] };

test("le cas du 18/10 : 1 777 est refusé, 1 908 et 112,2 sont acceptés", () => {
  const faux = "Depuis le début du mois (données jusqu'au 17/10/26), OPEL FR a généré 1 777 leads, soit environ 105 leads/jour, avec un pic à 164 leads le 10/10.";
  assert.deepEqual(nonVerifies(faux, "Combien de leads ?", preuves).sort(), ["105", "1 777"].sort());
  const juste = "Depuis le début du mois (données jusqu'au 17/10/26), OPEL FR a généré 1 908 leads, soit 112,2 leads/jour, avec un pic à 164 leads le 10/10.";
  assert.deepEqual(nonVerifies(juste, "Combien de leads ?", preuves), []);
});
test("évolutions et rapports déduits de deux chiffres calculés sont acceptés, pas les autres", () => {
  const p = { brut: [], calcule: [JSON.stringify({ a: 1200, b: 1111 })] };
  assert.deepEqual(nonVerifies("Les leads sont à 1 200 contre 1 111 : +8 %.", "", p), []);
  assert.deepEqual(nonVerifies("C'est +12 %.", "", p), ["12 %"]);
  assert.deepEqual(nonVerifies("Soit 2 311 au total.", "", p), []);                  // somme de deux chiffres calculés
});
test("dates, années, petits comptages et unités de période ne sont pas des chiffres métier", () => {
  assert.deepEqual(nonVerifies("Sur 17 jours, du 01/10/26 au 17/10/26, en 2026, 3 étapes, 4 agents, T3, GA4.", "", { brut: [], calcule: [] }), []);
  assert.deepEqual(nombres("1 908 leads et 7,4 %").map(n => n.v), [1908, 7.4]);
});
test("une valeur lue dans les données brutes est acceptée telle quelle (et arrondie), jamais déduite de celles-ci", () => {
  assert.deepEqual(nonVerifies("Le 2e jour : 85 leads.", "", preuves), []);
  assert.deepEqual(nonVerifies("Les deux premiers jours font 166 leads.", "", preuves), ["166"]);   // 81+85 : somme faite par le modèle sur des données brutes
});
