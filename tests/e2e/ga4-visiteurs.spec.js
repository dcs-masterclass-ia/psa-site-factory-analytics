// @ts-check
// GA4 > Audience > « Qui sont les visiteurs ? » : vrais nouveaux / récurrents, géographie et langue, profil des demandeurs (véhicule repris).
// La géographie (geoMonth) n'est pas encore dans les fichiers locaux : elle est ajoutée à la volée sur la réponse réelle de data/peugeot-fr.json.
const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ context }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
});

const ouvre = async (page, tab) => {
  await page.goto("/", { waitUntil: "networkidle" });
  await page.evaluate((t) => sessionStorage.setItem("psf_ui_state", JSON.stringify({ source: "ga", tab: t, sites: ["PEUGEOT FR"], from: null, to: null, cmpMode: "none" })), tab);
  await page.reload({ waitUntil: "networkidle" });
};

const avecGeo = async (page) => {
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  await page.route("**/data/peugeot-fr.json", async (route) => {
    const rep = await route.fetch();
    const d = await rep.json();
    d.geoMonth = d.geoMonth || {};
    for (const m of d.months || []) {
      d.geoMonth[m] = { total: 1000, pays: [["France", 930], ["Belgium", 40], ["Andorra", 20]], regions: [["Île-de-France", 200]], villes: [["Paris", 220], ["Lyon", 90], ["Marseille", 60]], langues: [["French", 960], ["English", 25]] };
    }
    await route.fulfill({ json: d });
  });
};

test("visiteurs : nouveaux / récurrents réels (plus les valeurs figées 68 % / 32 %)", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  await ouvre(page, "audience");
  const pct = async (lib) => parseInt(await page.getByText(lib, { exact: true }).locator("xpath=following-sibling::div[1]").innerText(), 10);
  const n = await pct("Nouveaux"), r = await pct("Récurrents");
  expect(n + r).toBeGreaterThanOrEqual(99);
  expect(n + r).toBeLessThanOrEqual(101);
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});

test("visiteurs : vue « Où sont les visiteurs ? » (pays, villes, langues traduits depuis GA4)", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await avecGeo(page);
  await ouvre(page, "geo");
  await expect(page.getByText("Où sont les visiteurs ?", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Paris", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Belgique", { exact: true }).first()).toBeVisible();      // Belgium
  await expect(page.getByText(/^français$/).first()).toBeVisible();                     // French, majuscule à l'affichage
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});

test("visiteurs : vue « Quel véhicule veulent-ils reprendre ? » (marque et carburant du véhicule repris, back-office)", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  await ouvre(page, "profil");
  await expect(page.getByText("Quel véhicule veulent-ils reprendre ?", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Marque du véhicule repris")).toBeVisible();
  await expect(page.getByText("Carburant", { exact: true }).first()).toBeVisible();
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});

test("visiteurs : sans donnée géographique, un message dit qu'elle est en cours de collecte (jamais de zéro trompeur)", async ({ page }) => {
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  await ouvre(page, "geo");
  await expect(page.getByText(/en cours de collecte/)).toBeVisible();
});
