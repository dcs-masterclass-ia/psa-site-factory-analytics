// @ts-check
// GA4 > Analyses détaillées > Pilotage > Objectifs : avancement, projection, saisie. L'API est simulée.
const { test, expect } = require("@playwright/test");

test.beforeEach(async ({ context }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
});

test("objectifs annuels : tableau d'avancement et saisie d'une cible", async ({ page }) => {
  const erreurs = [];
  page.on("pageerror", (e) => erreurs.push(e.message));
  const annee = String(new Date().getFullYear());
  let cibles = { "PEUGEOT FR": 120000 };
  const posts = [];
  await page.route("**/api/events", (r) => r.fulfill({ json: { events: [], peutEcrire: false } }));
  await page.route("**/api/objectifs", async (route) => {
    const req = route.request();
    if (req.method() === "GET") return route.fulfill({ json: { annees: { [annee]: cibles }, moi: "e2e@autobiz.com" } });
    const body = req.postDataJSON();
    posts.push(body);
    cibles = Object.assign({}, cibles, Object.fromEntries(Object.entries(body.cibles).filter(([, v]) => v)));
    return route.fulfill({ json: { ok: true, annees: { [annee]: cibles } } });
  });
  await page.goto("/?sites=PEUGEOT%20FR", { waitUntil: "networkidle" });
  await page.waitForTimeout(2200);
  await page.getByText("Pilotage", { exact: true }).first().click();
  await expect(page.getByText("Objectifs annuels de leads")).toBeVisible();
  await expect(page.getByText("PEUGEOT FR", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/% de l'objectif atteint/)).toBeVisible();

  await page.getByText("Définir les objectifs", { exact: true }).click();
  await page.locator('input[type="number"]').first().fill("150000");
  await page.getByText("Enregistrer", { exact: true }).click();
  await expect.poll(() => posts.length).toBe(1);
  expect(posts[0]).toMatchObject({ action: "save", annee, cibles: { "PEUGEOT FR": 150000 } });
  expect(erreurs, erreurs.join(" | ")).toEqual([]);
});
