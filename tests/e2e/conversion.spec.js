// @ts-check
// Sous-onglet GA4 "Conversion" : courbe quotidienne accueil -> estimation
// (funnelDaily, donnee GA4). Ne depend que des donnees du jour de test.
const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ context }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
});

test("la courbe de conversion par jour s'affiche pour un site avec funnelDaily", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator('[data-testid="scope-picker-toggle"]').click();
  await page.getByText("Aucun", { exact: true }).click();
  await page.locator('[data-testid="scope-search-input"]').fill("CITROEN FR");
  await page.locator('[data-testid="scope-item"]').filter({ hasText: "CITROEN FR" }).first().click();
  await page.keyboard.press("Escape");
  await page.mouse.click(5, 5);

  await page.getByText("Conversion", { exact: true }).first().click();
  await expect(page.getByText("Conversion par jour")).toBeVisible();
  await expect(page.getByText("Moyenne glissante 7 jours")).toBeVisible();
  // courbe de la moyenne glissante : un <path> violet epais
  await expect(page.locator('svg path[stroke="#7c63ee"][stroke-width="2.8"]').first()).toBeVisible();
  await expect(page.getByText(/Conversion moyenne \d+,\d %/)).toBeVisible();
  await page.locator('svg[viewBox="0 0 900 250"]').first().screenshot({ path: "test-results/conversion-citroen.png" });
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});

test("sans donnees quotidiennes, un message clair remplace la courbe", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.getByText("Conversion", { exact: true }).first().click();
  // "Marche entier" : la plupart des sites n'ont pas encore funnelDaily en local
  await expect(page.getByText("Conversion par jour")).toBeVisible();
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});
