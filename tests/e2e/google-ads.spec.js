// @ts-check
// Onglet Google Ads : sans données publiées il le dit, avec data/ads/ga4.json (collecte GA4 de la nuit) il affiche clics, impressions, coût et l'avertissement sur le coût non transmis.
const { test, expect } = require("@playwright/test");

const FIXTURE = {
  generee: "2026-10-28T04:20:00+01:00", jusqua: "2026-10-27", jours: 30, source: "GA4",
  sites: [
    { nom: "PEUGEOT FR", noms: ["PEUGEOT FR"], pays: "FR", propriete: "1", devise: "EUR", comptes: [
      { nom: "Compte Promo Test", campagnes: 12, cout: 0, clics: 120000, impressions: 3000000, clics_sans_cout: 120000, mensuel: { "2026-09": [0, 100000, 2500000], "2026-10": [0, 120000, 3000000] }, top: [["Camp A", 0, 90000, 2000000]] },
      { nom: "Compte Avec Cout", campagnes: 3, cout: 5000, clics: 10000, impressions: 200000, clics_sans_cout: 0, mensuel: { "2026-10": [5000, 10000, 200000] }, top: [] }] },
    { nom: "OPEL FR", noms: ["OPEL FR"], pays: "FR", propriete: "2", devise: "EUR", comptes: [
      { nom: "Compte Opel Test", campagnes: 4, cout: 2000, clics: 5000, impressions: 90000, clics_sans_cout: 0, mensuel: { "2026-10": [2000, 5000, 90000] }, top: [] }] },
  ],
  erreurs: [],
};

async function ouvre(context, page, ads) {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40exemple.test", url: "http://localhost:8199" }]);
  await context.addInitScript(() => { try { localStorage.setItem("psf_nouveau_v1", "1"); } catch (e) {} });
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  await page.route("**/data/ads/ga4.json", (r) => (ads ? r.fulfill({ json: ads }) : r.fulfill({ status: 404, body: "" })));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator('[title="Google Ads"]').first().click();
  return erreurs;
}

test("Google Ads : sans données publiées, l'onglet l'indique", async ({ context, page }) => {
  const erreurs = await ouvre(context, page, null);
  await expect(page.getByText("La collecte de la nuit n'a pas encore publié de données")).toBeVisible();
  expect(erreurs).toEqual([]);
});

test("Google Ads : chiffres du fichier, coût non transmis signalé, comptes par site", async ({ context, page }) => {
  const erreurs = await ouvre(context, page, FIXTURE);
  await expect(page.getByText("En cours de construction")).toHaveCount(0);
  await expect(page.getByText("Clics · 30 derniers jours")).toBeVisible();
  await expect(page.getByText("135 000", { exact: true })).toBeVisible();           // 120 000 + 10 000 + 5 000
  await expect(page.getByText("coût non transmis").first()).toBeVisible();          // PEUGEOT FR : 120 000 clics sur 130 000 sans coût
  await expect(page.getByText("LECTURE DES CHIFFRES")).toBeVisible();
  await expect(page.getByText("coût complet")).toBeVisible();                        // OPEL FR
  await page.getByText("PEUGEOT FR", { exact: true }).first().click();               // déplie les comptes du site
  await expect(page.getByText("Compte Promo Test")).toBeVisible();
  expect(erreurs).toEqual([]);
});
