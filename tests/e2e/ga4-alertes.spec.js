// @ts-check
// GA4 > Pilotage > Alertes : liste filtrée sur la sélection, seuils réglables. L'API est simulée.
const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ context }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
});

test("alertes proactives : liste de la sélection et réglage des seuils", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  const config = { sessionsPct: 25, convPts: 1.5, etapePts: 5, fraicheurJours: 3, volumeMin: 500, notifier: false };
  const alertes = [
    { site: "OPEL FR", regle: "conversion", severite: "haute", titre: "Baisse du taux de conversion", detail: "18,0 % sur 7 jours contre 20,7 % sur les 28 jours précédents (−2,8 pt).", depuis: "2026-10-09" },
    { site: "FIAT IT", regle: "sessions", severite: "moyenne", titre: "Chute des sessions", detail: "ailleurs", depuis: "2026-10-08" },
  ];
  const posts = [];
  await page.route("**/api/events", (r) => r.fulfill({ json: { events: [], peutEcrire: false } }));
  await page.route("**/api/alertes", async (route) => {
    const req = route.request();
    if (req.method() === "GET") return route.fulfill({ json: { config, alertes, genere: "2026-10-10", peutEcrire: true } });
    const body = req.postDataJSON();
    posts.push(body);
    return route.fulfill({ json: { ok: true, config: body.config } });
  });
  await page.goto("/", { waitUntil: "networkidle" });
  await page.locator('[data-testid="scope-picker-toggle"]').click();
  await page.getByText("Aucun", { exact: true }).click();
  await page.locator('[data-testid="scope-search-input"]').fill("OPEL FR");
  await page.locator('[data-testid="scope-item"]').filter({ hasText: "OPEL FR" }).first().click();
  await page.keyboard.press("Escape");
  await page.mouse.click(5, 5);
  await page.waitForTimeout(1500);
  await page.getByText("Pilotage", { exact: true }).first().click();
  await page.getByText("Alertes", { exact: true }).first().click();
  await expect(page.getByText("Baisse du taux de conversion", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("FIAT IT", { exact: true })).toHaveCount(0);                   // autre site : hors sélection
  await expect(page.getByText(/Seuils : sessions −25 %/)).toBeVisible();

  await page.getByText("Régler les seuils", { exact: true }).click();
  await page.locator('input[type="number"]').first().fill("40");
  await page.getByText("Teams : désactivé", { exact: true }).click();
  await page.getByText("Enregistrer", { exact: true }).click();
  await expect.poll(() => posts.length).toBe(1);
  expect(posts[0]).toMatchObject({ action: "save_config", config: { sessionsPct: 40, notifier: true } });
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});
