// @ts-check
// Mode sombre : le thème inverse toute la page ; les éléments marqués data-keep (logos, voitures, mascottes) doivent être ré-inversés.
const { test, expect } = require("@playwright/test");

test("mode sombre : les éléments data-keep sont ré-inversés", async ({ page }) => {
  await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
  await page.goto("/", { waitUntil: "networkidle" });
  const filtre = await page.evaluate(() => {
    document.documentElement.setAttribute("data-theme", "dark");
    const el = document.querySelector("[data-keep]");
    return el ? getComputedStyle(el).filter : null;
  });
  expect(filtre).toContain("invert(1)");
});
