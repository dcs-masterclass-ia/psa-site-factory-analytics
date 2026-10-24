// @ts-check
// Onglet Leads : « Leads heure par heure » (miroir du monitor) et « Leads par jour, tous sites confondus ».
const { test, expect } = require("@playwright/test");

const arr = (f) => Array.from({ length: 48 }, (_, i) => Math.round(f(i)));

test("Leads : heure par heure et par jour", async ({ context, page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40exemple.test", url: "http://localhost:8199" }]);
  await page.route("**/api/**", (r) => {
    if (r.request().url().includes("/api/leads-horaire")) {
      const base = arr((i) => Math.max(5, 130 * Math.sin((Math.PI * (i - 10)) / 34)));
      const bloc = { aujourdhui: arr((i) => (i < 30 ? base[i] * 0.9 : 0)), hier: base, baseline: base };
      return r.fulfill({ json: { genere: "2026-10-15T08:00:00Z", horaire: { date: "2026-10-15", creneauxEcoules: 30, flotte: bloc, sites: { "OPEL FR": bloc, "PEUGEOT PT": bloc } } } });
    }
    return r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } });
  });
  await page.goto("/", { waitUntil: "networkidle" });
  await page.evaluate(() => sessionStorage.setItem("psf_ui_state", JSON.stringify({ source: "tb" })));
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByText("Leads par heure")).toBeVisible();
  await expect(page.getByText(/leads depuis minuit \(Toute la flotte\)/)).toBeVisible();
  await expect(page.getByText("Leads par jour", { exact: true })).toBeVisible();
  await page.getByText("Hier", { exact: true }).first().click();
  await expect(page.getByText(/leads hier \(Toute la flotte\)/)).toBeVisible();
  await page.getByText("Mois", { exact: true }).first().click();
  await expect(page.getByText(/\w+\. 26/).first()).toBeVisible();      // axe mensuel : « sept. 26 »…
  // survol : info-bulle sur les trois graphiques de la page Leads
  for (const id of ["tbSparkBox", "hhBox", "trBox"]) {
    const b = await page.locator("#" + id).boundingBox();
    await page.mouse.move(b.x + b.width * 0.55, b.y + b.height * 0.5);
    await expect(page.locator("#chartHovTip")).toBeVisible();
    await expect(page.locator("#chartHovTip")).toContainText("Leads");
  }
  expect(erreurs).toEqual([]);
});
