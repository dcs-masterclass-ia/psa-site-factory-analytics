// @ts-check
// Au chargement (hard refresh), aucun message « Root.renderVals() : … » ne doit apparaître, même un instant :
// le premier rendu a lieu avant que les données soient chargées (listes de sites, mois… encore absentes).
const { test, expect } = require("@playwright/test");

for (const source of ["ga", "sc", "tb", "aaa", "c1st"]) {
  test(`premier rendu sans erreur — ${source}`, async ({ context, page }) => {
    const erreurs = [];
    page.on("console", (m) => { if (/renderVals|FAILED/.test(m.text())) erreurs.push(m.text().slice(0, 200)); });
    page.on("pageerror", (e) => erreurs.push(e.message));
    await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
    await page.route("**/api/**", (r) => r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } }));
    await page.goto("/", { waitUntil: "networkidle" });
    await page.evaluate((s) => sessionStorage.setItem("psf_ui_state", JSON.stringify({ source: s })), source);
    await page.reload({ waitUntil: "networkidle" });
    expect(erreurs).toEqual([]);
  });
}
