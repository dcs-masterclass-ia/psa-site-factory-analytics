// @ts-check
// Mode maintenance (MAINTENANCE=1 cote Vercel) : /api/config porte le drapeau, la
// page reste accessible mais floutee et bloquee derriere un message.
const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ context }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
});

const config = (page, maintenance) =>
  page.route("**/api/config", (route) => route.fulfill({ json: { googleClientId: null, maintenance } }));

test("maintenance active : page floutée, bloquée, message affiché", async ({ page }) => {
  await config(page, true);
  await page.goto("/", { waitUntil: "networkidle" });
  const voile = page.locator("#maint");
  await expect(voile).toBeVisible();
  await expect(voile).toContainText("Maintenance en cours");
  await expect(voile).toContainText("se rechargera automatiquement");
  // flou plein écran
  const flou = await voile.evaluate((e) => getComputedStyle(e).backdropFilter || getComputedStyle(e).webkitBackdropFilter);
  expect(flou).toContain("blur");
  // aucun clic ne traverse : le point sous la souris appartient au voile
  const traverse = await page.evaluate(() => !document.elementFromPoint(300, 300).closest("#maint"));
  expect(traverse).toBe(false);
  // le reste de la page est inerte (pas de clavier non plus)
  const inertes = await page.evaluate(() => [...document.body.children].filter((n) => n.id !== "maint" && n.hasAttribute("inert")).length);
  expect(inertes).toBeGreaterThan(0);
  expect(await page.evaluate(() => document.body.style.overflow)).toBe("hidden");
});

test("maintenance inactive : aucun voile", async ({ page }) => {
  await config(page, false);
  await page.goto("/", { waitUntil: "networkidle" });
  await page.waitForTimeout(500);
  await expect(page.locator("#maint")).toHaveCount(0);
  await expect(page.locator('div[title="Google Analytics 4"]').first()).toBeVisible();
});
