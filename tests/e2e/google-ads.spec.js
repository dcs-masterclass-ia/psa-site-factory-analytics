// @ts-check
// Onglet Google Ads : page « en cours de construction » (accès au compte en cours de récupération).
const { test, expect } = require("@playwright/test");

test("Google Ads : onglet en cours de construction", async ({ context, page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  await page.goto("/", { waitUntil: "networkidle" });
  await expect(page.getByText("Google Ads", { exact: true }).first()).toBeVisible();   // libellé du menu
  await page.locator('[title="Google Ads"]').first().click();
  await expect(page.getByText("En cours de construction")).toBeVisible();
  expect(erreurs).toEqual([]);
});
