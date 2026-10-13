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

test("mois entier : total mensuel GA4 (comme Looker) pour les sessions et le taux", async ({ page, context }) => {
  const fs = require("fs"), path = require("path");
  const fichier = path.join(__dirname, "../../data/citroen-fr.json");
  const d = JSON.parse(fs.readFileSync(fichier, "utf8"));
  test.skip(!d.repriseMonth || !d.repriseMonth["2026-09"], "données de septembre indisponibles");
  const prop = { daily: {}, month: { "2026-09": 1414658 } };   // total de la propriété (valeur GA4 relevée le 13/10/2026)
  await context.addCookies([{ name: "psf_user_email", value: "e2e%40autobiz.com", url: "http://localhost:8199" }]);
  await context.addInitScript(() => {
    sessionStorage.setItem("psf_ui_state", JSON.stringify({ source: "ga", from: "2026-09-01", to: "2026-09-30", sites: ["CITROEN FR"], cmpMode: "none" }));
  });
  await page.route("**/api/events", (r) => r.fulfill({ json: { events: [], peutEcrire: false } }));
  const ev = {};
  d.daily.d.forEach((j, i) => { ev[j] = Math.round((d.daily.rep[i] || 0) * 0.15); });
  await page.route(/\/data\/citroen-fr\.json$/, (r) => r.fulfill({ json: { ...d, evDaily: ev, propSessions: prop } }));
  await page.goto("/", { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const totalMois = d.repriseMonth["2026-09"].sessions;
  const evSept = d.daily.d.reduce((a, j, i) => a + (j.startsWith("2026-09") ? ev[j] : 0), 0);
  const attendu = (evSept / totalMois * 100).toFixed(1).replace(".", ",") + " %";
  const fmt = (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  const texte = (await page.evaluate(() => document.body.innerText)).replace(/ | /g, " ");
  expect(texte).toContain(fmt(totalMois).replace(/ /g, " "));    // sessions reprise = total mensuel
  expect(texte).toContain(attendu);                                  // taux = évènements ÷ total mensuel
  const tProp = prop.month["2026-09"];
  expect(texte).toContain(fmt(tProp).replace(/ /g, " "));        // sessions du site de la marque = total de la propriété
});
