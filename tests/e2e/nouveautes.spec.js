// @ts-check
// Fenêtre « Du nouveau sur Converge » : une seule fois, uniquement pour les adresses Présentations.
const { test, expect } = require("@playwright/test");

test("la fenêtre de nouveautés s'affiche une fois pour les adresses Présentations", async ({ page, context }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }, { name: "psf_feat", value: "pres", url: "http://localhost:8199" }]);
  await page.goto("/", { waitUntil: "networkidle" });
  await expect(page.getByText("Du nouveau sur Converge")).toBeVisible({ timeout: 8000 });
  await expect(page.getByText("l'Allemagne, la Pologne, l'Autriche et le Royaume-Uni sont ajoutés.")).toBeVisible();
  await page.screenshot({ path: process.env.TMPDIR + "/nouveautes.png" });
  await page.getByText("Compris", { exact: true }).click();
  await expect(page.getByText("Du nouveau sur Converge")).toHaveCount(0);
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  await expect(page.getByText("Du nouveau sur Converge")).toHaveCount(0);
});

test("pas de fenêtre de nouveautés pour les autres adresses", async ({ page, context }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
  await page.goto("/", { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  await expect(page.getByText("Du nouveau sur Converge")).toHaveCount(0);
});
