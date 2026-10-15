// @ts-check
// Paramètres (clic sur l'avatar) : profil en lecture seule, affichage, favoris ; enregistrement côté serveur.
const { test, expect } = require("@playwright/test");

test("Paramètres : ouverture par l'avatar et enregistrement d'une préférence", async ({ context, page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  let sauve = null;
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
  await page.route("**/api/**", (r) => {
    const u = r.request().url();
    if (u.includes("/api/preferences")) {
      if (r.request().method() === "PUT") { sauve = JSON.parse(r.request().postData() || "{}").prefs; return r.fulfill({ json: { prefs: sauve } }); }
      return r.fulfill({ json: { prefs: {} } });
    }
    return r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } });
  });
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator('[title^="Paramètres"]').first().click();
  await expect(page.getByText("Mon profil")).toBeVisible();
  await expect(page.getByText("e2e@autobiz.com").first()).toBeVisible();
  await page.getByText("7 jours", { exact: true }).click();
  await expect.poll(() => sauve && sauve.periode).toBe("7");
  await page.getByText("Pilotage des leads", { exact: true }).last().click();
  await expect.poll(() => sauve && sauve.accueil).toBe("tb");
  expect(erreurs).toEqual([]);
});

test("Paramètres : les préférences enregistrées s'appliquent à l'ouverture", async ({ context, page }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
  await page.route("**/api/**", (r) => {
    if (r.request().url().includes("/api/preferences")) return r.fulfill({ json: { prefs: { accueil: "tb", periode: "14", comparaison: "none" } } });
    return r.fulfill({ json: { events: [], peutEcrire: false, tickets: [] } });
  });
  await page.goto("/", { waitUntil: "networkidle" });
  await expect(page.getByText("Pilotage des leads").first()).toBeVisible();     // onglet d'accueil choisi
  await expect(page.getByText(/14 j/).first()).toBeVisible();                   // période par défaut : 14 jours
});
