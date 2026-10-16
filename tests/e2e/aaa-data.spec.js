// @ts-check
// Onglet AAA Data : une fiche par marché, limitée aux marchés des sites du sélecteur général (data/market.json).
const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ context, page }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }, { name: "psf_feat", value: "pres", url: "http://localhost:8199" }]);
  await context.addInitScript(() => { try { localStorage.setItem("psf_nouveau_v1", "1"); } catch (e) {} });   // pas de fenêtre « Du nouveau » devant les clics
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
});

/** Ouvre le dashboard, restreint le sélecteur général aux sites donnés, puis ouvre l'onglet AAA Data. */
async function ouvre(page, sites) {
  await page.goto("/", { waitUntil: "networkidle" });
  if (sites) {
    await page.locator('[data-testid="scope-picker-toggle"]').click();
    await page.getByText("Aucun", { exact: true }).click();
    for (const s of sites) {
      await page.locator('[data-testid="scope-search-input"]').fill(s);
      await page.locator('[data-testid="scope-item"]').filter({ hasText: s }).first().click();
    }
    await page.keyboard.press("Escape");
    await page.mouse.click(5, 5);
  }
  await page.locator('[title="AAA Data"]').first().click();
  await expect(page.getByText("Le socle chiffré du marché")).toBeVisible();
}
const fiches = (page) => page.getByText("Immatriculations par mois");

test("AAA Data : tous les sites -> fiches des marchés avec donnée, Europe, message pour les autres", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await ouvre(page, null);
  await expect(page.getByText("Historique annuel")).toBeVisible();      // France
  await expect(page.getByText("Allemagne").first()).toBeVisible();
  await expect(page.getByText("Par pays · 2025")).toBeVisible();        // bloc Europe : sélection multi-marchés
  await expect(page.getByText("Pas de donnée de marché disponible pour :")).toBeVisible();
  expect(erreurs).toEqual([]);
});

test("AAA Data : filtre sur un site français -> seule la fiche France", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await ouvre(page, ["CITROEN FR"]);
  await expect(page.getByText("Voitures neuves ·")).toBeVisible();
  await expect(page.getByText("Cumul depuis janvier").first()).toBeVisible();
  await expect(page.getByText("Historique annuel")).toBeVisible();
  await expect(page.getByText("Modèles les plus immatriculés ·").first()).toBeVisible();
  await expect(fiches(page)).toHaveCount(1);
  await expect(page.getByText("Marques ·")).toHaveCount(0);            // pas de classement des marques publié pour la France : rubrique absente
  await expect(page.getByText("Mix des énergies ·")).toHaveCount(1);
  await expect(page.getByText("Par pays · 2025")).toHaveCount(0);       // pas de bloc Europe pour un seul marché
  await expect(page.getByText("Pas de donnée de marché")).toHaveCount(0);
  expect(erreurs).toEqual([]);
});

test("AAA Data : sélection FR + DE -> deux fiches et le bloc Europe", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await ouvre(page, ["CITROEN FR", "CITROEN DE"]);
  await expect(page.getByText("Voitures neuves ·")).toHaveCount(2);
  await expect(fiches(page)).toHaveCount(2);                            // FR et DE ont chacun une série mensuelle
  await expect(page.getByText("Marques ·").first()).toBeVisible();      // DE publie les marques du mois
  await expect(page.getByText("Par pays · 2025")).toBeVisible();
  expect(erreurs).toEqual([]);
});

test("AAA Data : marché sans donnée (BE) -> une seule ligne explicative, aucune boîte vide", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await ouvre(page, ["CITROEN BE", "CITROEN LU"]);
  await expect(page.getByText("Pas de donnée de marché disponible pour :")).toBeVisible();
  await expect(page.getByText("Belgique / Luxembourg")).toHaveCount(1);
  await expect(fiches(page)).toHaveCount(0);
  await expect(page.getByText("Voitures neuves ·")).toHaveCount(0);
  await expect(page.getByText("Par pays · 2025")).toHaveCount(0);
  expect(erreurs).toEqual([]);
});
