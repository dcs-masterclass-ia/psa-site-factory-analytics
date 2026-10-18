// Moteur d'insights (insights.js) : constats calculés, classés par impact. node --test tests/api/insights.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const { calculeInsights } = require("../../insights.js");

const ETAPES = ["Page d'accueil", "Version", "Kilométrage", "Coordonnées", "Point de vente", "Leads GA"];
const base = { hasCmp: true, etapes: ETAPES, singleSite: true };
const ids = (r) => r.map((x) => x.id);

test("décomposition : variation des leads = effet trafic + effet conversion (exact)", () => {
  // L = S × taux : 1000 sessions à 5 % (50) -> 800 sessions à 5,5 % (44) : Δ = -6 ; trafic -200×5 % = -10, conversion +800×0,5 pt = +4
  const r = calculeInsights({ ...base, L0: 2000, S0: 40000, L1: 1650, S1: 33000 });
  const d = r.find((x) => x.id === "decomposition");
  assert.ok(d);
  assert.equal(d.leads, -350);
  assert.equal(d.type, "alerte");
  assert.match(d.texte, /trafic de reprise/);          // le trafic domine : 7 000 sessions de moins à 5 % = -350 ; la conversion est inchangée
  assert.match(d.texte, /−350/);
});

test("la conversion peut dominer, le trafic compense", () => {
  const r = calculeInsights({ ...base, L0: 1000, S0: 20000, L1: 1400, S1: 22000 });       // 5 % -> 6,36 %
  const d = r.find((x) => x.id === "decomposition");
  assert.ok(d && d.leads === 400);
  assert.match(d.texte, /surtout la conversion/);
  assert.match(d.texte, /amplifie/);
});

test("rien d'anormal : pas d'insight (pas de bruit pour remplir la carte)", () => {
  const r = calculeInsights({ ...base, L0: 1000, S0: 20000, L1: 1010, S1: 20100, canal1: { a: 1000 }, canal0: { a: 1010 }, steps1: [1000, 500, 450, 440, 300, 250], steps0: [1000, 500, 450, 440, 300, 250] });
  assert.deepEqual(r, []);
});

test("canal moteur : le canal qui explique la baisse, en sessions et en leads", () => {
  const r = calculeInsights({ ...base, L0: 2000, S0: 40000, L1: 1500, S1: 30000, canal1: { "Paid Social": 2000, Organic: 28000 }, canal0: { "Paid Social": 12000, Organic: 28000 } });
  const c = r.find((x) => x.id === "canal");
  assert.ok(c);
  assert.match(c.texte, /Paid Social : −10[\s ]000 sessions \(−83 %\)/);
  assert.match(c.texte, /100 % de la baisse totale/);
  assert.equal(Math.round(c.leads), -500);                              // 10 000 sessions × 5 %
});

test("tunnel : l'étape qui se dégrade vs la période précédente, avec les leads perdus", () => {
  const r = calculeInsights({ ...base, L0: 0, S0: 0, steps0: [10000, 6000, 5400, 5300, 3600, 3000], steps1: [10000, 6000, 4800, 4700, 3200, 2660] });
  const t = r.find((x) => x.id === "tunnel");
  assert.ok(t);
  assert.match(t.texte, /« Kilométrage »/);
  assert.match(t.texte, /80,0 %.*90,0 %/);
  assert.ok(t.leads < 0 && Math.abs(t.leads + 600 * 0.5541) < 6, String(t.leads));   // (0,9-0,8) × 6000 × (2660/4800)
});

test("appareils : écart de conversion et gain prudent (moitié de l'écart)", () => {
  const r = calculeInsights({ ...base, hasCmp: false, combos: [
    { canal: "Organic", device: "mobile", sessions: 6000, conversions: 60 }, { canal: "Direct", device: "mobile", sessions: 2000, conversions: 20 },
    { canal: "Organic", device: "desktop", sessions: 3000, conversions: 90 }, { canal: "Direct", device: "desktop", sessions: 1000, conversions: 30 }] });
  const a = r.find((x) => x.id === "appareils");
  assert.ok(a);
  assert.match(a.texte, /mobile \(67 % des sessions\), 1,00 % convertissent contre 3,00 % sur desktop/);
  assert.equal(Math.round(a.leads), 80);                                // 0,5 × (3 % - 1 %) × 8 000
});

test("segment peu volumineux mais très performant", () => {
  const combos = [{ canal: "Organic", device: "mobile", sessions: 20000, conversions: 200 }, { canal: "Email", device: "mobile", sessions: 1000, conversions: 70 }];
  const r = calculeInsights({ ...base, hasCmp: false, combos });
  const s = r.find((x) => x.id === "segment");
  assert.ok(s);
  assert.match(s.texte, /Email × mobile convertit/);
  assert.equal(Math.round(s.leads), 14);                                // +20 % de 70 conversions
});

test("parcours marque / modèle plus court que le parcours plaque", () => {
  const r = calculeInsights({ ...base, hasCmp: false, entree: { immat: [6000, 5800, 5700, 3500, 3400], mm: [400, 380, 360, 150, 100] } });
  const s = r.find((x) => x.id === "saisie");
  assert.ok(s);
  assert.match(s.texte, /6 % des visiteurs/);
  assert.equal(Math.round(s.leads), 63);                                // 0,5 × (56,7 % - 25 %) × 400
});

test("position vs parc : seulement sous la médiane, avec le gain pour la rejoindre", () => {
  const sous = calculeInsights({ ...base, hasCmp: false, S1: 100000, L1: 5000, parc: { rate: 5, mediane: 7, rang: 60, total: 82 } }).find((x) => x.id === "parc");
  assert.ok(sous && Math.round(sous.leads) === 2000);
  assert.equal(calculeInsights({ ...base, hasCmp: false, S1: 100000, L1: 8000, parc: { rate: 8, mediane: 7, rang: 10, total: 82 } }).length, 0);
});

test("rupture de la semaine : seuil de 2 écarts-types et 15 %", () => {
  assert.ok(calculeInsights({ ...base, hasCmp: false, semaine: { actuelle: 700, moyenne: 1000, ecartType: 100 } }).some((x) => x.id === "rupture"));
  assert.equal(calculeInsights({ ...base, hasCmp: false, semaine: { actuelle: 900, moyenne: 1000, ecartType: 100 } }).length, 0);       // 1 écart-type seulement
  assert.equal(calculeInsights({ ...base, hasCmp: false, semaine: { actuelle: 1040, moyenne: 1000, ecartType: 10 } }).length, 0);        // significatif mais < 15 %
});

test("classement par impact en leads, plus fort d'abord", () => {
  const r = calculeInsights({ ...base, L0: 2000, S0: 40000, L1: 1500, S1: 30000, canal1: { "Paid Social": 2000, Organic: 28000 }, canal0: { "Paid Social": 12000, Organic: 28000 },
    steps0: [10000, 6000, 5400, 5300, 3600, 3000], steps1: [10000, 6000, 4800, 4700, 3200, 2660] });
  const v = r.map((x) => Math.abs(x.leads));
  assert.deepEqual(v, [...v].sort((a, b) => b - a));
  assert.ok(ids(r).includes("decomposition") && ids(r).includes("canal") && ids(r).includes("tunnel"));
});

test("anglais : mêmes constats, textes et nombres en anglais", () => {
  const r = calculeInsights({ ...base, en: true, L0: 2000, S0: 40000, L1: 1500, S1: 30000, canal1: { "Paid Social": 2000 }, canal0: { "Paid Social": 12000 } });
  const c = r.find((x) => x.id === "canal");
  assert.match(c.texte, /Paid Social: −10,000 sessions \(−83 %\) vs the previous period/);
  assert.ok(!/[éèà]/.test(r.map((x) => x.texte + x.titre).join(" ")));
});

test("conversion à contre-courant : leads en hausse grâce au trafic mais conversion en recul -> constat séparé", () => {
  const r = calculeInsights({ ...base, L0: 2500, S0: 12000, L1: 2978, S1: 16000 });          // 20,8 % -> 18,6 % ; trafic +33 %
  const c = r.find((x) => x.id === "conversion");
  assert.ok(c && c.type === "alerte" && c.leads < 0);
  assert.match(c.texte, /recule de 2,\d\d pt/);
  assert.ok(r.some((x) => x.id === "decomposition"));
});
test("pas de doublon quand la conversion domine déjà la décomposition", () => {
  const r = calculeInsights({ ...base, L0: 1000, S0: 20000, L1: 1400, S1: 22000 });
  assert.ok(!r.some((x) => x.id === "conversion"));
});
