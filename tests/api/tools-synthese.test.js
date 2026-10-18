// Totaux d'une série calculés côté serveur (le modèle additionnait mal : 1 777 au lieu de 1 908). node --test tests/api/tools-synthese.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const { syntheseSerie } = require("../../api/_lib/tools");

test("synthèse : total, moyenne, extrêmes et total par mois exacts", () => {
  const daily = [81, 85, 78, 67, 130, 136, 103, 139, 119, 164, 124, 137, 131, 110, 98, 94, 112];     // octobre 2026 OPEL FR (1 908)
  const labels = daily.map((_, i) => "2026-10-" + String(i + 1).padStart(2, "0"));
  const s = syntheseSerie({ labels, values: daily });
  assert.equal(s.total, 1908);
  assert.equal(s.nb_jours, 17);
  assert.equal(s.moyenne_par_jour, 112.2);
  assert.deepEqual(s.maximum, { jour: "2026-10-10", valeur: 164 });
  assert.deepEqual(s.minimum, { jour: "2026-10-04", valeur: 67 });
  assert.deepEqual(s.total_par_mois, { "2026-10": 1908 });
});
test("synthèse : plusieurs mois, valeurs manquantes comptées pour 0, série vide", () => {
  const s = syntheseSerie({ labels: ["2026-09-30", "2026-10-01", "2026-10-02"], values: [10, null, 5] });
  assert.equal(s.total, 15);
  assert.deepEqual(s.total_par_mois, { "2026-09": 10, "2026-10": 5 });
  assert.deepEqual(syntheseSerie({ labels: [], values: [] }), { nb_jours: 0, total: 0 });
});
