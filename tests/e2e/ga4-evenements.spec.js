// @ts-check
// GA4 > Analyses détaillées > Événements : liste, ajout, repères sur les courbes. L'API (fonction Vercel) est simulée.
const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ context }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
});

test("calendrier d'événements : liste, ajout, repère sur la courbe de sessions", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  const events = [{ id: "E-1", date: "2026-09-20", type: "campagne", titre: "Lancement campagne Search Q3", sites: [] }];
  const posts = [];
  await page.route("**/api/events", async (route) => {
    const req = route.request();
    if (req.method() === "GET") return route.fulfill({ json: { events, peutEcrire: true, moi: "e2e@autobiz.com" } });
    const body = req.postDataJSON();
    posts.push(body);
    if (body.action === "save") events.push({ id: "E-2", ...body.event, auteur: "e2e@autobiz.com" });
    return route.fulfill({ json: { ok: true } });
  });
  await page.goto("/", { waitUntil: "networkidle" });
  await page.getByText("Événements", { exact: true }).first().click();
  await expect(page.getByText("Lancement campagne Search Q3").first()).toBeVisible();

  await page.getByText("+ Ajouter un événement").click();
  await page.locator('input[type="date"]').first().fill("2026-10-02");
  await page.getByPlaceholder("Ex. Lancement campagne Search Q3").fill("Nouveau bouton menu");
  await page.getByText("Site", { exact: true }).first().click();
  await page.getByText("Tous les sites", { exact: true }).first().click();
  await page.getByText("Enregistrer", { exact: true }).click();
  await expect(page.getByText("Nouveau bouton menu").first()).toBeVisible();
  expect(posts[0]).toMatchObject({ action: "save", event: { date: "2026-10-02", type: "site", titre: "Nouveau bouton menu", sites: [] } });

  await page.getByText("Sessions par canal", { exact: true }).first().click();
  await expect(page.locator("svg circle title", { hasText: "Lancement campagne Search Q3" })).toHaveCount(1);   // repère de l'événement sur la courbe
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});
