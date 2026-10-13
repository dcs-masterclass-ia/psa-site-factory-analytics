// @ts-check
// Taux de conversion global = évènements d'estimation ÷ sessions du site de reprise (comme Looker) ; le tunnel reste en utilisateurs.
const { test, expect } = require("@playwright/test");

test("carte principale : conversion en sessions quand evDaily existe, tunnel inchangé", async ({ page, context }) => {
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
  await page.route("**/api/events", (r) => r.fulfill({ json: { events: [], peutEcrire: false } }));
  // chaque site reçoit un evDaily = 15 % des sessions de reprise du jour -> taux global attendu : 15,0 %
  await page.route(/\/data\/[a-z0-9-]+\.json$/, async (route) => {
    // lecture directe sur disque : le serveur statique mono-thread supporte mal 90 requêtes parallèles relayées
    const slug = route.request().url().split("/").pop();
    let j; try { j = JSON.parse(require("fs").readFileSync(require("path").join(__dirname, "../../data", slug), "utf8")); } catch (e) { return route.continue(); }
    if (j && j.daily && j.daily.d && j.daily.rep) {
      j.evDaily = {};
      j.daily.d.forEach((d, i) => { j.evDaily[d] = Math.round((j.daily.rep[i] || 0) * 0.15); });
    }
    return route.fulfill({ json: j });
  });
  await page.goto("/", { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await expect(page.getByText("estimations ÷ sessions du site de reprise").first()).toBeVisible();
  await expect(page.locator("span").filter({ hasText: /^15,0 %$/ }).first()).toBeVisible();
  // le tunnel, lui, garde son entrée en utilisateurs de la page d'accueil
  await expect(page.getByText("Visiteurs de l'accueil menés jusqu'à l'estimation").first()).toBeVisible();
});
