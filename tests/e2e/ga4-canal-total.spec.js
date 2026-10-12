// @ts-check
// GA4 > Conversion : colonne Total par canal ; Fuites du tunnel : bascule « Par canal d'acquisition » avec effectifs.
const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ context }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
});

test("canal × device : colonne Total ; fuites par canal avec effectifs", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await page.route("**/api/events", (r) => r.fulfill({ json: { events: [], peutEcrire: false } }));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.getByText("Conversion", { exact: true }).first().click();
  await page.getByText("Canal × device", { exact: true }).first().click();
  await expect(page.getByText("Conversion par canal et device")).toBeVisible();
  await expect(page.getByText("Total", { exact: true }).first()).toBeVisible();
  await page.getByText("Fuites du tunnel", { exact: true }).first().click();
  await page.getByText("Par canal d'acquisition", { exact: true }).click();
  await expect(page.getByText("Moyenne du site").first()).toBeVisible();
  await page.screenshot({ path: process.env.TMPDIR + "/leaks.png" });
  expect(erreurs).toEqual([]);
});
