// @ts-check
// Onglet AAA Data : affiche le marché France / Europe depuis data/market.json.
const { test, expect } = require("@playwright/test");

test("AAA Data : onglet, cartes annuelles, graphique mensuel et pays", async ({ context, page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }, { name: "psf_feat", value: "pres", url: "http://localhost:8199" }]);
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  await page.goto("/", { waitUntil: "networkidle" });
  await expect(page.getByText("GA4", { exact: true })).toBeVisible();   // libellés sous les logos
  await expect(page.getByText("Search Console", { exact: true })).toBeVisible();
  await page.locator('[title="AAA Data"]').first().click();
  await expect(page.getByText("Le socle chiffré du marché")).toBeVisible();
  await expect(page.getByText("France — annuel")).toBeVisible();
  await expect(page.getByText("France — mensuel")).toBeVisible();
  await expect(page.getByText("Par pays · 2025")).toBeVisible();
  await expect(page.getByText("Allemagne").first()).toBeVisible();
  expect(erreurs).toEqual([]);
});
