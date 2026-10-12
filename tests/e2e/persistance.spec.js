// @ts-check
// Rafraîchir la page garde l'onglet, la vue, les sites et la période choisis (sessionStorage propre à l'onglet du navigateur).
const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ context, page }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
});

test("rafraîchissement : même onglet, mêmes sites, même vue d'analyse", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator('[title="Search Console"]').first().click();
  await expect(page.getByText("Performances de recherche")).toBeVisible();
  await page.getByText("Requêtes", { exact: true }).first().click();
  await page.getByText("Opportunités", { exact: true }).first().click();
  await page.locator('[data-testid="scope-picker-toggle"]').click();
  await page.getByText("Aucun", { exact: true }).click();
  await page.locator('[data-testid="scope-search-input"]').fill("PEUGEOT FR");
  await page.locator('[data-testid="scope-item"]').filter({ hasText: "PEUGEOT FR" }).first().click();
  await page.keyboard.press("Escape");
  await page.mouse.click(5, 5);
  await expect(page.getByText("Opportunités SEO")).toBeVisible();

  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByText("Performances de recherche")).toBeVisible();           // toujours Search Console
  await expect(page.getByText("Opportunités SEO")).toBeVisible();                    // même vue
  await expect(page.getByText(/PEUGEOT FR/).first()).toBeVisible();                  // même site
  await expect(page.getByText("Marché entier · 91 sites")).toHaveCount(0);
  expect(erreurs).toEqual([]);
});
