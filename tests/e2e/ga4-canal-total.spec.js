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
  await page.getByText("Conversion par canal et appareil", { exact: true }).first().click();
  await expect(page.getByText("Conversion par canal et device")).toBeVisible();
  await expect(page.getByText("Total", { exact: true }).first()).toBeVisible();
  await page.getByText("Où les visiteurs abandonnent", { exact: true }).first().click();
  await page.getByText("Par canal d'acquisition", { exact: true }).click();
  await expect(page.getByText("Moyenne du site").locator("visible=true").first()).toBeVisible();      // pas l'info-bulle (cachée), qui contient la même expression
  await page.screenshot({ path: process.env.TMPDIR + "/leaks.png" });
  expect(erreurs).toEqual([]);
});

test("canal × device : colonne Sessions, canaux classés par volume décroissant", async ({ page }) => {
  await page.route("**/api/events", (r) => r.fulfill({ json: { events: [], peutEcrire: false } }));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.getByText("Conversion", { exact: true }).first().click();
  await page.getByText("Conversion par canal et appareil", { exact: true }).first().click();
  await expect(page.getByText("Sessions", { exact: true }).first()).toBeVisible();
  const carte = page.locator("div").filter({ hasText: /^Conversion par canal et device/ }).last();
  const valeurs = await page.evaluate(() => {
    const lignes = [...document.querySelectorAll("div")].filter((d) => getComputedStyle(d).display === "grid" && /\d/.test(d.innerText) && d.children.length === 6 && /%/.test(d.innerText));
    return lignes.map((l) => parseInt(l.children[1].innerText.split("\n")[0].replace(/[^\d]/g, ""), 10)).filter((n) => !isNaN(n));
  });
  expect(valeurs.length).toBeGreaterThan(2);
  expect(valeurs).toEqual([...valeurs].sort((a, b) => b - a));
});
