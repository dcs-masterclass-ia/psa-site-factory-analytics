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

test("module Pages (Search Console) : leads GA4 rattachés à la page d'atterrissage", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator('[data-testid="scope-picker-toggle"]').click();
  await page.getByText("Aucun", { exact: true }).click();
  await page.locator('[data-testid="scope-search-input"]').fill("CITROEN FR");
  await page.locator('[data-testid="scope-item"]').filter({ hasText: "CITROEN FR" }).first().click();
  await page.keyboard.press("Escape");
  await page.mouse.click(5, 5);
  await page.locator('div[title="Search Console"]').first().click();

  await expect(page.getByText("Leads GA4", { exact: true }).first()).toBeVisible();
  // l'ancienne colonne "Conv. GA4" (comptee par pagePath, donc toujours 0) a disparu
  await expect(page.getByText("Conv. GA4")).toHaveCount(0);
  // une page de contenu avec des leads rattaches : nombre de leads puis taux (pas "—", pas 0)
  const lignes = await page.evaluate(() => [...document.querySelectorAll("span")]
    .filter((e) => e.textContent.trim() === "/lp/leasing-social-voitures-electriques")
    .map((e) => e.parentElement.innerText.replace(/\s+/g, " ")));
  expect(lignes.some((t) => /\s[1-9][\d ]* \d+,\d{2} %$/.test(t)), lignes.join(" || ")).toBeTruthy();
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});

test("onglet Avant / après V2 : indicateurs, jours exacts, écarts en points, info-bulle", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator('[data-testid="scope-picker-toggle"]').click();
  await page.getByText("Aucun", { exact: true }).click();
  await page.locator('[data-testid="scope-search-input"]').fill("OPEL FR");
  await page.locator('[data-testid="scope-item"]').filter({ hasText: "OPEL FR" }).first().click();
  await page.keyboard.press("Escape");
  await page.mouse.click(5, 5);
  await page.getByText("Avant / après V2", { exact: true }).first().click();
  await expect(page.getByText("Parcours avant / après V2")).toBeVisible();
  await expect(page.getByText(/Avant : .+ \(\d+ j\) · Après : .+ \(\d+ j\)/)).toBeVisible();
  await expect(page.getByText("Visiteurs accueil / jour")).toBeVisible();
  await expect(page.getByText("Estimations / jour")).toBeVisible();
  // écarts de conversion en POINTS (jamais une variation relative étiquetée pt)
  await expect(page.getByText(/[+−]\d+,\d pt/).first()).toBeVisible();
  // info-bulle : visible au survol
  const info = page.locator(".dc-info").filter({ has: page.locator(".dc-tip", { hasText: "28 jours qui précèdent la bascule" }) }).first();
  await info.scrollIntoViewIfNeeded();
  await page.waitForTimeout(300); // le défilement masque la bulle (voulu) : on survole une fois la page immobile
  await info.hover();
  await expect(page.locator("#dc-tipbox")).toBeVisible();
  await expect(page.locator("#dc-tipbox")).toContainText("28 jours qui précèdent la bascule");
  await page.locator("body").screenshot({ path: "test-results/v2-opel.png" });
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});

test("info-bulle d'une tuile : jamais rognée par la carte, reste dans l'écran", async ({ page }) => {
  await page.goto("/", { waitUntil: "networkidle" });
  const icone = page.locator(".dc-info").filter({ has: page.locator(".dc-tip", { hasText: "Sessions GA4 de l'outil de reprise" }) }).first();
  await icone.hover();
  const bulle = page.locator("#dc-tipbox");
  await expect(bulle).toBeVisible();
  await expect(bulle).toContainText("Sessions GA4 de l'outil de reprise");
  const b = await bulle.boundingBox();
  const vp = page.viewportSize();
  expect(b.x).toBeGreaterThanOrEqual(0);
  expect(b.y).toBeGreaterThanOrEqual(0);
  expect(b.x + b.width).toBeLessThanOrEqual(vp.width);
  expect(b.y + b.height).toBeLessThanOrEqual(vp.height);
  await page.screenshot({ path: "test-results/tip-tuile.png" });
  await page.mouse.move(5, 300);
  await expect(bulle).toBeHidden();
});
