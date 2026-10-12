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
  for (const [theme, nav, id] of [["Évolution", "Sessions par canal", "cbTrend"], ["Évolution", "Années passées", "cbHist"], ["Conversion", "Par jour", "cbConv"], ["Audience", "Jour & navigateurs", "cbSeason"], ["Évolution", "Contribution", "cbContrib"]]) {
    await page.getByText(theme, { exact: true }).first().click({ timeout: 3000 }).catch(() => {});
    await page.getByText(nav, { exact: true }).first().click({ timeout: 3000 }).catch(() => {});
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
