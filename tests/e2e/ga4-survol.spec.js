// @ts-check
// GA4 > Analyses détaillées : chaque courbe affiche une bulle d'informations au survol.
const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ context }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
});

test("survol des courbes : bulle avec valeurs", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await page.route("**/api/events", (r) => r.fulfill({ json: { events: [], peutEcrire: false } }));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.getByText("Analyses détaillées", { exact: false }).first().click().catch(() => {});
  const vus = [];
  for (const [theme, nav, id] of [["Évolution", "Évolution du trafic reprise par canal", "cbTrend"], ["Évolution", "Comparaison avec les années passées", "cbHist"], ["Conversion", "Taux de conversion par jour", "cbConv"], ["Audience", "Qui sont les visiteurs", "cbSeason"], ["Évolution", "Ce qui fait bouger les leads", "cbContrib"]]) {
    await page.getByText(theme, { exact: true }).first().click({ timeout: 3000 }).catch(() => {});
    await page.getByText(nav, { exact: true }).first().click({ timeout: 3000 }).catch(() => {});
    if (id === "cbContrib") await page.getByText("Vue graphique", { exact: true }).first().click({ timeout: 3000 }).catch(() => {});      // la cascade n'est plus la vue par défaut
    const box = page.locator("#" + id);
    if (!(await box.count())) continue;
    await box.scrollIntoViewIfNeeded();
    await page.waitForTimeout(300);
    const b = await box.boundingBox();
    await page.mouse.move(b.x + b.width * 0.4, b.y + b.height * 0.5);
    await page.mouse.move(b.x + b.width * 0.5, b.y + b.height * 0.5, { steps: 3 });
    await page.waitForTimeout(200);
    await expect(page.locator("#chartHovTip")).toBeVisible();
    vus.push(id);
    await page.mouse.move(2, 2);
  }
  expect(vus).toHaveLength(5);
  expect(erreurs).toEqual([]);
});
